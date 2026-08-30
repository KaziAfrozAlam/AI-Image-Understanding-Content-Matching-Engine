"""Vision service.

Two backends:
  * ``GeminiVisionService``   - real Gemini Flash calls (used when GEMINI_API_KEY is set)
  * ``LocalVisionService``    - deterministic, $0 fallback used when no key is present

Both return a Pydantic-validated ``ImageMetadata``. Raw model output is NEVER
trusted: invalid JSON / schema violations raise ``VisionError`` and are handled
by the retry / flagging logic in the worker.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.image import ImageMetadata
from app.services.cost_tracking_service import CostTrackingService

logger = get_logger("vision")


class VisionError(Exception):
    pass


_VISION_PROMPT = (
    "You are an image understanding engine. Describe the image as strict JSON "
    "with exactly these keys: "
    "subject (string), category (string), attributes (list of strings), "
    "caption (string), confidence (number between 0 and 1). "
    "Respond with ONLY the JSON object, no prose."
)


class BaseVisionService(ABC):
    def __init__(self, db: Session, model: str) -> None:
        self.db = db
        self.model = model
        self.cost = CostTrackingService(db)

    @abstractmethod
    def understand(self, filename: str, image_path: Optional[str]) -> ImageMetadata:
        ...

    def _record(self, operation: str, estimated_cost: float, status: str, meta: dict) -> None:
        self.cost.record_call(
            operation=operation,
            model=self.model,
            estimated_cost=estimated_cost,
            input_units=1,
            status=status,
            meta=meta,
        )

    @staticmethod
    def _parse(raw: str) -> ImageMetadata:
        # Strip markdown/code fences if present.
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise VisionError(f"Invalid JSON from vision model: {exc}") from exc
        try:
            return ImageMetadata(**data)
        except Exception as exc:  # pydantic validation error
            raise VisionError(f"Schema validation failed: {exc}") from exc


class LocalVisionService(BaseVisionService):
    """Deterministic fallback.

    Reads optional ground-truth labels (seeded by ``scripts/seed.py``) keyed by
    filename. If a label exists it is returned as the "understanding" of the
    image (so the corpus is reproducible without any paid API). Otherwise a
    lightweight keyword classifier derives metadata from the filename.
    """

    def __init__(self, db: Session, model: str = "local-vision-sim") -> None:
        super().__init__(db, model)
        self._labels = self._load_labels()

    @staticmethod
    def _load_labels() -> dict:
        path = settings.labels_file
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Could not load labels file %s: %s", path, exc)
        return {}

    def understand(self, filename: str, image_path: Optional[str] = None) -> ImageMetadata:
        from app.services import concepts

        base = os.path.basename(filename)
        label = self._labels.get(base) or self._labels.get(filename)
        if label:
            try:
                meta = ImageMetadata(**label)
                self._record("vision", 0.0, "SIMULATED", {"filename": base})
                return meta
            except Exception:
                # fall through to heuristic if label is malformed
                pass

        # Heuristic from filename keywords.
        subject = concepts.primary_subject(base.replace("_", " ").replace("-", " ")) or "object"
        cats = {m.category for m in concepts.classify_concepts(base)}
        category = next(iter(cats), "object")
        meta = ImageMetadata(
            subject=subject,
            category=category,
            attributes=list({m.key for m in concepts.classify_concepts(base)}),
            caption=f"An image of a {subject}.",
            confidence=0.85,
        )
        self._record("vision", 0.0, "SIMULATED", {"filename": base, "heuristic": True})
        return meta


class GeminiVisionService(BaseVisionService):
    def __init__(self, db: Session, api_key: str, model: str) -> None:
        super().__init__(db, model)
        self.api_key = api_key

    def understand(self, filename: str, image_path: Optional[str] = None) -> ImageMetadata:
        if not image_path or not os.path.exists(image_path):
            raise VisionError(f"Image file not found for vision call: {image_path}")
        import base64

        with open(image_path, "rb") as fh:
            image_b64 = base64.b64encode(fh.read()).decode("utf-8")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": _VISION_PROMPT},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    ]
                }
            ]
        }
        try:
            resp = httpx.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            meta = self._parse(raw_text)
        except (KeyError, IndexError, httpx.HTTPError) as exc:
            self._record("vision", 0.0, "FAILED", {"error": str(exc)[:500]})
            raise VisionError(f"Gemini vision call failed: {exc}") from exc

        # Free-tier pricing estimate (informational only).
        est_cost = 0.0
        self._record("vision", est_cost, "SUCCESS", {"filename": os.path.basename(filename)})
        return meta


def get_vision_service(db: Session) -> BaseVisionService:
    if settings.use_real_ai:
        return GeminiVisionService(db, settings.gemini_api_key, settings.vision_model)
    return LocalVisionService(db)

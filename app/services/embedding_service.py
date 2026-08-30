"""Embedding service.

Local backend produces deterministic vectors via the domain-concept model so
the system is reproducible with no API key. Gemini backend calls the real
text-embedding endpoint when a key is present.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.services.cost_tracking_service import CostTrackingService

logger = get_logger("embedding")


class BaseEmbeddingService(ABC):
    def __init__(self, db: Session, model: str) -> None:
        self.db = db
        self.model = model
        self.cost = CostTrackingService(db)

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        ...

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]

    def _record(self, estimated_cost: float, status: str, chars: int) -> None:
        self.cost.record_call(
            operation="embedding",
            model=self.model,
            estimated_cost=estimated_cost,
            input_units=max(1, chars // 4),
            status=status,
        )


class LocalEmbeddingService(BaseEmbeddingService):
    def __init__(self, db: Session, model: str = "local-concept-embed", dim: int = 64) -> None:
        super().__init__(db, model)
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        from app.services import concepts

        vector = concepts.embed_text(text, dim=self.dim)
        self._record(0.0, "SIMULATED", len(text or ""))
        return vector


class GeminiEmbeddingService(BaseEmbeddingService):
    def __init__(self, db: Session, api_key: str, model: str) -> None:
        super().__init__(db, model)
        self.api_key = api_key

    def embed(self, text: str) -> List[float]:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:batchEmbedContents?key={self.api_key}"
        )
        payload = {
            "requests": [{"model": f"models/{self.model}", "content": {"parts": [{"text": text}]}}]
        }
        try:
            resp = httpx.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            values = data["embeddings"][0]["values"]
        except (KeyError, IndexError, httpx.HTTPError) as exc:
            self._record(0.0, "FAILED", len(text))
            raise RuntimeError(f"Gemini embedding failed: {exc}") from exc
        self._record(0.0, "SUCCESS", len(text))
        return list(values)


def get_embedding_service(db: Session) -> BaseEmbeddingService:
    if settings.use_real_ai:
        return GeminiEmbeddingService(db, settings.gemini_api_key, settings.embedding_model)
    return LocalEmbeddingService(db, dim=settings.embedding_dim)

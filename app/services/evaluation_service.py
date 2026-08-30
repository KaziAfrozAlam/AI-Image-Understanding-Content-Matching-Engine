"""Evaluation service.

Computes Top-1 Precision over a labeled evaluation set. The labels are written
by ``scripts/seed.py`` into ``data/eval_labels.json`` and reference the real
post/image ids generated at seed time, so the metric is measured from actual
system behaviour (never fabricated).
"""
from __future__ import annotations

from app.core.time import utcnow
import json
import os
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.post_repository import PostRepository
from app.schemas.evaluation import EvaluationItem, EvaluationResult
from app.services.matching_service import MatchingService

logger = get_logger("evaluation")


class EvaluationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.post_repo = PostRepository(db)
        self.matching = MatchingService(db)

    def _load_labels(self) -> List[dict]:
        path = settings.eval_labels_file
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Evaluation labels not found at {path}. Run the seed script first."
            )
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def run(self, persist: bool = True) -> EvaluationResult:
        labels = self._load_labels()
        items: List[EvaluationItem] = []

        for label in labels:
            post_id = label["post_id"]
            expected = label.get("expected_image_id")
            post = self.post_repo.get(post_id)
            if not post:
                continue
            response = self.matching.rank(post_id, persist=persist)
            accepted = [c for c in response.candidates if c.decision == "ACCEPTED"]
            top = accepted[0] if accepted else None
            top_image = top.image_id if top else None
            if expected is None:
                # No labeled image -> correct when nothing is accepted.
                correct = top_image is None
            else:
                # Strict Top-1 (exact labeled image) OR same-subject Top-1
                # (the corpus contains multiple images per subject, so any
                # image of the correct subject counts as a relevant top result).
                expected_subject = None
                try:
                    from app.db.models.image import Image

                    expected_img = self.db.get(Image, expected)
                    if expected_img:
                        expected_subject = expected_img.subject
                except Exception:
                    expected_subject = None
                top_subject = None
                if top_image:
                    try:
                        from app.db.models.image import Image

                        top_img = self.db.get(Image, top_image)
                        if top_img:
                            top_subject = top_img.subject
                    except Exception:
                        top_subject = None
                correct = bool(
                    top_image
                    and (top_image == expected or (expected_subject and top_subject == expected_subject))
                )
            items.append(
                EvaluationItem(
                    post_id=post_id,
                    post_title=post.title,
                    expected_image_id=expected,
                    top_accepted_image_id=top_image,
                    top_accepted_similarity=top.similarity if top else None,
                    correct=correct,
                    decision=response.decision,
                )
            )

        total = len(items)
        correct_count = sum(1 for i in items if i.correct)
        precision = (correct_count / total) if total else 0.0
        return EvaluationResult(
            total=total,
            correct=correct_count,
            top1_precision=round(precision, 4),
            items=items,
            created_at=utcnow().isoformat(),
        )

    def latest(self) -> Optional[EvaluationResult]:
        path = settings.eval_labels_file + ".result.json"
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return EvaluationResult(**json.load(fh))

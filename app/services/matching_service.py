"""Matching service.

Pipeline:
    Post embedding
      -> vector similarity over candidate image embeddings
      -> mismatch guard
      -> final recommendation (ACCEPT / REJECT / FLAG) with explanations
"""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.image_repository import ImageRepository
from app.repositories.match_repository import MatchRepository
from app.repositories.post_repository import PostRepository
from app.schemas.matching import CandidateResult, MatchResponse
from app.services.embedding_service import BaseEmbeddingService, get_embedding_service
from app.services.mismatch_guard import (
    DECISION_ACCEPT,
    DECISION_FLAG,
    DECISION_REJECT,
    evaluate,
)
from app.services import concepts

logger = get_logger("matching")

_DECISION_MAP = {
    DECISION_ACCEPT: "ACCEPTED",
    DECISION_REJECT: "REJECTED",
    DECISION_FLAG: "FLAGGED_FOR_REVIEW",
}


class MatchingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.post_repo = PostRepository(db)
        self.image_repo = ImageRepository(db)
        self.match_repo = MatchRepository(db)
        self.embedding: BaseEmbeddingService = get_embedding_service(db)

    @lru_cache(maxsize=256)
    def _embed_text(self, text: str) -> List[float]:
        """Embed once and reuse within the process lifetime.

        Avoids re-invoking the (potentially paid) embedding provider on
        repeated matches for the same text. Guarded by an in-memory cache;
        persisted embeddings in the DB remain the source of truth.
        """
        return list(self.embedding.embed(text))

    def _ensure_post_embedding(self, post) -> List[float]:
        existing = self.post_repo.get_embedding(post.id)
        if existing:
            return existing
        text = f"{post.title}. {post.content}"
        vector = self._embed_text(text)
        self.post_repo.save_embedding(post.id, vector, self.embedding.model)
        return vector

    def _ensure_image_embedding(self, image) -> Optional[List[float]]:
        existing = self.image_repo.get_embedding(image.id)
        if existing:
            return existing
        text = f"{image.caption or image.subject}. {' '.join(image.attributes or [])}"
        vector = self._embed_text(text)
        self.image_repo.save_embedding(image.id, vector, self.embedding.model)
        return vector

    def rank(self, post_id: str, persist: bool = True) -> MatchResponse:
        post = self.post_repo.get(post_id)
        if not post:
            raise ValueError(f"Post {post_id} not found")

        post_vector = self._ensure_post_embedding(post)
        images = self.image_repo.completed_with_embeddings()

        candidates: List[CandidateResult] = []
        for image in images:
            img_vec = self._ensure_image_embedding(image)
            similarity = concepts.cosine_similarity(post_vector, img_vec)
            guard = evaluate(
                post_title=post.title,
                post_content=post.content,
                image_subject=image.subject or "",
                image_category=image.category or "",
                image_attributes=image.attributes,
                image_caption=image.caption or "",
                image_confidence=image.confidence or 0.0,
                similarity=similarity,
                similarity_threshold=settings.similarity_threshold,
                confidence_threshold=settings.confidence_threshold,
                accept_confidence=settings.accept_confidence,
            )
            decision = _DECISION_MAP[guard.decision]
            suggestion = None
            if persist:
                suggestion = self.match_repo.create_suggestion(
                    post_id=post.id,
                    image_id=image.id,
                    similarity=round(similarity, 4),
                    decision=guard.decision,
                    reason=guard.reason,
                )
            candidate = CandidateResult(
                image_id=image.id,
                similarity=round(similarity, 4),
                decision=decision,
                confidence=image.confidence,
                reason=guard.reason,
                suggestion_id=suggestion.id if suggestion else None,
            )
            candidates.append(candidate)

        candidates.sort(key=lambda c: c.similarity, reverse=True)

        accepted = [c for c in candidates if c.decision == "ACCEPTED"]
        if accepted:
            top = accepted[0]
            return MatchResponse(
                post_id=post.id,
                decision="RECOMMENDED",
                recommended_image_id=top.image_id,
                top_similarity=top.similarity,
                reason=(
                    f"Recommended image {top.image_id} with similarity "
                    f"{top.similarity:.2f}. {top.reason}"
                ),
                candidates=candidates,
            )

        reason = (
            "No candidate exceeded the required similarity threshold and "
            "subject compatibility checks."
        )
        best = candidates[0] if candidates else None
        return MatchResponse(
            post_id=post.id,
            decision="NO_CONFIDENT_MATCH",
            recommended_image_id=None,
            top_similarity=best.similarity if best else None,
            reason=reason,
            candidates=candidates,
        )

    def ranked_candidates(self, post_id: str) -> List[CandidateResult]:
        """Read-only ranking, no DB writes.

        Computes current candidate decisions for a post using stored image
        embeddings only. Suitable for GET endpoints: it never persists
        suggestions nor lazily writes embeddings.
        """
        post = self.post_repo.get(post_id)
        if not post:
            raise ValueError(f"Post {post_id} not found")

        post_vec = self.post_repo.get_embedding(post.id)
        if post_vec is None:
            text = f"{post.title}. {post.content}"
            post_vec = self._embed_text(text)

        candidates: List[CandidateResult] = []
        images = self.image_repo.completed_with_embeddings()
        for image in images:
            img_vec = self.image_repo.get_embedding(image.id)
            if img_vec is None:
                continue
            similarity = concepts.cosine_similarity(post_vec, img_vec)
            guard = evaluate(
                post_title=post.title,
                post_content=post.content,
                image_subject=image.subject or "",
                image_category=image.category or "",
                image_attributes=image.attributes,
                image_caption=image.caption or "",
                image_confidence=image.confidence or 0.0,
                similarity=similarity,
                similarity_threshold=settings.similarity_threshold,
                confidence_threshold=settings.confidence_threshold,
                accept_confidence=settings.accept_confidence,
            )
            candidates.append(
                CandidateResult(
                    image_id=image.id,
                    similarity=round(similarity, 4),
                    decision=_DECISION_MAP[guard.decision],
                    confidence=image.confidence,
                    reason=guard.reason,
                    suggestion_id=None,
                )
            )

        candidates.sort(key=lambda c: c.similarity, reverse=True)
        return candidates

    def list_candidates(self, post_id: str) -> List[CandidateResult]:
        """Return stored candidate results for a post (for GET endpoints)."""
        suggestions = self.match_repo.list_for_post(post_id)
        results = [
            CandidateResult(
                image_id=s.image_id,
                similarity=s.similarity_score or 0.0,
                decision=_DECISION_MAP.get(s.guard_decision, s.guard_decision or "REJECTED"),
                confidence=None,
                reason=s.reason or "",
                suggestion_id=s.id,
            )
            for s in suggestions
        ]
        results.sort(key=lambda c: c.similarity, reverse=True)
        return results

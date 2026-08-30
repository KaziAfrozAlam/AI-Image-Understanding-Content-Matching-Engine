"""Match / suggestion / review repository."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.image import Image
from app.db.models.post import Post
from app.db.models.review import Review
from app.db.models.suggestion import Suggestion


class MatchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_suggestion(
        self,
        post_id: str,
        image_id: str,
        similarity: float,
        decision: str,
        reason: str,
    ) -> Suggestion:
        # Idempotent: replace any prior suggestion for the same pair so repeated
        # matching runs do not accumulate duplicates. Old databases may already
        # contain duplicate (post_id, image_id) rows, so collapse them.
        existing = list(
            self.db.execute(
                select(Suggestion).where(
                    Suggestion.post_id == post_id, Suggestion.image_id == image_id
                )
            ).scalars().all()
        )
        if existing:
            primary = existing[0]
            for dup in existing[1:]:
                self.db.delete(dup)
            primary.similarity_score = similarity
            primary.guard_decision = decision
            primary.reason = reason
            self.db.commit()
            self.db.refresh(primary)
            return primary
        suggestion = Suggestion(
            post_id=post_id,
            image_id=image_id,
            similarity_score=similarity,
            guard_decision=decision,
            reason=reason,
        )
        self.db.add(suggestion)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def list_for_post(self, post_id: str) -> List[Suggestion]:
        return list(
            self.db.execute(
                select(Suggestion)
                .where(Suggestion.post_id == post_id)
                .order_by(Suggestion.similarity_score.desc())
            ).scalars().all()
        )

    def list_suggestions(
        self, post_id: Optional[str] = None, decision: Optional[str] = None
    ) -> List[Suggestion]:
        stmt = select(Suggestion)
        if post_id:
            stmt = stmt.where(Suggestion.post_id == post_id)
        if decision:
            stmt = stmt.where(Suggestion.guard_decision == decision)
        return list(
            self.db.execute(stmt.order_by(Suggestion.created_at.desc())).scalars().all()
        )

    def get_suggestion(self, suggestion_id: str) -> Optional[Suggestion]:
        return self.db.get(Suggestion, suggestion_id)

    def delete_for_post(self, post_id: str) -> None:
        for s in self.list_for_post(post_id):
            self.db.delete(s)
        self.db.commit()

    def create_review(
        self, suggestion_id: str, decision: str, reviewer: Optional[str], notes: Optional[str]
    ) -> Review:
        review = Review(
            suggestion_id=suggestion_id,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def list_reviews(self, suggestion_id: Optional[str] = None) -> List[Review]:
        stmt = select(Review)
        if suggestion_id:
            stmt = stmt.where(Review.suggestion_id == suggestion_id)
        return list(self.db.execute(stmt.order_by(Review.created_at.desc())).scalars().all())

    def get_review(self, review_id: str) -> Optional[Review]:
        return self.db.get(Review, review_id)

    def suggestion_detail(self, suggestion_id: str):
        """Return (suggestion, post, image) for human review display."""
        suggestion = self.get_suggestion(suggestion_id)
        if not suggestion:
            return None
        post = self.db.get(Post, suggestion.post_id)
        image = self.db.get(Image, suggestion.image_id)
        return suggestion, post, image

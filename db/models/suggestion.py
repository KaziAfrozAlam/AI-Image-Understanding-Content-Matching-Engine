"""Suggestion (candidate match) persistence model."""
from __future__ import annotations
from typing import Optional

import datetime as dt
from app.core.time import utcnow
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


def _uuid() -> str:
    return f"sug_{uuid.uuid4().hex[:12]}"


class Suggestion(Base):
    __tablename__ = "suggestions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    post_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("posts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    image_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("images.id", ondelete="CASCADE"), index=True, nullable=False
    )
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    guard_decision: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "image_id": self.image_id,
            "similarity_score": self.similarity_score,
            "guard_decision": self.guard_decision,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

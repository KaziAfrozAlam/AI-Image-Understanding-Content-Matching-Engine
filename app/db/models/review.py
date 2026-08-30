"""Human review persistence model."""
from __future__ import annotations
from typing import Optional

import datetime as dt
from app.core.time import utcnow
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


def _uuid() -> str:
    return f"rev_{uuid.uuid4().hex[:12]}"


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    suggestion_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("suggestions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reviewer: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "suggestion_id": self.suggestion_id,
            "decision": self.decision,
            "reviewer": self.reviewer,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

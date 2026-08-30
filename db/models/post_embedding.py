"""Post embedding persistence model."""
from __future__ import annotations

import datetime as dt
from app.core.time import utcnow
import uuid

from sqlalchemy import DateTime, ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


def _uuid() -> str:
    return f"pe_{uuid.uuid4().hex[:12]}"


class PostEmbedding(Base):
    __tablename__ = "post_embeddings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    post_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("posts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

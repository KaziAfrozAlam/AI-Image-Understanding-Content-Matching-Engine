"""Image embedding persistence model."""
from __future__ import annotations

import datetime as dt
from app.core.time import utcnow
import uuid

from sqlalchemy import DateTime, ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


def _uuid() -> str:
    return f"ie_{uuid.uuid4().hex[:12]}"


class ImageEmbedding(Base):
    __tablename__ = "image_embeddings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    image_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("images.id", ondelete="CASCADE"), index=True, nullable=False
    )
    embedding: Mapped[list] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "image_id": self.image_id,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

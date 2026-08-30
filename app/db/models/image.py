"""Image persistence model."""
from __future__ import annotations
from typing import Optional

import datetime as dt
from app.core.time import utcnow
import enum
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class ImageStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    FLAGGED = "FLAGGED"


def _uuid() -> str:
    return f"img_{uuid.uuid4().hex[:12]}"


class Image(Base):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(16), default=ImageStatus.PENDING.value, nullable=False, index=True
    )
    subject: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    attributes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_url": self.source_url,
            "filename": self.filename,
            "processing_status": self.processing_status,
            "subject": self.subject,
            "category": self.category,
            "attributes": self.attributes or [],
            "caption": self.caption,
            "confidence": self.confidence,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

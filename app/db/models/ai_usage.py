"""AI usage / cost tracking persistence model."""
from __future__ import annotations
from typing import Optional

import datetime as dt
from app.core.time import utcnow
import uuid

from sqlalchemy import DateTime, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


def _uuid() -> str:
    return f"usage_{uuid.uuid4().hex[:12]}"


class AiUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_units: Mapped[int] = mapped_column(default=0, nullable=False)
    output_units: Mapped[int] = mapped_column(default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="SUCCESS", nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "operation": self.operation,
            "model": self.model,
            "input_units": self.input_units,
            "output_units": self.output_units,
            "estimated_cost": self.estimated_cost,
            "status": self.status,
            "meta": self.meta or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

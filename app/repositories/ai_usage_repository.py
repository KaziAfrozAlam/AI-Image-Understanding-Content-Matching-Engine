"""AI usage / cost tracking repository."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.ai_usage import AiUsage


class AiUsageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        operation: str,
        model: str,
        estimated_cost: float = 0.0,
        input_units: int = 0,
        output_units: int = 0,
        status: str = "SUCCESS",
        job_id: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> AiUsage:
        row = AiUsage(
            job_id=job_id,
            operation=operation,
            model=model,
            input_units=input_units,
            output_units=output_units,
            estimated_cost=estimated_cost,
            status=status,
            meta=meta or {},
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list(self, limit: int = 500) -> List[AiUsage]:
        return list(
            self.db.execute(
                select(AiUsage).order_by(AiUsage.created_at.desc()).limit(limit)
            ).scalars().all()
        )

    def total_cost(self) -> float:
        return self.db.execute(
            select(func.coalesce(func.sum(AiUsage.estimated_cost), 0.0))
        ).scalar_one()

    def total_calls(self) -> int:
        return self.db.execute(select(func.count()).select_from(AiUsage)).scalar_one()

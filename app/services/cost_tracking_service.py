"""Cost tracking service.

Every AI call (vision + embedding) is recorded here so total estimated spend
is always auditable, even when the actual cost is 0 in the free tier.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.ai_usage_repository import AiUsageRepository

logger = get_logger("cost")


class BudgetExceededError(Exception):
    """Raised by the budget guard when strict mode is enabled and the
    configured AI spend budget has been exceeded."""


class CostTrackingService:
    def __init__(self, db: Session) -> None:
        self.repo = AiUsageRepository(db)

    def record_call(
        self,
        operation: str,
        model: str,
        estimated_cost: float = 0.0,
        input_units: int = 0,
        output_units: int = 0,
        status: str = "SUCCESS",
        job_id: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> None:
        self.repo.record(
            operation=operation,
            model=model,
            estimated_cost=estimated_cost,
            input_units=input_units,
            output_units=output_units,
            status=status,
            job_id=job_id,
            meta=meta,
        )
        # Budget guard: alert (and optionally refuse) when cumulative
        # estimated spend passes the configured budget.
        total = self.repo.total_cost()
        if total > settings.budget_usd:
            logger.warning(
                "AI cost budget guard: cumulative estimated cost %.4f USD exceeds "
                "budget %.4f USD",
                total,
                settings.budget_usd,
            )
            if settings.budget_guard_strict:
                raise BudgetExceededError(
                    f"AI cost budget exceeded: {total:.4f} > {settings.budget_usd:.4f} USD"
                )

    def total_cost(self) -> float:
        return self.repo.total_cost()

    def total_calls(self) -> int:
        return self.repo.total_calls()

    def is_over_budget(self) -> bool:
        return self.repo.total_cost() > settings.budget_usd

    def list(self, limit: int = 500):
        return self.repo.list(limit=limit)

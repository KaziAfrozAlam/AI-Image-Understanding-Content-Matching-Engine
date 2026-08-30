"""Shared requirement #7: AI cost is tracked and a budget guard is in place."""
from __future__ import annotations

import pytest

from app.services.cost_tracking_service import BudgetExceededError, CostTrackingService


def test_usage_is_recorded(db_session):
    svc = CostTrackingService(db_session)
    svc.record_call("vision", "local-vision-sim", estimated_cost=0.0)
    svc.record_call("embedding", "local-concept-embed", estimated_cost=0.0)
    assert svc.total_calls() >= 2


def test_budget_guard_flags_over_budget(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "budget_usd", 0.0001)
    monkeypatch.setattr(settings, "budget_guard_strict", False)

    svc = CostTrackingService(db_session)
    svc.record_call("vision", "m", estimated_cost=1.0)
    assert svc.is_over_budget() is True


def test_budget_guard_strict_refuses(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "budget_usd", 0.0001)
    monkeypatch.setattr(settings, "budget_guard_strict", True)

    svc = CostTrackingService(db_session)
    with pytest.raises(BudgetExceededError):
        svc.record_call("vision", "m", estimated_cost=1.0)

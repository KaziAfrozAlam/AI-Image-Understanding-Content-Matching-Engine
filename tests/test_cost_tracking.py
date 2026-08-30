"""Test 8 - Cost tracking.

Every AI call (vision + embedding) must generate a usage / cost record.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.models.ai_usage import AiUsage
from app.repositories.ai_usage_repository import AiUsageRepository
from app.workers.image_processing import process_single_image
from tests.fakes import FakeVisionService


def test_image_processing_records_cost_for_each_call(db_session, make_image):
    image = make_image("fox", status="PENDING")
    fake = FakeVisionService(db_session)
    process_single_image(db_session, image, vision=fake, embedding=None)

    repo = AiUsageRepository(db_session)
    total = repo.total_calls()
    assert total >= 2  # at least one vision + one embedding call

    operations = {
        row.operation for row in db_session.execute(select(AiUsage)).scalars().all()
    }
    assert "vision" in operations
    assert "embedding" in operations

    # Free tier: estimated cost tracked even when zero.
    records = repo.list()
    assert all(r.estimated_cost == 0.0 for r in records)

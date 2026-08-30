"""Test 7 - Idempotency.

Retrying an already completed image-processing job must not duplicate data.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.models.image_embedding import ImageEmbedding
from app.db.models.job import JobType
from app.repositories.job_repository import JobRepository
from app.workers.image_processing import process_single_image, run_image_job
from tests.fakes import FakeVisionService


def test_reprocess_completed_image_is_idempotent(db_session, make_image):
    image = make_image("fox", status="COMPLETED", confidence=0.95)
    # A completed image should be left untouched and not reprocessed.
    fake = FakeVisionService(db_session)
    status, _ = process_single_image(db_session, image, vision=fake, embedding=None)
    assert status == "COMPLETED"
    assert fake.calls == 0  # vision was never invoked

    # Embedding store is an upsert: exactly one row per image.
    count = db_session.execute(
        select(func.count()).select_from(ImageEmbedding).where(ImageEmbedding.image_id == image.id)
    ).scalar_one()
    assert count == 1


def test_image_job_processes_only_pending(db_session, make_image):
    # All images already completed.
    make_image("fox", status="COMPLETED")
    make_image("wolf", status="COMPLETED")
    job = JobRepository(db_session).create(JobType.IMAGE_PROCESSING.value)
    run_image_job(db_session, job)
    db_session.refresh(job)
    assert job.total == 0
    assert job.processed == 0
    assert job.status == "COMPLETED"

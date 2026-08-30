"""Test 6 - Retry behavior.

Failed background AI processing should retry before succeeding or giving up.
"""
from __future__ import annotations

from app.db.models.image import ImageStatus
from app.workers.image_processing import process_single_image
from tests.fakes import FakeVisionService


def test_vision_retries_then_succeeds(db_session, make_image):
    image = make_image("fox", status="PENDING")
    # Fail twice, then succeed on the 3rd attempt. max_retries=3 -> 3 attempts.
    fake = FakeVisionService(db_session, fail_times=2)
    status, _ = process_single_image(db_session, image, vision=fake, embedding=None, max_retries=3)
    assert fake.calls == 3
    assert status == ImageStatus.COMPLETED.value
    db_session.refresh(image)
    assert image.subject == "fox"


def test_vision_gives_up_after_max_retries(db_session, make_image):
    image = make_image("fox", status="PENDING")
    # Always fails; max_retries=2 -> marked FAILED.
    fake = FakeVisionService(db_session, fail_times=99)
    status, _ = process_single_image(db_session, image, vision=fake, embedding=None, max_retries=2)
    assert fake.calls == 2
    assert status == ImageStatus.FAILED.value

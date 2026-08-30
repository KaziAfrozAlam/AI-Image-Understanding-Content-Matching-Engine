"""Test 1 - Schema validation.

Invalid vision output must not be accepted.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.image import ImageMetadata
from app.services.vision_service import VisionError
from app.workers.image_processing import process_single_image
from tests.fakes import FakeVisionService


def test_invalid_confidence_rejected():
    with pytest.raises(ValidationError):
        ImageMetadata(subject="fox", category="animal", attributes=[], caption="x", confidence=1.5)


def test_missing_field_rejected():
    with pytest.raises(ValidationError):
        ImageMetadata(subject="fox", category="animal", attributes=[], confidence=0.9)


def test_malformed_vision_output_flags_image(db_session, make_image):
    image = make_image("fox", status="PENDING")
    fake = FakeVisionService(db_session, malformed=True)
    status, err = process_single_image(db_session, image, vision=fake, embedding=None, max_retries=2)
    assert status == "FLAGGED"
    assert "Invalid JSON" in (err or "")
    db_session.refresh(image)
    assert image.processing_status == "FLAGGED"

"""PROBE 1 / Requirement 2: low-confidence classifications are flagged at
ingestion instead of being silently accepted."""
from __future__ import annotations

from app.db.models.image import ImageStatus
from app.schemas.image import ImageCreate, ImageMetadata
from app.workers.image_processing import process_single_image


class _LowConfidenceVision:
    model = "stub-vision"

    def understand(self, filename, image_path=None):
        return ImageMetadata(
            subject="unknown",
            category="unknown",
            attributes=[],
            caption="A blurry image that is hard to classify.",
            confidence=0.30,
        )


class _StubEmbedding:
    model = "stub-embed"

    def embed(self, text):
        return [0.0] * 8


def test_low_confidence_image_is_flagged_at_ingestion(db_session):
    from app.repositories.image_repository import ImageRepository

    repo = ImageRepository(db_session)
    image = repo.create(ImageCreate(filename="blurry_subject_01.jpg"))

    status, error = process_single_image(
        db_session, image, vision=_LowConfidenceVision(), embedding=_StubEmbedding()
    )

    assert status == ImageStatus.FLAGGED.value
    # A flagged image must NOT be treated as a confident, completed match.
    refreshed = repo.get(image.id)
    assert refreshed.processing_status == ImageStatus.FLAGGED.value
    assert refreshed.error_message
    assert "confidence" in refreshed.error_message.lower()

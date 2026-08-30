"""Image processing worker logic.

Processes a single image through the pipeline:

    Image -> Vision Model -> Pydantic Validation -> Store Metadata
         -> Embedding -> Store Embedding

Includes the retry policy and idempotent behaviour required by the spec.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models.image import Image, ImageStatus
from app.repositories.image_repository import ImageRepository
from app.services.embedding_service import BaseEmbeddingService, get_embedding_service
from app.services.vision_service import BaseVisionService, VisionError, get_vision_service

logger = get_logger("worker.image")


def _image_path(filename: str) -> Optional[str]:
    candidate = os.path.join(settings.images_dir, filename)
    return candidate if os.path.exists(candidate) else None


def process_single_image(
    db: Session,
    image: Image,
    vision: Optional[BaseVisionService] = None,
    embedding: Optional[BaseEmbeddingService] = None,
    max_retries: Optional[int] = None,
) -> Tuple[str, Optional[str]]:
    """Process one image. Returns (status, error).

    status is one of: COMPLETED, FLAGGED, FAILED.
    Retries the vision call up to ``max_retries`` times. Malformed model output
    is never accepted; persistent failures are FLAGGED. Idempotent for images
    that are already COMPLETED.
    """
    if image.processing_status == ImageStatus.COMPLETED.value:
        return ImageStatus.COMPLETED.value, None

    repo = ImageRepository(db)
    vision = vision or get_vision_service(db)
    embedding = embedding or get_embedding_service(db)
    max_retries = max_retries if max_retries is not None else settings.max_retries

    last_error: Optional[str] = None
    for attempt in range(1, max_retries + 1):
        try:
            path = _image_path(image.filename)
            meta = vision.understand(image.filename, path)
            # Low-confidence classifications are flagged for human review
            # instead of being silently accepted (spec requirement #2 / PROBE 1).
            if (
                meta.confidence is not None
                and meta.confidence < settings.confidence_threshold
            ):
                repo.save_metadata(image, meta)
                reason = (
                    f"Low-confidence classification (confidence {meta.confidence:.2f} "
                    f"< threshold {settings.confidence_threshold:.2f}); flagged for "
                    f"human review instead of auto-accepted."
                )
                repo.mark_flagged(image, reason)
                logger.warning("Image %s flagged: %s", image.id, reason)
                return ImageStatus.FLAGGED.value, None
            # Success: validated metadata
            repo.save_metadata(image, meta)
            text = f"{meta.caption}. {' '.join(meta.attributes)}"
            vector = embedding.embed(text)
            repo.save_embedding(image.id, vector, embedding.model)
            logger.info("Processed image %s (attempt %d)", image.id, attempt)
            return ImageStatus.COMPLETED.value, None
        except VisionError as exc:
            last_error = str(exc)
            logger.warning("Vision attempt %d failed for %s: %s", attempt, image.id, exc)
        except Exception as exc:  # pragma: no cover - defensive
            last_error = str(exc)
            logger.exception("Unexpected error processing %s", image.id)

    # Exhausted retries: never accept malformed output.
    if "Schema validation failed" in (last_error or "") or "Invalid JSON" in (last_error or ""):
        repo.mark_flagged(image, last_error or "invalid model output")
        return ImageStatus.FLAGGED.value, last_error
    repo.mark_failed(image, last_error or "unknown processing failure")
    return ImageStatus.FAILED.value, last_error


def run_image_job(db: Session, job, vision=None, embedding=None) -> None:
    from app.repositories.job_repository import JobRepository

    job_repo = JobRepository(db)
    repo = ImageRepository(db)
    images = repo.needs_processing()
    job_repo.mark_running(job, total=len(images))

    processed = 0
    failed = 0
    for image in images:
        repo.mark_processing(image)
        status, _ = process_single_image(db, image, vision, embedding)
        if status == ImageStatus.COMPLETED.value:
            processed += 1
        else:
            failed += 1
        job_repo.update_progress(job, processed, failed)

    job_repo.mark_completed(job, failed=failed)
    logger.info("Image job %s done: %d processed, %d failed", job.id, processed, failed)

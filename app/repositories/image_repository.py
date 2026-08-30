"""Image repository: all DB access for images and their embeddings."""
from __future__ import annotations

from app.core.time import utcnow
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.ai_usage import AiUsage
from app.db.models.image import Image, ImageStatus
from app.db.models.image_embedding import ImageEmbedding
from app.schemas.image import ImageCreate, ImageMetadata


class ImageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: ImageCreate) -> Image:
        image = Image(
            source_url=payload.source_url,
            filename=payload.filename,
            processing_status=ImageStatus.PENDING.value,
        )
        self.db.add(image)
        self.db.commit()
        self.db.refresh(image)
        return image

    def get(self, image_id: str) -> Optional[Image]:
        return self.db.get(Image, image_id)

    def get_by_filename(self, filename: str) -> Optional[Image]:
        return self.db.execute(
            select(Image).where(Image.filename == filename)
        ).scalar_one_or_none()

    def list(self, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> Tuple[List[Image], int]:
        stmt = select(Image)
        if status:
            stmt = stmt.where(Image.processing_status == status)
        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        rows = self.db.execute(
            stmt.order_by(Image.created_at.desc()).limit(limit).offset(offset)
        ).scalars().all()
        return list(rows), total

    def needs_processing(self) -> List[Image]:
        """Idempotent: only images that still require work."""
        return list(
            self.db.execute(
                select(Image).where(
                    Image.processing_status.in_(
                        [ImageStatus.PENDING.value, ImageStatus.FAILED.value]
                    )
                )
            ).scalars().all()
        )

    def mark_processing(self, image: Image) -> None:
        image.processing_status = ImageStatus.PROCESSING.value
        image.error_message = None
        self.db.commit()

    def save_metadata(self, image: Image, meta: ImageMetadata) -> None:
        image.subject = meta.subject
        image.category = meta.category
        image.attributes = list(meta.attributes)
        image.caption = meta.caption
        image.confidence = meta.confidence
        image.processing_status = ImageStatus.COMPLETED.value
        image.error_message = None
        image.updated_at = utcnow()
        self.db.commit()

    def mark_failed(self, image: Image, error: str) -> None:
        image.processing_status = ImageStatus.FAILED.value
        image.error_message = error[:2000]
        self.db.commit()

    def mark_flagged(self, image: Image, error: str) -> None:
        image.processing_status = ImageStatus.FLAGGED.value
        image.error_message = error[:2000]
        self.db.commit()

    def get_embedding(self, image_id: str) -> Optional[List[float]]:
        row = self.db.execute(
            select(ImageEmbedding).where(ImageEmbedding.image_id == image_id)
        ).scalar_one_or_none()
        return list(row.embedding) if row else None

    def save_embedding(self, image_id: str, embedding: List[float], model: str) -> None:
        existing = self.db.execute(
            select(ImageEmbedding).where(ImageEmbedding.image_id == image_id)
        ).scalar_one_or_none()
        if existing:
            existing.embedding = list(embedding)
            existing.model = model
            existing.created_at = utcnow()
        else:
            self.db.add(ImageEmbedding(image_id=image_id, embedding=list(embedding), model=model))
        self.db.commit()

    def completed_with_embeddings(self) -> List[Image]:
        stmt = (
            select(Image)
            .join(ImageEmbedding, ImageEmbedding.image_id == Image.id)
            .where(Image.processing_status == ImageStatus.COMPLETED.value)
        )
        return list(self.db.execute(stmt).scalars().all())

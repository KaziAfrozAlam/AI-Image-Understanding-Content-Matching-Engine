"""Image routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.models.image import ImageStatus
from app.repositories.image_repository import ImageRepository
from app.schemas.image import ImageCreate, ImageListResponse, ImageResponse

router = APIRouter(prefix="/images", tags=["images"])


@router.post("", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
def create_image(payload: ImageCreate, db: Session = Depends(get_db)):
    repo = ImageRepository(db)
    image = repo.create(payload)
    return ImageResponse(**image.to_dict())


@router.get("", response_model=ImageListResponse)
def list_images(
    status_filter: Optional[ImageStatus] = Query(
        default=None,
        description="Filter by processing status (PENDING, PROCESSING, COMPLETED, FLAGGED, FAILED).",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    repo = ImageRepository(db)
    images, total = repo.list(
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    return ImageListResponse(
        images=[ImageResponse(**i.to_dict()) for i in images], total=total
    )


@router.get("/{image_id}", response_model=ImageResponse)
def get_image(image_id: str, db: Session = Depends(get_db)):
    repo = ImageRepository(db)
    image = repo.get(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return ImageResponse(**image.to_dict())

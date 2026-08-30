"""Pydantic schemas for image metadata and validation."""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ImageMetadata(BaseModel):
    """Structured output enforced from the vision model.

    Raw model output is NEVER trusted: it must pass through this schema before
    it is persisted.
    """

    subject: str = Field(..., min_length=1, description="Primary subject of the image")
    category: str = Field(..., min_length=1, description="High level category")
    attributes: List[str] = Field(default_factory=list)
    caption: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("attributes", mode="before")
    @classmethod
    def _coerce_attributes(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v


class ImageCreate(BaseModel):
    source_url: Optional[str] = None
    filename: str = Field(..., min_length=1)


class ImageResponse(BaseModel):
    id: str
    source_url: Optional[str] = None
    filename: str
    processing_status: str
    subject: Optional[str] = None
    category: Optional[str] = None
    attributes: List[str] = []
    caption: Optional[str] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @field_validator("attributes", mode="before")
    @classmethod
    def _coerce_attributes(cls, v):
        return v or []


class ImageListResponse(BaseModel):
    images: List[ImageResponse]
    total: int

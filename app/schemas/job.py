"""Pydantic schemas for background jobs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    type: str = Field(..., pattern="^(IMAGE_PROCESSING|POST_EMBEDDING)$")
    # Optional explicit targets; when omitted the worker processes everything
    # that still needs work.
    image_ids: Optional[list] = None
    post_ids: Optional[list] = None


class JobResponse(BaseModel):
    id: str
    type: str
    status: str
    progress: int = 0
    total: int = 0
    processed: int = 0
    failed: int = 0
    retry_count: int = 0
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list
    total: int

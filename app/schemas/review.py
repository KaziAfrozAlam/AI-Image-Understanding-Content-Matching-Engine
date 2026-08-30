"""Pydantic schemas for human reviews."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    reviewer: Optional[str] = "admin"
    notes: Optional[str] = None


class ReviewResponse(BaseModel):
    id: str
    suggestion_id: str
    decision: str
    reviewer: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

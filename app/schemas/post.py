"""Pydantic schemas for blog posts."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    category: Optional[str] = None


class PostResponse(BaseModel):
    id: str
    title: str
    content: str
    category: Optional[str] = None
    has_embedding: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PostListResponse(BaseModel):
    posts: list
    total: int

"""Pydantic schemas for evaluation results."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class EvaluationItem(BaseModel):
    post_id: str
    post_title: str
    expected_image_id: Optional[str] = None
    top_accepted_image_id: Optional[str] = None
    top_accepted_similarity: Optional[float] = None
    correct: bool
    decision: str


class EvaluationResult(BaseModel):
    total: int
    correct: int
    top1_precision: float
    items: List[EvaluationItem] = []
    created_at: Optional[str] = None

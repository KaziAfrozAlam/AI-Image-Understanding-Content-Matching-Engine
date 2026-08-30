"""Pydantic schemas for matching, suggestions and recommendations."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CandidateResult(BaseModel):
    image_id: str
    similarity: float
    decision: str  # ACCEPTED | REJECTED | FLAGGED_FOR_REVIEW
    confidence: Optional[float] = None
    reason: str
    suggestion_id: Optional[str] = None


class MatchResponse(BaseModel):
    post_id: str
    decision: str  # RECOMMENDED | NO_CONFIDENT_MATCH
    recommended_image_id: Optional[str] = None
    top_similarity: Optional[float] = None
    reason: str
    candidates: List[CandidateResult] = []


class SuggestionResponse(BaseModel):
    id: str
    post_id: str
    image_id: str
    similarity_score: Optional[float] = None
    guard_decision: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[str] = None

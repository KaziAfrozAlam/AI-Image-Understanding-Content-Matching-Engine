"""Review workflow routes."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.security import require_api_key
from app.repositories.match_repository import MatchRepository
from app.schemas.matching import SuggestionResponse
from app.schemas.review import ReviewCreate, ReviewResponse

router = APIRouter(tags=["reviews"])

SuggestionDecision = Literal["ACCEPTED", "REJECTED", "FLAGGED_FOR_REVIEW"]


@router.get("/suggestions", response_model=list[SuggestionResponse])
def list_suggestions(
    post_id: Optional[str] = Query(default=None),
    decision: Optional[SuggestionDecision] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List stored suggestions so the review UI can fetch ids to approve/reject."""
    repo = MatchRepository(db)
    suggestions = repo.list_suggestions(post_id=post_id, decision=decision)
    return [SuggestionResponse(**s.to_dict()) for s in suggestions[offset : offset + limit]]


@router.get("/suggestions/{suggestion_id}")
def get_suggestion_detail(suggestion_id: str, db: Session = Depends(get_db)):
    detail = MatchRepository(db).suggestion_detail(suggestion_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    suggestion, post, image = detail
    return {
        "suggestion": suggestion.to_dict(),
        "post": post.to_dict() if post else None,
        "image": image.to_dict() if image else None,
    }


@router.post("/suggestions/{suggestion_id}/approve", response_model=ReviewResponse, dependencies=[Depends(require_api_key)])
def approve_suggestion(
    suggestion_id: str,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
):
    repo = MatchRepository(db)
    suggestion = repo.get_suggestion(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    review = repo.create_review(
        suggestion_id, "APPROVED", payload.reviewer, payload.notes
    )
    return ReviewResponse(**review.to_dict())


@router.post("/suggestions/{suggestion_id}/reject", response_model=ReviewResponse, dependencies=[Depends(require_api_key)])
def reject_suggestion(
    suggestion_id: str,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
):
    repo = MatchRepository(db)
    suggestion = repo.get_suggestion(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    review = repo.create_review(
        suggestion_id, "REJECTED", payload.reviewer, payload.notes
    )
    return ReviewResponse(**review.to_dict())


@router.get("/reviews", response_model=list[ReviewResponse])
def list_reviews(
    suggestion_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    repo = MatchRepository(db)
    reviews = repo.list_reviews(suggestion_id=suggestion_id)
    return [ReviewResponse(**r.to_dict()) for r in reviews[offset : offset + limit]]

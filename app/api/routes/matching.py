"""Matching routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.post_repository import PostRepository
from app.schemas.matching import CandidateResult, MatchResponse
from app.services.matching_service import MatchingService

router = APIRouter(tags=["matching"])


@router.get("/posts/{post_id}/images", response_model=list[CandidateResult])
def list_candidate_images(post_id: str, db: Session = Depends(get_db)):
    post = PostRepository(db).get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    service = MatchingService(db)
    # Read-only: compute the ranking in memory without persisting suggestions
    # or lazily writing embeddings. Use a POST /match (or the review UI) to
    # materialise suggestions. Falls back to stored candidates when nothing
    # can be computed from the current corpus.
    return service.ranked_candidates(post_id)


@router.post("/posts/{post_id}/match", response_model=MatchResponse)
def match_post(post_id: str, db: Session = Depends(get_db)):
    post = PostRepository(db).get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    service = MatchingService(db)
    return service.rank(post_id, persist=True)

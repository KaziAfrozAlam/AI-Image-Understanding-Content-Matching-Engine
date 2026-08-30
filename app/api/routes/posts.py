"""Post routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.models.job import JobType
from app.repositories.job_repository import JobRepository
from app.repositories.post_repository import PostRepository
from app.schemas.post import PostCreate, PostListResponse, PostResponse

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, db: Session = Depends(get_db)):
    repo = PostRepository(db)
    post = repo.create(payload)
    # Enqueue embedding generation so the AI call does not block the request.
    JobRepository(db).create(JobType.POST_EMBEDDING.value)
    return PostResponse(
        id=post.id,
        title=post.title,
        content=post.content,
        category=post.category,
        has_embedding=repo.has_embedding(post.id),
        created_at=post.created_at.isoformat() if post.created_at else None,
        updated_at=post.updated_at.isoformat() if post.updated_at else None,
    )


@router.get("", response_model=PostListResponse)
def list_posts(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    repo = PostRepository(db)
    posts, total = repo.list(limit=limit, offset=offset)
    return PostListResponse(
        posts=[
            PostResponse(
                id=p.id,
                title=p.title,
                content=p.content,
                category=p.category,
                has_embedding=repo.has_embedding(p.id),
                created_at=p.created_at.isoformat() if p.created_at else None,
                updated_at=p.updated_at.isoformat() if p.updated_at else None,
            )
            for p in posts
        ],
        total=total,
    )


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: str, db: Session = Depends(get_db)):
    repo = PostRepository(db)
    post = repo.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return PostResponse(
        id=post.id,
        title=post.title,
        content=post.content,
        category=post.category,
        has_embedding=repo.has_embedding(post.id),
        created_at=post.created_at.isoformat() if post.created_at else None,
        updated_at=post.updated_at.isoformat() if post.updated_at else None,
    )

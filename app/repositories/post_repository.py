"""Post repository: all DB access for posts and their embeddings."""
from __future__ import annotations

from app.core.time import utcnow
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.post import Post
from app.db.models.post_embedding import PostEmbedding
from app.schemas.post import PostCreate


class PostRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: PostCreate) -> Post:
        post = Post(
            title=payload.title,
            content=payload.content,
            category=payload.category,
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        return post

    def get(self, post_id: str) -> Optional[Post]:
        return self.db.get(Post, post_id)

    def list(self, limit: int = 100, offset: int = 0) -> Tuple[List[Post], int]:
        total = self.db.execute(select(func.count()).select_from(Post)).scalar_one()
        rows = self.db.execute(
            select(Post).order_by(Post.created_at.desc()).limit(limit).offset(offset)
        ).scalars().all()
        return list(rows), total

    def get_embedding(self, post_id: str) -> Optional[List[float]]:
        row = self.db.execute(
            select(PostEmbedding).where(PostEmbedding.post_id == post_id)
        ).scalar_one_or_none()
        return list(row.embedding) if row else None

    def has_embedding(self, post_id: str) -> bool:
        return (
            self.db.execute(
                select(PostEmbedding.id).where(PostEmbedding.post_id == post_id)
            ).first()
            is not None
        )

    def save_embedding(self, post_id: str, embedding: List[float], model: str) -> None:
        existing = self.db.execute(
            select(PostEmbedding).where(PostEmbedding.post_id == post_id)
        ).scalar_one_or_none()
        if existing:
            existing.embedding = list(embedding)
            existing.model = model
            existing.created_at = utcnow()
        else:
            self.db.add(PostEmbedding(post_id=post_id, embedding=list(embedding), model=model))
        self.db.commit()

    def all(self) -> List[Post]:
        return list(self.db.execute(select(Post)).scalars().all())

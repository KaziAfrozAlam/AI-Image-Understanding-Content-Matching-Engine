"""Post embedding worker logic.

Generates and stores semantic embeddings for posts. Posts created via the API
are enqueued for embedding so the (potentially slow) AI call does not block the
HTTP request.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.job_repository import JobRepository
from app.repositories.post_repository import PostRepository
from app.services.embedding_service import BaseEmbeddingService, get_embedding_service

logger = get_logger("worker.embedding")


def run_post_embedding_job(
    db: Session,
    job,
    embedding: Optional[BaseEmbeddingService] = None,
    post_ids: Optional[list] = None,
) -> None:
    job_repo = JobRepository(db)
    post_repo = PostRepository(db)
    embedding = embedding or get_embedding_service(db)

    posts = post_repo.all()
    if post_ids:
        wanted = set(post_ids)
        posts = [p for p in posts if p.id in wanted]
    posts = [p for p in posts if not post_repo.has_embedding(p.id)]

    job_repo.mark_running(job, total=len(posts))
    processed = 0
    failed = 0
    for post in posts:
        try:
            text = f"{post.title}. {post.content}"
            vector = embedding.embed(text)
            post_repo.save_embedding(post.id, vector, embedding.model)
            processed += 1
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed embedding post %s: %s", post.id, exc)
            failed += 1
        job_repo.update_progress(job, processed, failed)

    job_repo.mark_completed(job, failed=failed)
    logger.info("Post embedding job %s done: %d ok, %d failed", job.id, processed, failed)

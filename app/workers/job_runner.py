"""Job runner.

Dispatches queued jobs to the appropriate worker. Runs as:
  * a background thread inside the API process (so the system works in a single
    container), AND
  * a standalone worker process via ``python -m app.workers.job_runner``.

The worker is intentionally simple: poll for QUEUED jobs, process one at a time.
"""
from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.db.models.job import JobType
from app.repositories.job_repository import JobRepository
from app.workers.embedding_processing import run_post_embedding_job
from app.workers.image_processing import run_image_job

logger = get_logger("worker.runner")


def process_job(db: Session, job, vision=None, embedding=None) -> None:
    try:
        if job.type == JobType.IMAGE_PROCESSING.value:
            run_image_job(db, job, vision=vision, embedding=embedding)
        elif job.type == JobType.POST_EMBEDDING.value:
            run_post_embedding_job(db, job, embedding=embedding)
        else:
            from app.repositories.job_repository import JobRepository

            JobRepository(db).mark_failed(job, f"Unknown job type: {job.type}")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Job %s failed: %s", getattr(job, "id", "?"), exc)
        try:
            from app.repositories.job_repository import JobRepository

            JobRepository(db).mark_failed(job, str(exc)[:2000])
        except Exception:
            pass


def run_once() -> bool:
    db = SessionLocal()
    try:
        repo = JobRepository(db)
        queued = repo.get_queued(limit=1)
        if not queued:
            return False
        job = queued[0]
        process_job(db, job)
        return True
    finally:
        db.close()


def run_forever(poll_interval: float = 2.0) -> None:
    logger.info("Worker started (poll interval %.1fs)", poll_interval)
    while True:
        try:
            ran = run_once()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Worker poll error: %s", exc)
            ran = False
        if not ran:
            time.sleep(poll_interval)


def start_background_worker(poll_interval: float = 3.0) -> None:
    """Start the worker loop in a daemon thread (used by the API process)."""
    import threading

    def _loop():
        while True:
            try:
                run_once()
            except Exception:  # pragma: no cover - defensive
                pass
            time.sleep(poll_interval)

    t = threading.Thread(target=_loop, name="bg-worker", daemon=True)
    t.start()
    logger.info("Background worker thread started")
    return None


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Image matching background worker")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Process all currently queued jobs and exit (useful in CI/tests).",
    )
    args = parser.parse_args()
    if args.run_once:
        while run_once():
            pass
        logger.info("Processed all queued jobs; exiting.")
    else:
        run_forever()


if __name__ == "__main__":
    _main()

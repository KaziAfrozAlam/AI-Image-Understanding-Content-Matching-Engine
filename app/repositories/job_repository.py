"""Job repository."""
from __future__ import annotations

from app.core.time import utcnow
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.job import Job, JobStatus


class JobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, job_type: str) -> Job:
        job = Job(type=job_type, status=JobStatus.QUEUED.value, total=0)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self.db.get(Job, job_id)

    def list(self, limit: int = 100, offset: int = 0) -> Tuple[List[Job], int]:
        total = self.db.execute(
            select(func.count()).select_from(Job)
        ).scalar_one()
        rows = self.db.execute(
            select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
        ).scalars().all()
        return list(rows), total

    def get_queued(self, limit: int = 5) -> List[Job]:
        return list(
            self.db.execute(
                select(Job).where(Job.status == JobStatus.QUEUED.value)
            ).scalars().all()
        )

    def mark_running(self, job: Job, total: int) -> None:
        job.status = JobStatus.RUNNING.value
        job.total = total
        job.started_at = utcnow()
        self.db.commit()

    def update_progress(self, job: Job, processed: int, failed: int) -> None:
        job.processed = processed
        job.failed = failed
        job.progress = processed + failed
        self.db.commit()

    def mark_completed(self, job: Job, failed: int = 0) -> None:
        job.status = JobStatus.COMPLETED.value if failed == 0 else JobStatus.PARTIAL.value
        job.progress = job.total
        job.processed = job.total - failed
        job.failed = failed
        job.completed_at = utcnow()
        self.db.commit()

    def mark_failed(self, job: Job, error: str) -> None:
        job.status = JobStatus.FAILED.value
        job.error = error[:2000]
        job.completed_at = utcnow()
        self.db.commit()

    def increment_retry(self, job: Job) -> None:
        job.retry_count += 1
        self.db.commit()

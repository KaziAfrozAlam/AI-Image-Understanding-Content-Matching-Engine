"""Job and cost/usage routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.db.models.job import JobType
from app.repositories.ai_usage_repository import AiUsageRepository
from app.repositories.job_repository import JobRepository
from app.services.cost_tracking_service import CostTrackingService
from app.schemas.job import JobListResponse, JobResponse

router = APIRouter(tags=["jobs"])


@router.post("/jobs/images/process", response_model=JobResponse, status_code=202)
def process_images(db: Session = Depends(get_db)):
    job = JobRepository(db).create(JobType.IMAGE_PROCESSING.value)
    return JobResponse(**job.to_dict())


@router.post("/jobs/posts/process", response_model=JobResponse, status_code=202)
def process_post_embeddings(db: Session = Depends(get_db)):
    job = JobRepository(db).create(JobType.POST_EMBEDDING.value)
    return JobResponse(**job.to_dict())


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    jobs, total = JobRepository(db).list(limit=limit, offset=offset)
    return JobListResponse(
        jobs=[JobResponse(**j.to_dict()) for j in jobs], total=total
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = JobRepository(db).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job.to_dict())


@router.get("/usage")
def usage(db: Session = Depends(get_db)):
    repo = AiUsageRepository(db)
    calls = repo.list(limit=500)
    by_operation = {}
    for c in calls:
        by_operation.setdefault(c.operation, {"calls": 0, "estimated_cost": 0.0})
        by_operation[c.operation]["calls"] += 1
        by_operation[c.operation]["estimated_cost"] += c.estimated_cost
    return {
        "total_calls": repo.total_calls(),
        "total_estimated_cost": repo.total_cost(),
        "currency": "USD",
        "budget_usd": settings.budget_usd,
        "over_budget": CostTrackingService(db).is_over_budget(),
        "note": "Estimated cost is 0 in the free/local tier; actual paid cost "
        "would be tracked identically when a real provider key is configured.",
        "by_operation": by_operation,
        "model_vision": settings.vision_model if settings.use_real_ai else "local-vision-sim",
        "model_embedding": settings.embedding_model if settings.use_real_ai else "local-concept-embed",
        "records": [c.to_dict() for c in calls[:100]],
    }

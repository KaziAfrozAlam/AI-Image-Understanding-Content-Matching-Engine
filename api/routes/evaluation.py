"""Evaluation routes."""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import settings
from app.core.security import require_api_key
from app.schemas.evaluation import EvaluationResult
from app.services.evaluation_service import EvaluationService

router = APIRouter(tags=["evaluation"])


@router.post("/evaluation/run", response_model=EvaluationResult, dependencies=[Depends(require_api_key)])
def run_evaluation(db: Session = Depends(get_db)):
    service = EvaluationService(db)
    result = service.run(persist=True)
    # Persist the latest result so GET /evaluation/latest is reproducible.
    out_path = settings.eval_labels_file + ".result.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result.model_dump(), fh, indent=2)
    return result


@router.get("/evaluation/latest", response_model=EvaluationResult)
def latest_evaluation(db: Session = Depends(get_db)):
    service = EvaluationService(db)
    result = service.latest()
    if result is None:
        raise HTTPException(status_code=404, detail="No evaluation has been run yet.")
    return result

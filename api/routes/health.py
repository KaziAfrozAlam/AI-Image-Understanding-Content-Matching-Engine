"""Health route."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "use_real_ai": settings.use_real_ai,
        "vision_model": settings.vision_model if settings.use_real_ai else "local-vision-sim",
        "embedding_model": settings.embedding_model if settings.use_real_ai else "local-concept-embed",
        "similarity_threshold": settings.similarity_threshold,
        "confidence_threshold": settings.confidence_threshold,
    }

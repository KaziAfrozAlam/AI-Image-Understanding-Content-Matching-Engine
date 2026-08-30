"""FastAPI application entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import (
    evaluation,
    health,
    images,
    jobs,
    matching,
    posts,
    reviews,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import engine
from app.db.models import Base
from app.db.models import ai_usage, image, image_embedding, job, post, post_embedding, review, suggestion

logger = get_logger("main")


def _ensure_schema() -> None:
    """Apply schema migrations.

    On a brand-new (empty) database, apply the versioned Alembic migration so
    the schema is created from a reviewable definition. On any existing
    database we never risk re-running migrations against a live/partially
    populated schema: we only ensure the required tables exist via
    ``create_all`` (idempotent). This keeps startup safe on every environment.
    """
    import os

    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    if existing_tables:
        # Already-initialised database: just make sure all model tables exist.
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ensured (existing schema; create_all).")
        return

    from alembic import command
    from alembic.config import Config

    # alembic.ini lives at the project root; it already declares
    # script_location = app/db/migrations.
    alembic_ini = Path(__file__).parent.parent.parent / "alembic.ini"
    script_location = Path(__file__).parent / "db" / "migrations"
    try:
        if alembic_ini.exists() and script_location.exists():
            cfg = Config(str(alembic_ini))
            cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL") or settings.database_url)
            command.upgrade(cfg, "head")
            logger.info("Database migrations applied (alembic upgrade head).")
            return
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Alembic migration failed (%s); falling back to create_all.", exc)

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured (create_all fallback).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_schema()

    worker_enabled = os.getenv("WORKER_ENABLED", "1").lower() not in {"0", "false", "no"}
    if worker_enabled:
        from app.workers.job_runner import start_background_worker

        start_background_worker(poll_interval=3.0)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Image Understanding & Content Matching Engine",
        version="1.0.0",
        description="A trustworthy AI decision system that recommends images for "
        "blog posts and explicitly rejects uncertain or incorrect matches.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (health, images, posts, matching, reviews, jobs, evaluation):
        app.include_router(module.router)

    # Static web UI (single-page frontend served by the API itself).
    static_dir = Path(__file__).parent / "static"

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()


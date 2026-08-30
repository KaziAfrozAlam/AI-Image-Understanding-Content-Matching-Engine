"""Pytest configuration and shared fixtures.

Uses a dedicated SQLite database so ``pytest`` works on a clean machine with no
Postgres running (the production stack still uses Postgres via Docker).
"""
from __future__ import annotations

import os
import tempfile

# Configure environment BEFORE importing the application.
_TEST_DB = os.path.join(tempfile.gettempdir(), "capstone_test.db")
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["WORKER_ENABLED"] = "0"
os.environ["DATA_DIR"] = tempfile.gettempdir()
os.environ["IMAGES_DIR"] = os.path.join(tempfile.gettempdir(), "images")
os.environ["LABELS_FILE"] = os.path.join(tempfile.gettempdir(), "labels.json")
os.environ["EVAL_LABELS_FILE"] = os.path.join(tempfile.gettempdir(), "eval_labels.json")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, engine  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.models.image import Image, ImageStatus  # noqa: E402
from app.db.models.image_embedding import ImageEmbedding  # noqa: E402
from app.db.models.post import Post  # noqa: E402
from app.db.models.post_embedding import PostEmbedding  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories.image_repository import ImageRepository  # noqa: E402
from app.repositories.post_repository import PostRepository  # noqa: E402
from app.services.embedding_service import get_embedding_service  # noqa: E402

settings.eval_labels_file = os.environ["EVAL_LABELS_FILE"]


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[__import__("app.api.dependencies", fromlist=["get_db"]).get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _embed(db, text):
    return get_embedding_service(db).embed(text)


@pytest.fixture()
def make_image(db_session):
    repo = ImageRepository(db_session)

    def _factory(
        subject,
        category="animal",
        confidence=0.95,
        attributes=None,
        caption=None,
        status=ImageStatus.COMPLETED.value,
        filename=None,
    ):
        from app.schemas.image import ImageCreate

        filename = filename or f"{subject}_{abs(hash(subject)) % 1000:03d}.jpg"
        image = repo.create(ImageCreate(filename=filename))
        image.subject = subject
        image.category = category
        image.attributes = attributes or [subject]
        image.caption = caption or f"An image of a {subject}."
        image.confidence = confidence
        image.processing_status = status
        db_session.commit()
        text = f"{image.caption} {' '.join(image.attributes)}"
        repo.save_embedding(image.id, _embed(db_session, text), "test-embed")
        return image

    return _factory


@pytest.fixture()
def make_post(db_session):
    repo = PostRepository(db_session)

    def _factory(title, content, category=None):
        from app.schemas.post import PostCreate

        post = repo.create(PostCreate(title=title, content=content, category=category))
        text = f"{title}. {content}"
        repo.save_embedding(post.id, _embed(db_session, text), "test-embed")
        return post

    return _factory

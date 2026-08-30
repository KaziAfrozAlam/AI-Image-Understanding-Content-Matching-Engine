"""Application configuration loaded from environment variables.

All secrets come exclusively from the environment. Nothing is hardcoded.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Settings:
    """Centralised application settings."""

    def __init__(self) -> None:
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        self.database_url: str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@db:5432/image_matching",
        )

        # AI provider configuration. The system runs without a key by using a
        # deterministic local model so it stays $0 / freely reproducible.
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY") or None
        self.vision_model: str = os.getenv("VISION_MODEL", "gemini-1.5-flash")
        self.embedding_model: str = os.getenv(
            "EMBEDDING_MODEL", "models/text-embedding-004"
        )
        self.use_real_ai: bool = bool(self.gemini_api_key)

        # Safety thresholds
        self.similarity_threshold: float = _get_float("SIMILARITY_THRESHOLD", 0.75)
        self.confidence_threshold: float = _get_float("CONFIDENCE_THRESHOLD", 0.70)
        # A higher bar is required to fully ACCEPT; otherwise the item is
        # flagged for human review.
        self.accept_confidence: float = _get_float("ACCEPT_CONFIDENCE", 0.80)

        self.max_retries: int = _get_int("MAX_RETRIES", 3)
        self.embedding_dim: int = _get_int("EMBEDDING_DIM", 64)

        # Cost budget guard (shared requirement #7): every AI call is cost
        # tracked; if cumulative estimated spend exceeds this budget the guard
        # alerts (and, when strict, refuses further calls).
        self.budget_usd: float = _get_float("BUDGET_USD", 1.0)
        self.budget_guard_strict: bool = _get_bool("BUDGET_GUARD_STRICT", False)

        # Local data paths (used by seed / local vision fallback)
        self.data_dir: str = os.getenv("DATA_DIR", "data")
        self.images_dir: str = os.getenv("IMAGES_DIR", "data/images")
        self.labels_file: str = os.getenv("LABELS_FILE", "data/labels.json")
        self.eval_labels_file: str = os.getenv(
            "EVAL_LABELS_FILE", "data/eval_labels.json"
        )

        self.api_v1_prefix: str = "/api/v1"

        # CORS. Defaults to allowing any origin in development so the bundled
        # static UI and local tooling work with zero config. Restrict this in
        # production via CORS_ORIGINS (comma-separated).
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "*").split(",")
            if o.strip()
        ]

    @property
    def database_echo(self) -> bool:
        return self.app_env == "development" and _get_bool("DB_ECHO", False)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

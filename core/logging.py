"""Logging configuration.

API keys and secrets must never be logged. We attach a filter that redacts
anything that looks like a secret before it reaches a handler.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.core.config import get_settings

_settings = get_settings()

_SECRET_RE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{6,}",
)


class _RedactSecrets(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, dict):
            record.args = {
                k: ("***REDACTED***" if self._is_secret(k) else v)
                for k, v in record.args.items()
            }
        elif record.args:
            try:
                msg = str(record.msg) % record.args
            except Exception:
                msg = str(record.msg)
            record.msg = _SECRET_RE.sub(r"\1=***REDACTED***", msg)
            record.args = ()
        else:
            record.msg = _SECRET_RE.sub(r"\1=***REDACTED***", str(record.msg))
        return True

    @staticmethod
    def _is_secret(key: str) -> bool:
        return bool(re.search(r"(?i)(key|token|secret|password|auth)", key))


def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name or "image_matching")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(_RedactSecrets())
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, _settings.log_level.upper(), logging.INFO))
        logger.propagate = False
    return logger

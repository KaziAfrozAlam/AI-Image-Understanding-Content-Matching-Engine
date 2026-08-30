"""Security helpers.

The system exposes no authentication by default (this is a backend capstone),
but we centralise the few safety-related helpers here so they are easy to
extend later (e.g. API key validation for external callers).
"""
from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException, status


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Optional guard for administrative endpoints.

    Only enforced when ``ADMIN_API_KEY`` is configured. This keeps the project
    $0 and open by default while showing where a real boundary would live.
    """
    configured = os.getenv("ADMIN_API_KEY")
    if not configured:
        return
    if not x_api_key or not constant_time_compare(x_api_key, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )

"""Time helpers.

All timestamps are stored as **naive UTC** datetimes. The database columns are
plain (non-timezone-aware) ``DateTime`` for SQLite/Postgres portability, so we
deliberately keep values naive-but-UTC to stay consistent with the columns and
the serialised ISO output. We use a single helper here both to avoid the
deprecated ``datetime.utcnow()`` and to keep every write in one place.

If a deployment ever needs true timezone-aware columns, migrate the relevant
columns to ``DateTime(timezone=True)`` and change ``utcnow`` to return an aware
value in lock-step.
"""
from __future__ import annotations

import datetime as _dt


def utcnow() -> _dt.datetime:
    """Return the current UTC time as a naive datetime."""
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)

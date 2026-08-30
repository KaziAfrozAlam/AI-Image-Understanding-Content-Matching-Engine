"""Standalone evaluation script (PROBE 5).

Computes Top-1 Precision over the labeled evaluation set and prints the result.
This is the number that should match the value reported in README.md.

Run (after seeding):
    python scripts/evaluate.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.services.evaluation_service import EvaluationService  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        result = EvaluationService(db).run(persist=True)
    finally:
        db.close()

    print("Top-1 Precision: {}".format(result.top1_precision))
    print("Correct:        {} / {}".format(result.correct, result.total))
    print("Created at:     {}".format(result.created_at))
    print("Sample items:")
    for item in result.items[:5]:
        print(
            "  - {:40s} expected={} top={} correct={}".format(
                item.post_title[:40],
                item.expected_image_id,
                item.top_accepted_image_id,
                item.correct,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

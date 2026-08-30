"""Test 2 - Low confidence must be flagged (never silently accepted)."""
from __future__ import annotations

from app.services.mismatch_guard import DECISION_FLAG, evaluate
from app.services.matching_service import MatchingService


def test_guard_flags_low_confidence():
    result = evaluate(
        post_title="The Behavior of Red Foxes",
        post_content="Red foxes are wild animals.",
        image_subject="fox",
        image_category="animal",
        image_attributes=["orange fur", "wild"],
        image_caption="A red fox in a forest.",
        image_confidence=0.45,
        similarity=0.95,
        similarity_threshold=0.75,
        confidence_threshold=0.70,
        accept_confidence=0.80,
    )
    assert result.decision == DECISION_FLAG
    assert "confidence" in result.reason.lower()


def test_low_confidence_image_flagged_in_matching(db_session, make_post, make_image):
    post = make_post("The Behavior of Red Foxes", "Red foxes are wild animals with orange fur.")
    # Subject-compatible but untrustworthy confidence.
    img = make_image("fox", confidence=0.50)
    service = MatchingService(db_session)
    response = service.rank(post.id, persist=True)
    fox_candidate = next(c for c in response.candidates if c.image_id == img.id)
    assert fox_candidate.decision == "FLAGGED_FOR_REVIEW"

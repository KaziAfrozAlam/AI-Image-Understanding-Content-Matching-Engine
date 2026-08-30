"""Test 5 - No confident match.

A post with no suitable image must return NO_CONFIDENT_MATCH and never force a
recommendation.
"""
from __future__ import annotations

from app.services.matching_service import MatchingService


def test_no_confident_match(db_session, make_post, make_image):
    post = make_post(
        "The History of Renaissance Painting in Florence",
        "Renaissance painting flourished in Florence during the 15th century. "
        "This article discusses art, frescoes, and classical sculpture.",
    )
    # Only animal/environment images exist in the corpus.
    make_image("fox", confidence=0.95)
    make_image("wolf", confidence=0.95)
    make_image("deer", confidence=0.95)

    service = MatchingService(db_session)
    response = service.rank(post.id, persist=True)

    assert response.decision == "NO_CONFIDENT_MATCH"
    assert response.recommended_image_id is None
    assert "similarity" in response.reason.lower() or "subject" in response.reason.lower()
    accepted = [c for c in response.candidates if c.decision == "ACCEPTED"]
    assert accepted == []

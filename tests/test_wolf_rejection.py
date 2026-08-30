"""Test 4 - Wolf rejection: force a wolf candidate for a fox article.

Expected: REJECTED with a meaningful explanation, even though the wolf is
semantically close to a fox.
"""
from __future__ import annotations

from app.services.matching_service import MatchingService


def test_wolf_candidate_rejected_for_fox_article(db_session, make_post, make_image):
    post = make_post(
        "The Behavior of Red Foxes",
        "Red foxes are wild animals with orange fur found in forests.",
    )
    wolf = make_image("wolf", confidence=0.95)
    # sanity: ensure the wolf really is a close semantic neighbour of the fox post
    service = MatchingService(db_session)
    response = service.rank(post.id, persist=True)

    wolf_candidate = next(c for c in response.candidates if c.image_id == wolf.id)
    assert wolf_candidate.decision == "REJECTED"
    assert "wolf" in wolf_candidate.reason.lower()
    assert "mismatch" in wolf_candidate.reason.lower()
    # The rejected wolf must NOT be recommended.
    assert response.recommended_image_id != wolf.id

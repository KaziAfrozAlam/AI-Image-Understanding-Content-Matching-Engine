"""Test 3 - Semantic matching: a fox article should rank the fox image first."""
from __future__ import annotations

from app.services.matching_service import MatchingService


def test_fox_article_ranks_fox_image_first(db_session, make_post, make_image):
    post = make_post(
        "The Behavior of Red Foxes",
        "Red foxes are adaptable wild animals. Vulpes vulpes is a small predator.",
    )
    fox = make_image("fox", confidence=0.95)
    wolf = make_image("wolf", confidence=0.95)
    dog = make_image("dog", confidence=0.95)

    service = MatchingService(db_session)
    response = service.rank(post.id, persist=True)

    assert response.decision == "RECOMMENDED"
    assert response.recommended_image_id == fox.id
    accepted = [c for c in response.candidates if c.decision == "ACCEPTED"]
    assert accepted
    assert accepted[0].image_id == fox.id

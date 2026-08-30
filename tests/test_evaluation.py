"""Test 9 - Top-1 evaluation produces a real, measured precision value."""
from __future__ import annotations

import json

from app.core.config import settings
from app.services.evaluation_service import EvaluationService


def test_top1_precision_measured(db_session, make_post, make_image):
    fox_post = make_post(
        "The Behavior of Red Foxes",
        "Red foxes are wild animals with orange fur found in forests.",
    )
    fox_img = make_image("fox", confidence=0.95)

    synonym_post = make_post(
        "Vulpes vulpes: The Red Fox Explained",
        "Vulpes vulpes, commonly called the red fox, is a wild canine.",
    )
    wolf_post = make_post(
        "Gray Wolves of the Northern Forest",
        "The gray wolf is a wild canine that hunts in forests.",
    )
    wolf_img = make_image("wolf", confidence=0.95)

    no_match_post = make_post(
        "The History of Renaissance Painting in Florence",
        "Renaissance painting flourished in Florence during the 15th century.",
    )

    labels = [
        {"post_id": fox_post.id, "post_title": fox_post.title, "expected_image_id": fox_img.id},
        {"post_id": synonym_post.id, "post_title": synonym_post.title, "expected_image_id": fox_img.id},
        {"post_id": wolf_post.id, "post_title": wolf_post.title, "expected_image_id": wolf_img.id},
        {"post_id": no_match_post.id, "post_title": no_match_post.title, "expected_image_id": None},
    ]
    with open(settings.eval_labels_file, "w", encoding="utf-8") as fh:
        json.dump(labels, fh)

    result = EvaluationService(db_session).run(persist=True)

    assert isinstance(result.top1_precision, float)
    assert 0.0 <= result.top1_precision <= 1.0
    assert result.total == 4
    assert result.correct == 4
    assert result.top1_precision == 1.0

    # The synonym post must match the fox image (true semantic equivalence).
    synonym_item = next(i for i in result.items if i.post_id == synonym_post.id)
    assert synonym_item.top_accepted_image_id == fox_img.id
    assert synonym_item.correct is True

    # The no-match post must yield NO_CONFIDENT_MATCH and count as correct.
    no_match_item = next(i for i in result.items if i.post_id == no_match_post.id)
    assert no_match_item.decision == "NO_CONFIDENT_MATCH"
    assert no_match_item.correct is True

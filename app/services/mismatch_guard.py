"""Mismatch guard.

This is the trust layer of the whole system. It is a standalone, deterministic,
independently-testable module that decides whether a candidate image may be
recommended for a post.

Decision logic (in order):

    1. Subject / category compatibility  (structured semantic check)
         - incompatible  -> REJECT with an explicit mismatch reason,
                            EVEN if similarity is high. A wolf is semantically
                            close to a fox, but it is the wrong subject.
    2. Vision confidence
         - too low       -> FLAG_FOR_REVIEW (never silently accept)
    3. Semantic similarity
         - below threshold -> REJECT

The guard never blindly selects the highest-similarity candidate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.services import concepts


DECISION_ACCEPT = "ACCEPT"
DECISION_REJECT = "REJECT"
DECISION_FLAG = "FLAG_FOR_REVIEW"


@dataclass
class GuardResult:
    decision: str
    reason: str
    expected_subject: Optional[str]
    detected_subject: Optional[str]
    similarity: float
    confidence: float


def _animal_subjects(text: str) -> List[str]:
    return concepts._animal_subjects(text)


def _categories(text: str) -> List[str]:
    return [m.category for m in concepts.classify_concepts(text)]


def evaluate(
    *,
    post_title: str,
    post_content: str,
    image_subject: str,
    image_category: str,
    image_attributes: Optional[List[str]],
    image_caption: str,
    image_confidence: float,
    similarity: float,
    similarity_threshold: float,
    confidence_threshold: float,
    accept_confidence: float,
) -> GuardResult:
    post_text = f"{post_title} {post_content}"
    image_text = f"{image_subject} {image_caption} {' '.join(image_attributes or [])}"

    # Compatibility is judged on the post's PRIMARY animal subject (the topic).
    # A post may mention several animals (e.g. "fox ... canine"), but the
    # candidate must contain the *primary* one to be considered compatible.
    # Environment context such as "forest" must not make a wolf compatible
    # with a fox post.
    post_animals = _animal_subjects(post_text)
    image_animals = _animal_subjects(image_text)
    post_primary = concepts.primary_subject(post_text)

    if post_animals:
        compatible = post_primary in image_animals
    else:
        # No animal topic (e.g. an environment or art post): rely on similarity.
        compatible = True

    if not compatible:
        expected = post_primary or (post_title.strip() or "unknown")
        detected = image_animals[0] if image_animals else (image_subject or "unknown")
        post_cats = set(_categories(post_text))
        image_cats = set(_categories(image_text)) | {image_category}
        if post_cats & image_cats:
            reason = (
                f"Animal category/subject mismatch: expected {expected}, "
                f"detected {detected}."
            )
        else:
            reason = (
                f"Category mismatch: expected {expected}, detected {detected} "
                f"({image_category})."
            )
        return GuardResult(
            decision=DECISION_REJECT,
            reason=reason,
            expected_subject=expected,
            detected_subject=detected,
            similarity=similarity,
            confidence=image_confidence,
        )

    # Subject is compatible; now judge confidence.
    if image_confidence < confidence_threshold:
        return GuardResult(
            decision=DECISION_FLAG,
            reason=(
                f"Low vision confidence ({image_confidence:.2f}) below threshold "
                f"{confidence_threshold:.2f}; flagged for human review."
            ),
            expected_subject=post_primary if post_animals else None,
            detected_subject=image_animals[0] if image_animals else image_subject,
            similarity=similarity,
            confidence=image_confidence,
        )

    if image_confidence < accept_confidence:
        return GuardResult(
            decision=DECISION_FLAG,
            reason=(
                f"Borderline vision confidence ({image_confidence:.2f}); "
                f"flagged for human review."
            ),
            expected_subject=post_primary if post_animals else None,
            detected_subject=image_animals[0] if image_animals else image_subject,
            similarity=similarity,
            confidence=image_confidence,
        )

    # Subject compatible and confident; require semantic similarity.
    if similarity < similarity_threshold:
        return GuardResult(
            decision=DECISION_REJECT,
            reason=(
                f"Low semantic similarity ({similarity:.2f}) below required "
                f"threshold ({similarity_threshold:.2f})."
            ),
            expected_subject=post_primary if post_animals else None,
            detected_subject=image_animals[0] if image_animals else image_subject,
            similarity=similarity,
            confidence=image_confidence,
        )

    return GuardResult(
        decision=DECISION_ACCEPT,
        reason="Strong semantic similarity and matching subject/category, with sufficient confidence.",
        expected_subject=post_primary if post_animals else None,
        detected_subject=image_animals[0] if image_animals else image_subject,
        similarity=similarity,
        confidence=image_confidence,
    )

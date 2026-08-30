"""Deterministic domain-concept model.

This module is the single source of truth for how free text is turned into a
vector and how subjects/categories are detected. Both the local embedding
service and the mismatch guard rely on it, which keeps behaviour consistent
and fully reproducible on a clean machine with **no API key** (the project's
$0 requirement).

The vector space is hierarchical:

    [category dims] + [group dims] + [specific-concept dims]

Related concepts (e.g. ``fox`` and ``wolf``) share a category (``animal``) and a
group (``canid``), so their cosine similarity is *high* even though their
specific subject differs. That is exactly the situation the mismatch guard is
designed to catch: a wolf is semantically close to a fox, but it is the wrong
subject and must be rejected.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# concept key -> definition
# category: top-level bucket, group: finer taxonomic/semantic cluster
_CONCEPTS: Dict[str, Dict[str, object]] = {
    # ---- animal subjects (groups) ----
    "fox": {"category": "animal", "group": "canid", "synonyms": [
        "fox", "foxes", "red fox", "arctic fox", "fennec", "vulpes", "vulpes vulpes"]},
    "wolf": {"category": "animal", "group": "canid", "synonyms": [
        "wolf", "wolves", "gray wolf", "grey wolf", "timber wolf", "canis lupus"]},
    "dog": {"category": "animal", "group": "canid", "synonyms": [
        "dog", "dogs", "puppy", "canine", "husky", "labrador", "retriever", "poodle"]},
    "bear": {"category": "animal", "group": "ursine", "synonyms": [
        "bear", "bears", "grizzly", "polar bear", "black bear", "panda"]},
    "deer": {"category": "animal", "group": "cervid", "synonyms": [
        "deer", "fawn", "elk", "reindeer", "moose", "stag", "buck"]},
    "cat": {"category": "animal", "group": "feline", "synonyms": [
        "cat", "cats", "kitten", "feline", "tiger", "lion", "leopard"]},
    "bird": {"category": "animal", "group": "avian", "synonyms": [
        "bird", "birds", "eagle", "owl", "sparrow", "robin", "hawk", "penguin"]},
    "fish": {"category": "animal", "group": "aquatic", "synonyms": [
        "fish", "salmon", "trout", "shark", "tuna", "goldfish"]},
    # ---- environment / attribute concepts ----
    "forest": {"category": "environment", "group": "land", "synonyms": [
        "forest", "woods", "woodland", "jungle", "pine", "tree", "trees"]},
    "ocean": {"category": "environment", "group": "water", "synonyms": [
        "ocean", "sea", "beach", "shore", "coast", "coastal"]},
    "mountain": {"category": "environment", "group": "land", "synonyms": [
        "mountain", "mountains", "peak", "hill", "alps", "rocky"]},
    "snow": {"category": "environment", "group": "weather", "synonyms": [
        "snow", "snowy", "ice", "frozen", "winter"]},
    "domestic": {"category": "nature", "group": "state", "synonyms": [
        "domestic", "pet", "home", "indoor", "tame", "house"]},
    "wild": {"category": "nature", "group": "state", "synonyms": [
        "wild", "feral", "wilderness", "nature"]},
}

# Weighting: shared category/group dominate so related items score high;
# the specific concept is a smaller nudge so subjects stay distinguishable.
_CATEGORY_WEIGHT = 1.0
_GROUP_WEIGHT = 1.0
_ANIMAL_CONCEPT_WEIGHT = 0.6
_ENV_CONCEPT_WEIGHT = 0.3
_ATTR_WEIGHT = 0.15

# Build a stable, ordered dimension list.
_CATEGORIES = sorted({c["category"] for c in _CONCEPTS.values()})  # type: ignore
_GROUPS = sorted({c["group"] for c in _CONCEPTS.values()})  # type: ignore
_CONCEPT_KEYS = sorted(_CONCEPTS.keys())

# Ordered dimension names
_DIMENSIONS: List[str] = (
    [f"cat:{c}" for c in _CATEGORIES]
    + [f"grp:{g}" for g in _GROUPS]
    + [f"con:{k}" for k in _CONCEPT_KEYS]
)

_DIM_INDEX = {name: i for i, name in enumerate(_DIMENSIONS)}
_DIM_SIZE = len(_DIMENSIONS)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\s+[a-z0-9]+)?")


def _synonym_match(lowered: str, synonym: str) -> bool:
    """Match ``synonym`` as a whole word / phrase only.

    A raw substring test would wrongly match short synonyms inside unrelated
    words (e.g. ``cat`` inside ``category``, ``catering`` or ``classification``),
    corrupting subject detection. Requiring word boundaries keeps detection
    exact and reproducible.
    """
    return (
        re.search(r"(?<![a-z0-9])" + re.escape(synonym) + r"(?![a-z0-9])", lowered)
        is not None
    )


@dataclass
class ConceptMatch:
    key: str
    category: str
    group: str
    is_subject: bool


def _match_concepts(text: str) -> List[ConceptMatch]:
    lowered = f" {text.lower()} "
    matches: List[ConceptMatch] = []
    for key, definition in _CONCEPTS.items():
        for syn in definition["synonyms"]:  # type: ignore
            if _synonym_match(lowered, syn):
                matches.append(
                    ConceptMatch(
                        key=key,
                        category=definition["category"],  # type: ignore
                        group=definition["group"],  # type: ignore
                        # Primary image subjects are animals and environments;
                        # pure attributes (wild/domestic/...) stay one-dimensional
                        # so they do not dilute subject-level similarity.
                        is_subject=definition["category"] in ("animal", "environment"),
                    )
                )
                break
    return matches


def embed_text(text: str, dim: int = 64) -> List[float]:
    """Return a deterministic, normalised dense vector for ``text``.

    The vector length is padded/truncated to ``dim`` so callers can request a
    fixed size. Semantic relationships inside the domain are preserved.
    """
    vec = [0.0] * _DIM_SIZE
    matches = _match_concepts(text)
    for m in matches:
        if m.category == "animal":
            # Animal subjects dominate so a correct subject match stays highly
            # similar even when the post text is verbose.
            vec[_DIM_INDEX[f"con:{m.key}"]] += _ANIMAL_CONCEPT_WEIGHT
            vec[_DIM_INDEX[f"cat:{m.category}"]] += _CATEGORY_WEIGHT
            vec[_DIM_INDEX[f"grp:{m.group}"]] += _GROUP_WEIGHT
        elif m.category == "environment":
            # Environment subjects are lighter so they don't dilute the animal
            # signal, but still allow environment<->environment matches.
            vec[_DIM_INDEX[f"con:{m.key}"]] += _ENV_CONCEPT_WEIGHT
            vec[_DIM_INDEX[f"cat:{m.category}"]] += _CATEGORY_WEIGHT * 0.2
            vec[_DIM_INDEX[f"grp:{m.group}"]] += _GROUP_WEIGHT * 0.2
        else:
            # Pure attributes (wild / domestic / ...) stay one-dimensional.
            vec[_DIM_INDEX[f"con:{m.key}"]] += _ATTR_WEIGHT

    # Normalise
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]

    # Expand / truncate to the requested dimensionality. Padding is zero so the
    # semantic signal lives entirely in the concept dimensions (no noise that
    # would distort cosine similarity for small corpora).
    if dim <= _DIM_SIZE:
        return vec[:dim]
    return vec + [0.0] * (dim - _DIM_SIZE)


def classify_concepts(text: str) -> List[ConceptMatch]:
    return _match_concepts(text)


def _animal_subjects(text: str) -> List[str]:
    """Animal subjects only.

    Environment subjects (forest/ocean/...) are context, not the *topic* of a
    post, so they must not create cross-animal compatibility in the guard.
    """
    return [m.key for m in _match_concepts(text) if m.category == "animal"]


def primary_subject(text: str) -> Optional[str]:
    """Return the most specific subject mentioned in ``text`` (if any).

    Animal subjects are preferred for mismatch explanations, falling back to
    environment subjects.
    """
    matches = _match_concepts(text)
    subjects = [m.key for m in matches if m.is_subject]
    animals = [m.key for m in matches if m.category == "animal"]
    if animals:
        return animals[0]
    return subjects[0] if subjects else None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

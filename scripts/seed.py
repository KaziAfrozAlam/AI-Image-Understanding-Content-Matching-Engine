"""Reproducible seed script.

Creates the image corpus (placeholder files + structured labels), the blog
posts, processes images + post embeddings synchronously, and writes the
evaluation labels used to measure Top-1 Precision.

Run with:
    python scripts/seed.py

It is idempotent: re-running will not duplicate records. Pass ``--reset`` to
first drop all tables for a clean, fully reproducible re-seed:
    python scripts/seed.py --reset
"""
from __future__ import annotations

import json
import os
import sys

# Allow running as a standalone script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.db.database import SessionLocal, engine  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.models.image import ImageStatus  # noqa: E402
from app.db.models.job import JobType  # noqa: E402
from app.repositories.image_repository import ImageRepository  # noqa: E402
from app.repositories.job_repository import JobRepository  # noqa: E402
from app.repositories.post_repository import PostRepository  # noqa: E402
from app.workers.embedding_processing import run_post_embedding_job  # noqa: E402
from app.workers.image_processing import run_image_job  # noqa: E402
from scripts.download_images import ensure_images  # noqa: E402

# ---------------------------------------------------------------------------
# Corpus definition (subject -> number of images + sample attributes)
# ---------------------------------------------------------------------------
CORPUS_PLAN = {
    "fox": {
        "count": 6,
        "category": "animal",
        "attributes": ["orange fur", "wild", "forest", "predator", "mammal"],
        "caption": "A red fox standing in a forest.",
    },
    "wolf": {
        "count": 6,
        "category": "animal",
        "attributes": ["gray fur", "wild", "forest", "predator", "canine"],
        "caption": "A gray wolf in a forest.",
    },
    "dog": {
        "count": 5,
        "category": "animal",
        "attributes": ["domestic", "pet", "loyal", "canine"],
        "caption": "A domestic dog looking at the camera.",
    },
    "bear": {
        "count": 5,
        "category": "animal",
        "attributes": ["brown fur", "wild", "large", "mammal"],
        "caption": "A brown bear in the wilderness.",
    },
    "deer": {
        "count": 5,
        "category": "animal",
        "attributes": ["tan fur", "wild", "forest", "herbivore"],
        "caption": "A deer standing in a grassy clearing.",
    },
    "cat": {
        "count": 4,
        "category": "animal",
        "attributes": ["domestic", "pet", "feline", "soft fur"],
        "caption": "A cat resting indoors.",
    },
    "bird": {
        "count": 4,
        "category": "animal",
        "attributes": ["wings", "wild", "sky", "avian"],
        "caption": "A bird perched on a branch.",
    },
    "fish": {
        "count": 3,
        "category": "animal",
        "attributes": ["scales", "wild", "ocean", "aquatic"],
        "caption": "A fish swimming underwater.",
    },
    "forest": {
        "count": 3,
        "category": "environment",
        "attributes": ["trees", "green", "wild", "peaceful"],
        "caption": "A quiet forest with tall trees.",
    },
    "ocean": {
        "count": 2,
        "category": "environment",
        "attributes": ["water", "blue", "waves", "vast"],
        "caption": "A wide ocean view with waves.",
    },
    "mountain": {
        "count": 2,
        "category": "environment",
        "attributes": ["rocky", "high", "snow", "wild"],
        "caption": "A tall mountain against the sky.",
    },
}

POSTS = [
    ("The Behavior of Red Foxes", "Red foxes are adaptable wild animals that live in forests. The red fox is a small predator known for its orange fur.", "fox"),
    ("Gray Wolves of the Northern Forest", "The gray wolf is a wild canine that hunts in packs across northern forests. Wolves are powerful predators.", "wolf"),
    ("Domestic Dogs and Their Ancestry", "Domestic dogs are loyal pets descended from wild canines. The dog is a common household companion.", "dog"),
    ("Bears: Giants of the Wilderness", "The bear is a large wild mammal found in forests and mountains. Brown bears are powerful animals.", "bear"),
    ("Deer in the Wild", "Deer are gentle wild herbivores that roam forests and meadows. The deer is known for its tan coat.", "deer"),
    ("Cats: From Pets to Predators", "The cat is a small feline kept as a pet but still a skilled predator. Domestic cats are soft and curious.", "cat"),
    ("Birds of Prey in the Sky", "Birds such as eagles and owls rule the skies. The bird is a winged animal built for flight.", "bird"),
    ("Life Underwater: Fish and Their Habitats", "Fish are aquatic animals that breathe through gills. The fish swims freely in oceans and rivers.", "fish"),
    ("The Quiet Life of the Forest", "The forest is a calm environment full of tall trees and wildlife. Forests are green and peaceful places.", "forest"),
    ("Oceans and Their Mysteries", "The ocean is a vast body of salt water covering the planet. Oceans are blue and full of waves.", "ocean"),
    ("Mountains and High Altitudes", "The mountain is a tall rocky landform often capped with snow. Mountains rise high above the land.", "mountain"),
    ("Vulpes vulpes: The Red Fox Explained", "Vulpes vulpes, commonly called the red fox, is a wild canine with orange fur found in forests.", "fox"),
    ("The History of Renaissance Painting in Florence", "Renaissance painting flourished in Florence during the 15th century. This article discusses art, frescoes, and classical sculpture.", None),
]


# A deliberately low-confidence image: the simulated vision model is unsure, so
# the ingestion pipeline must FLAG it (PROBE 1) rather than accept it. It is not
# referenced by any post, so it does not affect the evaluation precision.
LOW_CONFIDENCE_IMAGE = {
    "filename": "blurry_subject_01.jpg",
    "subject": "unknown",
    "category": "unknown",
    "attributes": [],
    "caption": "A low-quality, blurry image that is difficult to classify.",
    "confidence": 0.30,
}


def build_corpus():
    entries = []
    for subject, plan in CORPUS_PLAN.items():
        for i in range(1, plan["count"] + 1):
            filename = f"{subject}_{i:02d}.jpg"
            entries.append(
                {
                    "filename": filename,
                    "subject": subject,
                    "category": plan["category"],
                    "attributes": plan["attributes"],
                    "caption": plan["caption"],
                    "confidence": round(0.90 + (i % 5) * 0.015, 3),
                }
            )
    entries.append(LOW_CONFIDENCE_IMAGE)
    return entries


def main() -> None:
    reset = "--reset" in sys.argv
    if reset:
        Base.metadata.drop_all(bind=engine)
        print("Reset: dropped all tables.")

    os.makedirs(settings.data_dir, exist_ok=True)
    os.makedirs(settings.images_dir, exist_ok=True)

    # Ensure the schema exists (the API also does this on startup; this keeps
    # the seed script runnable on its own, e.g. before the API starts).
    Base.metadata.create_all(bind=engine)

    corpus = build_corpus()
    ensure_images(settings.images_dir, corpus)

    # Write structured labels (simulated vision output for the local backend).
    labels = {e["filename"]: {k: e[k] for k in ("subject", "category", "attributes", "caption", "confidence")} for e in corpus}
    with open(settings.labels_file, "w", encoding="utf-8") as fh:
        json.dump(labels, fh, indent=2)

    db = SessionLocal()
    try:
        img_repo = ImageRepository(db)
        post_repo = PostRepository(db)
        job_repo = JobRepository(db)

        # --- Images (idempotent by filename) ---
        from app.schemas.image import ImageCreate

        image_ids_by_subject: dict = {}
        for e in corpus:
            existing = img_repo.get_by_filename(e["filename"])
            if existing:
                image_ids_by_subject.setdefault(e["subject"], []).append(existing.id)
                continue
            image = img_repo.create(ImageCreate(source_url=None, filename=e["filename"]))
            image_ids_by_subject.setdefault(e["subject"], []).append(image.id)

        # --- Posts (idempotent by title) ---
        from sqlalchemy import select

        from app.db.models.post import Post
        from app.schemas.post import PostCreate

        post_id_by_title = {}
        for title, content, _subject in POSTS:
            pid = db.execute(
                select(Post.id).where(Post.title == title)
            ).scalar_one_or_none()
            if pid:
                post_id_by_title[title] = pid
                continue
            post = post_repo.create(PostCreate(
                title=title, content=content, category=_subject or "art"
            ))
            post_id_by_title[title] = post.id

        # --- Process images + post embeddings synchronously ---
        img_job = job_repo.create(JobType.IMAGE_PROCESSING.value)
        run_image_job(db, img_job)

        emb_job = job_repo.create(JobType.POST_EMBEDDING.value)
        run_post_embedding_job(db, emb_job)

        # --- Build evaluation labels ---
        eval_labels = []
        for title, _content, subject in POSTS:
            pid = post_id_by_title[title]
            expected = None
            if subject and image_ids_by_subject.get(subject):
                expected = image_ids_by_subject[subject][0]
            eval_labels.append(
                {"post_id": pid, "post_title": title, "expected_image_id": expected}
            )
        with open(settings.eval_labels_file, "w", encoding="utf-8") as fh:
            json.dump(eval_labels, fh, indent=2)

        # --- Summary ---
        completed = img_repo.list(status=ImageStatus.COMPLETED.value)[1]
        print("Seed complete.")
        print(f"  Images: {len(corpus)} ({completed} completed)")
        print(f"  Posts:  {len(POSTS)}")
        print(f"  Labels written to: {settings.labels_file}")
        print(f"  Eval labels written to: {settings.eval_labels_file}")
        print("Next: run `pytest`, then POST /evaluation/run (or `python -m app.workers.job_runner --run-once`).")
    finally:
        db.close()


if __name__ == "__main__":
    main()

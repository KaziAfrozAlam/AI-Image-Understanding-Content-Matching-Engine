"""Generate a small, licensed-free, fully offline image corpus.

For the $0 / reproducible requirement this script creates deterministic
placeholder images (one solid colour block per category) so the pipeline has
real files to reference. The *understanding* of each image comes from the
structured labels written by ``scripts/seed.py`` (which simulate a vision
model when no API key is configured).

If you want real photographs, drop JPEGs into ``data/images`` named exactly like
the entries in ``labels.json`` and configure ``GEMINI_API_KEY``; the real vision
backend will be used automatically.
"""
from __future__ import annotations

import os

from PIL import Image

# One representative colour per subject/category for the placeholder blocks.
CATEGORY_COLORS = {
    "fox": (200, 90, 40),
    "wolf": (120, 120, 130),
    "dog": (170, 130, 80),
    "bear": (90, 60, 40),
    "deer": (160, 120, 80),
    "cat": (80, 80, 90),
    "bird": (60, 120, 180),
    "fish": (40, 130, 160),
    "forest": (40, 110, 50),
    "ocean": (30, 90, 170),
    "mountain": (120, 110, 130),
}


def ensure_images(images_dir: str, entries: list) -> None:
    os.makedirs(images_dir, exist_ok=True)
    for entry in entries:
        subject = entry["subject"]
        filename = entry["filename"]
        path = os.path.join(images_dir, filename)
        if os.path.exists(path):
            continue
        color = CATEGORY_COLORS.get(subject, (128, 128, 128))
        img = Image.new("RGB", (256, 256), color)
        img.save(path)

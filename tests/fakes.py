"""Shared test fakes."""
from __future__ import annotations

from app.schemas.image import ImageMetadata
from app.services.vision_service import BaseVisionService, VisionError


class FakeVisionService(BaseVisionService):
    """Configurable vision fake for pipeline tests."""

    def __init__(self, db, fail_times=0, malformed=False, metadata=None):
        super().__init__(db, "fake-vision")
        self.fail_times = fail_times
        self.malformed = malformed
        self.metadata = metadata or ImageMetadata(
            subject="fox", category="animal",
            attributes=["orange fur", "wild"], caption="A red fox.", confidence=0.95,
        )
        self.calls = 0

    def understand(self, filename, image_path=None):
        self.calls += 1
        if self.malformed:
            raise VisionError("Invalid JSON from vision model")
        if self.calls <= self.fail_times:
            raise VisionError(f"transient vision failure (attempt {self.calls})")
        self._record("vision", 0.0, "SIMULATED", {"fake": True})
        return self.metadata

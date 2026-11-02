"""
Video Ingestion Module (SRS §8.1).

- Accepts webcam index or local file path (FR-01).
- Configurable source FPS vs. processing FPS via frame skipping (FR-03).
- Bounded internal state — no unbounded buffering (NFR-04, NFR-03).
- Dropped/failed frames are counted and reported, never crash the pipeline
  (SRS §8.1: "Dropped frames shall not crash the pipeline").

This module intentionally does nothing beyond "read frames reliably and
measure throughput" — detection/tracking/pose are separate modules that
consume frames from here (NFR-05: modularity).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2


@dataclass
class FrameResult:
    ok: bool
    frame: "cv2.typing.MatLike | None"
    timestamp: float


class VideoSource:
    """Wraps cv2.VideoCapture for a webcam index or a video file path."""

    def __init__(self, source: str, source_fps: int = 30, processing_fps: int = 12):
        self._raw_source = source
        self.source_fps = source_fps
        self.processing_fps = max(1, min(processing_fps, source_fps))
        # Frame skip ratio to go from source_fps -> processing_fps
        self._skip_every = max(1, round(self.source_fps / self.processing_fps))

        self._cap: cv2.VideoCapture | None = None
        self._frame_counter = 0
        self.dropped_frames = 0
        self.processed_frames = 0

        # Rolling FPS measurement window
        self._fps_window_start = time.monotonic()
        self._fps_window_count = 0
        self.measured_fps = 0.0

    @property
    def _cv2_source(self):
        # "0", "1" etc. -> webcam index (int). Anything else -> file path (str).
        return int(self._raw_source) if self._raw_source.isdigit() else self._raw_source

    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self._cv2_source)
        return self._cap.isOpened()

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> FrameResult:
        """Reads the next frame that should be *processed*, applying frame
        skipping to go from source_fps to processing_fps. Returns
        ok=False (without raising) on a failed/dropped read."""
        if self._cap is None:
            return FrameResult(ok=False, frame=None, timestamp=time.monotonic())

        while True:
            ok, frame = self._cap.read()
            now = time.monotonic()
            if not ok:
                self.dropped_frames += 1
                return FrameResult(ok=False, frame=None, timestamp=now)

            self._frame_counter += 1
            if self._frame_counter % self._skip_every != 0:
                continue  # skip this frame — not on the processing_fps cadence

            self.processed_frames += 1
            self._update_measured_fps(now)
            return FrameResult(ok=True, frame=frame, timestamp=now)

    def _update_measured_fps(self, now: float) -> None:
        self._fps_window_count += 1
        elapsed = now - self._fps_window_start
        if elapsed >= 1.0:
            self.measured_fps = round(self._fps_window_count / elapsed, 2)
            self._fps_window_count = 0
            self._fps_window_start = now

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def status(self) -> dict:
        return {
            "source": self._raw_source,
            "is_open": self.is_open(),
            "target_processing_fps": self.processing_fps,
            "measured_fps": self.measured_fps,
            "processed_frames": self.processed_frames,
            "dropped_frames": self.dropped_frames,
        }

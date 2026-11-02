"""
Detection + Tracking Module (SRS §8.2, Week 2 deliverable).

Baseline per SRS §8.2 table:
  Detector: YOLO11n | Input: 640-class | Precision: FP16 on CUDA | Tracker: ByteTrack

Design note on module boundaries (NFR-05): the SRS calls for detection and
tracking as conceptually separable modules. In practice, Ultralytics' YOLO
implementation couples per-frame detection with ByteTrack association inside
`model.track()` — re-implementing ByteTrack independently would add a heavy,
error-prone custom component for no accuracy or performance benefit at this
stage. We keep the *interface* clean instead: `PersonTracker.track_frame()`
is the single seam every downstream module (pose, HAR, safety events) calls
through. If a future requirement needs detection and tracking decoupled
(e.g. swapping trackers without touching the detector), that seam is where
the split happens.
"""
from __future__ import annotations

from dataclasses import dataclass

from ultralytics import YOLO

try:
    import torch
    _TORCH_AVAILABLE = True
except Exception:
    _TORCH_AVAILABLE = False

# COCO class id for "person" — the only class this module tracks (SRS §8.2: Tracked classes = Person)
PERSON_CLASS_ID = 0


@dataclass
class TrackedPerson:
    track_id: int
    bbox_xyxy: tuple[float, float, float, float]
    confidence: float


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    if _TORCH_AVAILABLE and torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


class PersonTracker:
    """Wraps YOLO11n + ByteTrack for stable person tracking (FR-04, FR-06)."""

    def __init__(
        self,
        model_path: str = "yolo11n.pt",
        device: str = "auto",
        conf_threshold: float = 0.4,
        img_size: int = 640,
        tracker_config: str = "bytetrack.yaml",
    ):
        self.device = resolve_device(device)
        self.half = self.device.startswith("cuda")  # FP16 on GPU per SRS §8.2
        self.conf_threshold = conf_threshold
        self.img_size = img_size
        self.tracker_config = tracker_config

        self.model = YOLO(model_path)

        # Inference-stage FPS (separate from ingestion FPS — this is the
        # number that matters against NFR-01's 10-15 FPS target).
        self._infer_times: list[float] = []
        self.inference_fps = 0.0

    def track_frame(self, frame) -> list[TrackedPerson]:
        import time

        t0 = time.monotonic()
        results = self.model.track(
            frame,
            persist=True,
            tracker=self.tracker_config,
            classes=[PERSON_CLASS_ID],
            conf=self.conf_threshold,
            imgsz=self.img_size,
            device=self.device,
            half=self.half,
            verbose=False,
        )
        elapsed = time.monotonic() - t0
        self._update_inference_fps(elapsed)

        return self._parse_results(results)

    def _parse_results(self, results) -> list[TrackedPerson]:
        tracked: list[TrackedPerson] = []
        if not results:
            return tracked

        boxes = results[0].boxes
        if boxes is None or boxes.id is None:
            # No stable track IDs yet this frame (e.g. first frame, or all
            # detections still unconfirmed by ByteTrack) — report nothing
            # rather than IDs that aren't actually stable (FR-06).
            return tracked

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        ids = boxes.id.cpu().numpy().astype(int)

        for box, conf, track_id in zip(xyxy, confs, ids):
            tracked.append(
                TrackedPerson(
                    track_id=int(track_id),
                    bbox_xyxy=tuple(float(v) for v in box),
                    confidence=float(conf),
                )
            )
        return tracked

    def _update_inference_fps(self, elapsed_seconds: float) -> None:
        # Rolling window of the last 30 inference calls — smooths jitter
        # while still reacting quickly to a real slowdown (unlike a
        # cumulative average since startup).
        self._infer_times.append(elapsed_seconds)
        if len(self._infer_times) > 30:
            self._infer_times.pop(0)
        avg = sum(self._infer_times) / len(self._infer_times)
        self.inference_fps = round(1.0 / avg, 2) if avg > 0 else 0.0

    def status(self) -> dict:
        return {
            "device": self.device,
            "half_precision": self.half,
            "inference_fps": self.inference_fps,
        }

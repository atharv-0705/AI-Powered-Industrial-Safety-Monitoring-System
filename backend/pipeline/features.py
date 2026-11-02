"""
Feature extraction + temporal buffering (SRS §8.4 input side).

SRS §8.4 specifies the HAR module's input as "32 frames x normalized
pose/motion features" with example features: normalized landmark coords,
landmark velocity, selected joint angles, body orientation, bbox
width/height, center-of-box velocity. This module builds exactly that
32-frame buffer, per track_id. The Temporal Transformer that *consumes*
the buffer is Week 4 — this module's job ends at "buffer is full and ready".

Bounded by design (SRS §17 risk table: "16 GB RAM pressure" / "Bounded
queues, avoid storing full videos in memory"): each track's buffer is a
fixed-size deque (maxlen=32), and stale tracks (not updated for
STALE_TRACK_FRAMES) are dropped so memory doesn't grow with track churn.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

from backend.pipeline.pose import PoseResult

SEQUENCE_LENGTH = 64          # SRS §8.4: fixed-length sequence per person
STALE_TRACK_FRAMES = 30      # ~5s at 12 FPS — drop buffers for tracks we haven't seen recently

# MediaPipe Pose landmark indices used for joint-angle/orientation features
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle at vertex b, formed by points a-b-c, in degrees. Returns 0.0
    on a degenerate (zero-length) vector rather than raising."""
    v1, v2 = a - b, c - b
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos_angle = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def build_feature_vector(
    pose: PoseResult,
    bbox_xyxy: tuple[float, float, float, float],
    frame_size: tuple[int, int],
    prev_landmarks_xy: np.ndarray | None,
    prev_bbox_center: tuple[float, float] | None,
) -> np.ndarray:
    """One frame's feature vector for one tracked person.

    Layout (all floats, concatenated):
      [0:132]   33 landmarks x (x, y, z, visibility)   -- normalized to bbox
      [132:198] 33 landmarks x (dx, dy) velocity vs previous frame
      [198:200] 2 selected joint angles (elbow avg, knee avg), degrees/180
      [200]     body orientation: shoulder-line angle vs horizontal, degrees/180
      [201:203] bbox (width, height) normalized by frame size
      [203:205] bbox center velocity (dx, dy), normalized by frame size
    Total: 205 dims.
    """
    landmarks = pose.landmarks  # (33, 4): x, y, z, visibility — already bbox-normalized
    xy = landmarks[:, :2]

    velocity = np.zeros((landmarks.shape[0], 2), dtype=np.float32)
    if prev_landmarks_xy is not None and prev_landmarks_xy.shape == xy.shape:
        velocity = xy - prev_landmarks_xy

    l_elbow_angle = _angle(landmarks[L_SHOULDER, :2], landmarks[L_ELBOW, :2], landmarks[L_WRIST, :2])
    r_elbow_angle = _angle(landmarks[R_SHOULDER, :2], landmarks[R_ELBOW, :2], landmarks[R_WRIST, :2])
    l_knee_angle = _angle(landmarks[L_HIP, :2], landmarks[L_KNEE, :2], landmarks[L_ANKLE, :2])
    r_knee_angle = _angle(landmarks[R_HIP, :2], landmarks[R_KNEE, :2], landmarks[R_ANKLE, :2])
    avg_elbow_angle = (l_elbow_angle + r_elbow_angle) / 2.0 / 180.0
    avg_knee_angle = (l_knee_angle + r_knee_angle) / 2.0 / 180.0

    shoulder_vec = landmarks[R_SHOULDER, :2] - landmarks[L_SHOULDER, :2]
    body_orientation = float(np.degrees(np.arctan2(shoulder_vec[1], shoulder_vec[0]))) / 180.0

    x1, y1, x2, y2 = bbox_xyxy
    frame_w, frame_h = frame_size
    bbox_w = (x2 - x1) / frame_w
    bbox_h = (y2 - y1) / frame_h
    center = ((x1 + x2) / 2.0 / frame_w, (y1 + y2) / 2.0 / frame_h)

    center_velocity = (0.0, 0.0)
    if prev_bbox_center is not None:
        center_velocity = (center[0] - prev_bbox_center[0], center[1] - prev_bbox_center[1])

    return np.concatenate([
        landmarks.flatten(),                                   # 132
        velocity.flatten(),                                    # 66
        np.array([avg_elbow_angle, avg_knee_angle], dtype=np.float32),  # 2
        np.array([body_orientation], dtype=np.float32),         # 1
        np.array([bbox_w, bbox_h], dtype=np.float32),            # 2
        np.array(center_velocity, dtype=np.float32),             # 2
    ]).astype(np.float32)                                        # = 205


@dataclass
class _TrackBuffer:
    features: deque = field(default_factory=lambda: deque(maxlen=SEQUENCE_LENGTH))
    prev_landmarks_xy: np.ndarray | None = None
    prev_bbox_center: tuple[float, float] | None = None
    frames_since_update: int = 0

    @property
    def is_full(self) -> bool:
        return len(self.features) == SEQUENCE_LENGTH

    def as_array(self) -> np.ndarray:
        """Shape (32, 205) — exactly the SRS §8.4 HAR input shape."""
        return np.stack(list(self.features), axis=0)


class TemporalFeatureManager:
    """Owns one bounded feature buffer per track_id (FR-06 identities +
    SRS §8.4 input prep). This is the object Week 4's HAR module will read
    completed buffers from."""

    def __init__(self):
        self._buffers: dict[int, _TrackBuffer] = {}

    def update(
        self,
        track_id: int,
        pose: PoseResult,
        bbox_xyxy: tuple[float, float, float, float],
        frame_size: tuple[int, int],
    ) -> _TrackBuffer:
        buf = self._buffers.setdefault(track_id, _TrackBuffer())

        vec = build_feature_vector(
            pose, bbox_xyxy, frame_size, buf.prev_landmarks_xy, buf.prev_bbox_center
        )
        buf.features.append(vec)
        buf.prev_landmarks_xy = pose.landmarks[:, :2]
        x1, y1, x2, y2 = bbox_xyxy
        w, h = frame_size
        buf.prev_bbox_center = ((x1 + x2) / 2.0 / w, (y1 + y2) / 2.0 / h)
        buf.frames_since_update = 0
        return buf

    def prune_stale(self, active_track_ids: set[int]) -> None:
        """Call once per frame with the current frame's active track IDs.
        Drops buffers for tracks not seen recently (bounds memory growth —
        SRS §17: '16 GB RAM pressure' risk)."""
        for track_id, buf in list(self._buffers.items()):
            if track_id in active_track_ids:
                continue
            buf.frames_since_update += 1
            if buf.frames_since_update > STALE_TRACK_FRAMES:
                del self._buffers[track_id]

    def get(self, track_id: int) -> _TrackBuffer | None:
        return self._buffers.get(track_id)

    def clear(self) -> None:
        """Clear all active buffers."""
        self._buffers.clear()

    def reset(self) -> None:
        """Alias for clear()."""
        self.clear()

    def status(self) -> dict:
        return {
            "active_buffers": len(self._buffers),
            "ready_for_har": [tid for tid, b in self._buffers.items() if b.is_full],
        }

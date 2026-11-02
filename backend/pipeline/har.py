"""
Activity Recognition inference wrapper (SRS §8.4 output side).

Consumes temporal feature buffers produced by TemporalFeatureManager and returns
an activity label + confidence.

Modes:
  1. Live Webcam Mode:
     - Predicts ONLY 'standing', 'sitting', or 'walking'.
     - If the person's position changes along the X, Y, or Z axis, predicts 'walking'.
     - Otherwise, predicts 'standing' or 'sitting' based on posture.
     - Never predicts 'climbing' or 'running' (strictly zeroed out).
  2. Video (.mp4 / file) Mode:
     - Evaluates all 5 classes: 'walking', 'running', 'standing', 'sitting', 'climbing'.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F

from backend.app.ml.har_model import ACTIVITY_CLASSES, FEATURE_DIM, SEQUENCE_LENGTH, build_model


@dataclass
class ActivityPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


def _resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    return "cuda:0" if torch.cuda.is_available() else "cpu"


def is_webcam_source(source: str | int | None) -> bool:
    """Returns True if the source represents a live webcam feed, False for video files (.mp4, etc.)."""
    if source is None:
        return True
    if isinstance(source, int):
        return True
    s = str(source).strip()
    if s.isdigit():
        return True
    if s.lower() in ("", "0", "1", "2", "webcam"):
        return True
    # If the string ends with a standard video file extension, it's a file
    video_exts = (".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv")
    if any(s.lower().endswith(ext) for ext in video_exts):
        return False
    # If it exists on disk as a file
    try:
        p = Path(s)
        if p.is_file():
            return False
    except Exception:
        pass
    return False


def _apply_kinematic_priors(
    probs: np.ndarray,
    feature_sequence: np.ndarray,
    is_webcam: bool = False,
) -> np.ndarray:
    """Refines model prediction probabilities with physical kinematic constraints.

    Webcam Mode:
      - Predicts ONLY 'standing', 'sitting', or 'walking'.
      - If person moves along X, Y, or Z axis -> 'walking'.
      - Stationary -> 'standing' or 'sitting' based on posture.
      - 'climbing' and 'running' are strictly suppressed (0.0).

    Video (.mp4) Mode:
      - All 5 classes ('walking', 'running', 'standing', 'sitting', 'climbing')
        are fully active.
    """
    adjusted = probs.copy().astype(np.float64)

    # 1. Landmark velocities: [132:198] -> 33 landmarks x (dx, dy)
    landmark_vel = feature_sequence[:, 132:198].reshape(-1, 33, 2)
    motion_energy = float(np.linalg.norm(landmark_vel, axis=-1).mean())
    bbox_vel = float(np.linalg.norm(feature_sequence[:, 203:205], axis=-1).mean())

    # 2. Key landmark positions in normalized bbox: [33, 4] -> (x, y, z, vis)
    landmarks_seq = feature_sequence[:, :132].reshape(-1, 33, 4)
    l_shoulder_y = float(landmarks_seq[:, 11, 1].mean())
    r_shoulder_y = float(landmarks_seq[:, 12, 1].mean())
    l_wrist_y = float(landmarks_seq[:, 15, 1].mean())
    r_wrist_y = float(landmarks_seq[:, 16, 1].mean())

    # Hands raised: wrist near/above shoulder
    hands_raised = (l_wrist_y < l_shoulder_y + 0.08) or (r_wrist_y < r_shoulder_y + 0.08)

    # Visibilities & posture dimensions:
    knee_vis = float((landmarks_seq[:, 25, 3] + landmarks_seq[:, 26, 3]).mean() / 2.0)
    bbox_w = max(0.01, float(feature_sequence[:, 201].mean()))
    bbox_h = max(0.01, float(feature_sequence[:, 202].mean()))
    aspect_ratio = bbox_h / bbox_w
    knee_angle_deg = float(feature_sequence[:, 199].mean()) * 180.0

    # 3. Positional displacement along X, Y, and Z axes:
    # Use both recent window (last 16 frames, ~1-1.5s) and full buffer to prevent stationary dilution
    recent_len = min(len(feature_sequence), 16)
    recent_seq = feature_sequence[-recent_len:]

    # X-axis displacement (horizontal motion in camera frame)
    recent_step_x = float(np.max(np.abs(recent_seq[:, 203]))) if len(recent_seq) > 0 else 0.0
    recent_path_x = float(np.sum(np.abs(recent_seq[:, 203]))) if len(recent_seq) > 0 else 0.0
    full_path_x = float(np.sum(np.abs(feature_sequence[:, 203]))) if len(feature_sequence) > 0 else 0.0
    has_x_motion = (recent_step_x > 0.0020 or recent_path_x > 0.008 or full_path_x > 0.015)

    # Y-axis displacement (vertical motion in camera frame)
    recent_step_y = float(np.max(np.abs(recent_seq[:, 204]))) if len(recent_seq) > 0 else 0.0
    recent_path_y = float(np.sum(np.abs(recent_seq[:, 204]))) if len(recent_seq) > 0 else 0.0
    full_path_y = float(np.sum(np.abs(feature_sequence[:, 204]))) if len(feature_sequence) > 0 else 0.0
    has_y_motion = (recent_step_y > 0.0020 or recent_path_y > 0.008 or full_path_y > 0.015)

    # Z-axis displacement (depth motion towards or away from the camera)
    # Measured by bounding box height and width scale changes and MediaPipe Z coordinates
    recent_scale_z = float(np.ptp(recent_seq[:, 202])) if len(recent_seq) > 0 else 0.0
    recent_scale_w = float(np.ptp(recent_seq[:, 201])) if len(recent_seq) > 0 else 0.0
    full_scale_z = float(np.ptp(feature_sequence[:, 202])) if len(feature_sequence) > 0 else 0.0
    lm_z_ptp = float(np.ptp(recent_seq[:, :132].reshape(-1, 33, 4)[:, [11, 12, 23, 24], 2])) if len(recent_seq) > 0 else 0.0
    has_z_motion = (recent_scale_z > 0.010 or recent_scale_w > 0.008 or full_scale_z > 0.018 or lm_z_ptp > 0.025)

    # Dynamic limb motion energy in recent frames
    recent_limb_energy = float(np.linalg.norm(recent_seq[:, 132:198].reshape(-1, 33, 2), axis=-1).mean())
    has_limb_motion = (recent_limb_energy > 0.012 or motion_energy > 0.018 or bbox_vel > 0.0025)

    # Combined position movement detector across x, y, and z axes
    has_position_change = (has_x_motion or has_y_motion or has_z_motion or has_limb_motion)

    # Standing vs Sitting posture decision
    is_standing = (
        (bbox_h >= 0.70)
        or (aspect_ratio >= 1.50)
        or (knee_vis > 0.35 and knee_angle_deg >= 135.0)
    )

    # ── BRANCH 1: WEBCAM MODE (Only standing, sitting, or walking) ───────────
    if is_webcam:
        # Strictly never predict climbing or running in webcam mode
        adjusted[1] = 0.0  # running = 0
        adjusted[4] = 0.0  # climbing = 0

        if has_position_change:
            # Person changes position along x, y, or z axis -> PREDICT WALKING
            adjusted[0] = 0.85  # walking (dominant)
            adjusted[2] = 0.08  # standing
            adjusted[3] = 0.07  # sitting
        else:
            # Stationary -> PREDICT STANDING OR SITTING
            adjusted[0] = 0.05  # walking (5%)
            if is_standing:
                adjusted[2] = 0.55  # standing (55%)
                adjusted[3] = 0.40  # sitting (40%)
            else:
                adjusted[3] = 0.55  # sitting (55%)
                adjusted[2] = 0.40  # standing (40%)

    # ── BRANCH 2: VIDEO (.MP4) MODE (All 5 classes active) ──────────────────


    else:
        # Case A: Climbing (arms raised above head with active motion)
        if hands_raised and motion_energy > 0.045:
            adjusted[4] = max(adjusted[4], 0.70) + 0.30
            adjusted[0] *= 0.20
            adjusted[1] *= 0.20
            adjusted[2] *= 0.20
            adjusted[3] *= 0.10

        # Case B: Running (high velocity & motion energy)
        elif motion_energy >= 0.120 or bbox_vel >= 0.030:
            adjusted[1] = max(adjusted[1], 0.75) + 0.35
            adjusted[0] *= 0.30
            adjusted[2] *= 0.05
            adjusted[3] *= 0.02
            adjusted[4] *= 0.10

        # Case C: Walking (moderate velocity / positional shift)
        elif has_position_change or motion_energy >= 0.055 or bbox_vel >= 0.015:
            adjusted[0] = max(adjusted[0], 0.70) + 0.30
            adjusted[1] *= 0.25
            adjusted[2] *= 0.15
            adjusted[3] *= 0.10
            adjusted[4] *= 0.10

        # Case D: Stationary Posture (Standing vs Sitting)
        else:
            adjusted[0] *= 0.05
            adjusted[1] *= 0.01
            adjusted[4] *= 0.05

            if is_standing:
                adjusted[2] = max(adjusted[2], 0.80) + 0.40
                adjusted[3] *= 0.15
            else:
                adjusted[3] = max(adjusted[3], 0.80) + 0.40
                adjusted[2] *= 0.15

    # Normalize to valid probability distribution
    total = np.sum(adjusted)
    if total > 0:
        adjusted = adjusted / total
    return adjusted.astype(np.float32)


class ActivityRecognizer:
    def __init__(
        self,
        checkpoint_path: str,
        device: str = "auto",
        is_webcam: bool = False,
    ):
        self.device = _resolve_device(device)
        self.checkpoint_path = Path(checkpoint_path)
        self.is_webcam = is_webcam
        self.model = build_model().to(self.device)
        self.is_ready = False

        if self.checkpoint_path.is_file() and self.checkpoint_path.stat().st_size > 0:
            try:
                state = torch.load(self.checkpoint_path, map_location=self.device, weights_only=False)
                self.model.load_state_dict(state["model_state_dict"] if "model_state_dict" in state else state)
                self.model.eval()
                self.is_ready = True
            except Exception as e:
                print(f"[ActivityRecognizer] Warning: Failed to load checkpoint from '{self.checkpoint_path}': {e}")
                self.is_ready = False

    def set_source(self, source: str | int | None) -> None:
        """Sets webcam mode dynamically based on video source path or device index."""
        self.is_webcam = is_webcam_source(source)

    def predict(
        self,
        feature_sequence: np.ndarray,
        is_webcam: Optional[bool] = None,
    ) -> ActivityPrediction | None:
        if not self.is_ready:
            return None

        # Accept sequence lengths >= SEQUENCE_LENGTH (e.g. 32 or 64 frames)
        if feature_sequence.shape[-1] != FEATURE_DIM:
            raise ValueError(
                f"Expected feature dimension {FEATURE_DIM}, got {feature_sequence.shape[-1]}"
            )
        if feature_sequence.shape[0] < SEQUENCE_LENGTH:
            raise ValueError(
                f"Expected at least {SEQUENCE_LENGTH} frames, got {feature_sequence.shape[0]}"
            )

        # Slice the most recent SEQUENCE_LENGTH frames for the Transformer input
        model_input = feature_sequence[-SEQUENCE_LENGTH:]

        with torch.no_grad():
            x = torch.from_numpy(model_input).float().unsqueeze(0).to(self.device)  # (1, 32, 205)
            logits = self.model(x)
            probs = F.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

        webcam_mode = self.is_webcam if is_webcam is None else is_webcam
        probs = _apply_kinematic_priors(probs, feature_sequence, is_webcam=webcam_mode)

        top_idx = int(np.argmax(probs))
        return ActivityPrediction(
            label=ACTIVITY_CLASSES[top_idx],
            confidence=float(probs[top_idx]),
            probabilities={cls: float(p) for cls, p in zip(ACTIVITY_CLASSES, probs)},
        )

    def status(self) -> dict:
        return {
            "is_ready": self.is_ready,
            "is_webcam": self.is_webcam,
            "mode": "webcam (standing/sitting/walking)" if self.is_webcam else "video (5 classes)",
            "checkpoint_path": str(self.checkpoint_path),
            "device": self.device,
            "classes": ACTIVITY_CLASSES if not self.is_webcam else ["walking", "standing", "sitting"],
        }

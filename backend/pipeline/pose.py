"""
Pose Module (SRS §8.3, Week 3 deliverable).

"MediaPipe Pose shall operate on person crops or tracked person regions.
The module shall return landmark coordinates and visibility/confidence
values." — SRS §8.3

Design decision: static_image_mode=True (see DECISIONS.md for the full
reasoning). Short version: MediaPipe's tracking mode assumes the ROI is
roughly the same size/position frame-to-frame; a YOLO+ByteTrack bbox crop
jumps around a lot more than that assumption tolerates, so we treat each
crop as an independent image instead of trusting MediaPipe's internal
smoothing across crops that don't correspond to a stable ROI.
"""
from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import mediapipe as mp
import numpy as np

# 33 landmarks per SRS glossary ("anatomical landmarks such as shoulders,
# hips, knees and ankles") — this is MediaPipe Pose's fixed landmark set.
NUM_LANDMARKS = 33

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"
MODEL_PATH = Path("models/pose_landmarker_full.task")


@dataclass
class PoseResult:
    # Each landmark: (x, y, z, visibility) — x/y normalized 0-1 *within the
    # crop*, which (since the crop == the tracked bbox) already satisfies
    # SRS §8.3's "normalized relative to the person bounding box".
    landmarks: np.ndarray  # shape (33, 4)


class PoseEstimator:
    def __init__(self, min_detection_confidence: float = 0.5):
        self._mode = "legacy"
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
            self._mp_pose = mp.solutions.pose
            self._pose = self._mp_pose.Pose(
                static_image_mode=True,
                model_complexity=1,  # 0=lite, 1=full, 2=heavy
                min_detection_confidence=min_detection_confidence,
            )
        else:
            # Modern MediaPipe Tasks API (MediaPipe 0.10.35+ / 1.0+)
            self._mode = "tasks"
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            if not MODEL_PATH.exists():
                print(f"[PoseEstimator] Downloading pose landmarker model to {MODEL_PATH} ...")
                urllib.request.urlretrieve(MODEL_URL, str(MODEL_PATH))
                print("[PoseEstimator] Download complete.")

            from mediapipe.tasks.python import BaseOptions, vision

            options = vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.IMAGE,
                min_pose_detection_confidence=min_detection_confidence,
            )
            self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def estimate(self, person_crop_bgr: np.ndarray) -> PoseResult | None:
        if person_crop_bgr is None or person_crop_bgr.size == 0:
            return None

        rgb = np.ascontiguousarray(person_crop_bgr[:, :, ::-1])

        if self._mode == "legacy":
            results = self._pose.process(rgb)
            if not results.pose_landmarks:
                return None

            landmarks = np.array(
                [(lm.x, lm.y, lm.z, getattr(lm, "visibility", 1.0)) for lm in results.pose_landmarks.landmark],
                dtype=np.float32,
            )
            return PoseResult(landmarks=landmarks)
        else:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = self._landmarker.detect(mp_image)
            if not results.pose_landmarks or len(results.pose_landmarks) == 0:
                return None

            first_person = results.pose_landmarks[0]
            landmarks = np.array(
                [(lm.x, lm.y, lm.z, getattr(lm, "visibility", 1.0)) for lm in first_person],
                dtype=np.float32,
            )
            return PoseResult(landmarks=landmarks)

    def close(self) -> None:
        if self._mode == "legacy" and hasattr(self, "_pose"):
            self._pose.close()
        elif self._mode == "tasks" and hasattr(self, "_landmarker"):
            self._landmarker.close()

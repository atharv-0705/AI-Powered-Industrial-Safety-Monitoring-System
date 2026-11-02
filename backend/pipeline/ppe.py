"""
PPE Detection Module (SRS §8.2, FR-05, Week 5 deliverable).

Detects personal protective equipment (safety helmets / hard hats, high-visibility vests)
and associates compliance status with tracked persons using spatial geometry
(DECISIONS.md §7 R-07: head IoU in upper 25-30% of bbox, torso IoU in middle 20-70%).

Model: models/ppe_yolo11n.pt
Target Classes: hardhat/helmet, no_hardhat, vest, no_vest, person
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from ultralytics import YOLO


@dataclass
class PPEDetection:
    category: str  # "helmet", "no-helmet", "vest", "no-vest", "boots", "gloves", "person"
    raw_class: str
    bbox_xyxy: tuple[float, float, float, float]
    confidence: float

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox_xyxy
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


@dataclass
class PersonPPEStatus:
    track_id: int
    has_helmet: bool
    has_vest: bool
    helmet_confidence: float = 0.0
    vest_confidence: float = 0.0
    helmet_bbox: Optional[tuple[float, float, float, float]] = None
    vest_bbox: Optional[tuple[float, float, float, float]] = None


# Normalize dataset class names to unified categories
CATEGORY_MAP = {
    "hardhat": "helmet",
    "helmet": "helmet",
    "no_hardhat": "no-helmet",
    "no-hardhat": "no-helmet",
    "vest": "vest",
    "no_vest": "no-vest",
    "no-vest": "no-vest",
    "boots": "boots",
    "no_boots": "no-boots",
    "gloves": "gloves",
    "no_gloves": "no-gloves",
    "person": "person",
}


def _box_iou(box1: tuple[float, float, float, float], box2: tuple[float, float, float, float]) -> float:
    """Calculate Intersection-over-Union (IoU) between two bounding boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = area1 + area2 - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def _point_in_box(point: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    """Return True if (x, y) is inside the bounding box."""
    px, py = point
    return box[0] <= px <= box[2] and box[1] <= py <= box[3]


def _resolve_device(device: str | int | None) -> str | int:
    """Normalize device for Ultralytics YOLO (expects 0 or 'cpu', never 'auto')."""
    if isinstance(device, int):
        return device if torch.cuda.is_available() else "cpu"
    if device is None or device in ("auto", ""):
        return 0 if torch.cuda.is_available() else "cpu"
    if str(device).lower() in ("cuda", "cuda:0", "0"):
        return 0 if torch.cuda.is_available() else "cpu"
    return device


class PPEDetector:
    """Wraps custom YOLO11n PPE detector with person association heuristics."""

    def __init__(
        self,
        model_path: str = "models/ppe_yolo11n.pt",
        device: str | int = "auto",
        conf_threshold: float = 0.30,
        img_size: int = 640,
    ):
        self.model_path = Path(model_path)
        self.device = _resolve_device(device)
        self.conf_threshold = conf_threshold
        self.img_size = img_size
        self.is_ready = False
        self.model: Optional[YOLO] = None

        if self.model_path.exists() and self.model_path.stat().st_size > 0:
            try:
                self.model = YOLO(str(self.model_path))
                self.is_ready = True
            except Exception as e:
                print(f"[PPEDetector] Warning: Failed to load model '{self.model_path}': {e}")
                self.is_ready = False

    def detect_ppe(self, frame_or_crop) -> list[PPEDetection]:
        """Runs PPE object detection across the frame and returns detections."""
        if not self.is_ready or self.model is None:
            return []

        results = self.model(
            frame_or_crop,
            conf=self.conf_threshold,
            imgsz=self.img_size,
            device=self.device,
            verbose=False,
        )

        detections = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                raw_name = self.model.names.get(cls_id, str(cls_id)).lower()
                category = CATEGORY_MAP.get(raw_name, raw_name)
                conf = float(box.conf[0])
                xyxy = tuple(float(v) for v in box.xyxy[0].tolist())

                detections.append(
                    PPEDetection(
                        category=category,
                        raw_class=raw_name,
                        bbox_xyxy=xyxy,
                        confidence=conf,
                    )
                )

        return detections

    def associate_ppe_to_person(
        self,
        track_id: int,
        person_bbox: tuple[float, float, float, float],
        ppe_detections: list[PPEDetection],
    ) -> PersonPPEStatus:
        """Associates helmet and vest detections to a tracked person.

        Uses anatomically constrained ROIs (DECISIONS.md §7 R-07):
          - Head ROI: upper 30% of person bounding box
          - Torso ROI: middle 20% to 70% of person bounding box
        """
        px1, py1, px2, py2 = person_bbox
        pw = px2 - px1
        ph = py2 - py1

        head_roi = (px1 - 0.05 * pw, py1 - 0.10 * ph, px2 + 0.05 * pw, py1 + 0.35 * ph)
        torso_roi = (px1 - 0.05 * pw, py1 + 0.15 * ph, px2 + 0.05 * pw, py1 + 0.75 * ph)

        best_helmet: Optional[PPEDetection] = None
        best_no_helmet: Optional[PPEDetection] = None
        best_vest: Optional[PPEDetection] = None
        best_no_vest: Optional[PPEDetection] = None

        for det in ppe_detections:
            center = det.center
            iou_head = _box_iou(det.bbox_xyxy, head_roi)
            in_head = _point_in_box(center, head_roi) or iou_head > 0.15

            iou_torso = _box_iou(det.bbox_xyxy, torso_roi)
            in_torso = _point_in_box(center, torso_roi) or iou_torso > 0.15

            if det.category == "helmet" and in_head:
                if best_helmet is None or det.confidence > best_helmet.confidence:
                    best_helmet = det
            elif det.category == "no-helmet" and in_head:
                if best_no_helmet is None or det.confidence > best_no_helmet.confidence:
                    best_no_helmet = det
            elif det.category == "vest" and in_torso:
                if best_vest is None or det.confidence > best_vest.confidence:
                    best_vest = det
            elif det.category == "no-vest" and in_torso:
                if best_no_vest is None or det.confidence > best_no_vest.confidence:
                    best_no_vest = det

        # Decide helmet status
        if best_helmet and (best_no_helmet is None or best_helmet.confidence >= best_no_helmet.confidence):
            has_helmet = True
            helmet_conf = best_helmet.confidence
            helmet_box = best_helmet.bbox_xyxy
        elif best_no_helmet:
            has_helmet = False
            helmet_conf = best_no_helmet.confidence
            helmet_box = best_no_helmet.bbox_xyxy
        else:
            has_helmet = False
            helmet_conf = 0.0
            helmet_box = None

        # Decide vest status
        if best_vest and (best_no_vest is None or best_vest.confidence >= best_no_vest.confidence):
            has_vest = True
            vest_conf = best_vest.confidence
            vest_box = best_vest.bbox_xyxy
        elif best_no_vest:
            has_vest = False
            vest_conf = best_no_vest.confidence
            vest_box = best_no_vest.bbox_xyxy
        else:
            has_vest = False
            vest_conf = 0.0
            vest_box = None

        return PersonPPEStatus(
            track_id=track_id,
            has_helmet=has_helmet,
            has_vest=has_vest,
            helmet_confidence=helmet_conf,
            vest_confidence=vest_conf,
            helmet_bbox=helmet_box,
            vest_bbox=vest_box,
        )

    def status(self) -> dict:
        return {
            "is_ready": self.is_ready,
            "model_path": str(self.model_path),
            "device": str(self.device),
            "classes": self.model.names if self.model else {},
        }

"""
Manual exit-criteria test for Week 5 (SRS §16, FR-05):
  "PPE detector detects helmets and high-visibility vests on tracked persons."

Full Pipeline:
  VideoSource -> PersonTracker (YOLO11n + ByteTrack) -> PPEDetector (YOLO11n-PPE)
  -> Anatomical Association (Upper-25% Head IoU, Torso-60% IoU).

Usage:
  python backend/scripts/test_ppe.py
  python backend/scripts/test_ppe.py --no-display --seconds 15
  python backend/scripts/test_ppe.py --source data/raw/walking/sample.avi
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.pa rent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from backend.app.core.config import get_settings
from backend.pipeline.detector import PersonTracker
from backend.pipeline.ingestion import VideoSource
from backend.pipeline.ppe import PPEDetector, PersonPPEStatus


def draw_ppe_overlay(
    frame: np.ndarray,
    tracked_persons,
    ppe_detector: PPEDetector,
    ppe_detections,
    fps: float,
) -> np.ndarray:
    """Renders visual bounding boxes, compliance tags, and FPS counter on frame."""
    out = frame.copy()
    h, w = out.shape[:2]

    # Draw raw PPE detections with subtle dashed-style boxes
    for det in ppe_detections:
        dx1, dy1, dx2, dy2 = (int(v) for v in det.bbox_xyxy)
        color = (0, 255, 255) if "helmet" in det.category else (255, 200, 0)
        cv2.rectangle(out, (dx1, dy1), (dx2, dy2), color, 1)

    compliant_count = 0
    total_persons = len(tracked_persons)

    for person in tracked_persons:
        px1, py1, px2, py2 = (int(v) for v in person.bbox_xyxy)
        status: PersonPPEStatus = ppe_detector.associate_ppe_to_person(
            person.track_id, person.bbox_xyxy, ppe_detections
        )

        is_fully_compliant = status.has_helmet and status.has_vest
        if is_fully_compliant:
            compliant_count += 1

        # Person box: Green if compliant, Red/Orange if missing any PPE
        box_color = (0, 220, 0) if is_fully_compliant else (0, 0, 240)
        cv2.rectangle(out, (px1, py1), (px2, py2), box_color, 2)

        # Labels
        helmet_label = f"HELMET OK ({status.helmet_confidence:.2f})" if status.has_helmet else "NO HELMET"
        vest_label = f"VEST OK ({status.vest_confidence:.2f})" if status.has_vest else "NO VEST"
        id_label = f"ID {person.track_id}"

        # Draw tags above person box
        tag_y = max(20, py1 - 10)
        cv2.putText(out, id_label, (px1, tag_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        h_color = (0, 255, 0) if status.has_helmet else (0, 0, 255)
        v_color = (0, 255, 0) if status.has_vest else (0, 0, 255)

        cv2.putText(out, helmet_label, (px1, tag_y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.50, h_color, 2)
        cv2.putText(out, vest_label, (px1, tag_y + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.50, v_color, 2)

    # Top HUD bar
    hud_bg = (20, 20, 20)
    cv2.rectangle(out, (0, 0), (w, 42), hud_bg, -1)

    hud_text = f"FPS: {fps:4.1f} | Workers: {total_persons} | Compliant: {compliant_count}/{total_persons}"
    cv2.putText(out, hud_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 200), 2)

    ready_color = (0, 255, 0) if ppe_detector.is_ready else (0, 0, 255)
    cv2.putText(out, f"PPE Detector: {'ONLINE' if ppe_detector.is_ready else 'DEGRADED'}", (w - 240, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, ready_color, 2)

    return out


def main():
    parser = argparse.ArgumentParser(description="Week 5 PPE Detection Pipeline Test")
    parser.add_argument("--source", type=str, default="", help="Video source (default: from .env)")
    parser.add_argument("--no-display", action="store_true", help="Run headless without cv2.imshow")
    parser.add_argument("--seconds", type=int, default=0, help="Run for N seconds then exit")
    args = parser.parse_args()

    settings = get_settings()
    video_source_path = args.source if args.source else settings.VIDEO_SOURCE

    print("=" * 60)
    print("Week 5: Live PPE Detection Pipeline Test")
    print("=" * 60)
    print(f"Video Source:    {video_source_path}")
    print(f"Detector Model:  {settings.DETECTOR_MODEL}")
    print(f"PPE Model:       models/ppe_yolo11n.pt")

    ppe_detector = PPEDetector(
        model_path="models/ppe_yolo11n.pt",
        device=settings.DETECTOR_DEVICE,
        conf_threshold=0.30,
    )
    print(f"PPE Status:      {'Ready' if ppe_detector.is_ready else 'Not ready (degraded)'}")

    tracker = PersonTracker(
        model_path=settings.DETECTOR_MODEL,
        device=settings.DETECTOR_DEVICE,
        conf_threshold=settings.DETECTOR_CONF_THRESHOLD,
        img_size=settings.DETECTOR_IMG_SIZE,
        tracker_config=settings.TRACKER_CONFIG,
    )

    source = VideoSource(video_source_path, settings.SOURCE_FPS, settings.PROCESSING_FPS)
    if not source.open():
        print(f"[ERROR] Could not open video source: '{video_source_path}'")
        sys.exit(1)

    t_start = time.time()
    frame_count = 0
    t_prev = time.time()
    fps = 0.0

    print("\nStarting pipeline loop... Press 'q' to quit.")
    try:
        while True:
            res = source.read()
            if not res.ok:
                print("Stream ended or frame read failed — stopping.")
                break

            frame = res.frame
            frame_count += 1
            now = time.time()
            dt = now - t_prev
            t_prev = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps > 0 else (1.0 / dt)

            # 1. Track persons
            tracked_persons = tracker.track_frame(frame)

            # 2. Detect PPE items across frame
            ppe_detections = ppe_detector.detect_ppe(frame)

            # 3. Print occasional telemetry
            if frame_count % 15 == 0:
                print(f"  frame={frame_count:4d} | fps={fps:4.1f} | persons={len(tracked_persons)} | ppe_items={len(ppe_detections)}")

            # 4. Display overlay
            if not args.no_display:
                annotated = draw_ppe_overlay(frame, tracked_persons, ppe_detector, ppe_detections, fps)
                cv2.imshow("Week 5 - PPE Detection", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

            if args.seconds > 0 and (now - t_start) >= args.seconds:
                print(f"Completed duration target of {args.seconds} seconds.")
                break

    finally:
        source.release()
        if not args.no_display:
            cv2.destroyAllWindows()

    print(f"\nFinal Test Summary: Processed {frame_count} frames at average {fps:.1f} FPS.")
    print("PPE Detector Status:", ppe_detector.status())


if __name__ == "__main__":
    main()

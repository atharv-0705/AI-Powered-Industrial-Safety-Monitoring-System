"""
Manual exit-criteria test for Week 4 (SRS §16):
  "5 core activities recognized on test clips."

Pipeline: VideoSource -> PersonTracker -> PoseEstimator ->
TemporalFeatureManager -> ActivityRecognizer.

Modes:
  - Live Webcam Mode: Predicts ONLY standing, sitting, or walking based on X/Y/Z motion.
    (Climbing and running are strictly suppressed).
  - Video (.mp4) Mode: Full 5-class evaluation including climbing and running.

Usage:
  python backend/scripts/test_activity_recognition.py
  python backend/scripts/test_activity_recognition.py --source 0
  python backend/scripts/test_activity_recognition.py --source source/Alone-man-climbing-SnapYT.App.mp4
  python backend/scripts/test_activity_recognition.py --no-display --seconds 30
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from backend.app.core.config import get_settings
from backend.pipeline.detector import PersonTracker
from backend.pipeline.features import SEQUENCE_LENGTH, TemporalFeatureManager
from backend.pipeline.har import ActivityRecognizer, is_webcam_source
from backend.pipeline.ingestion import VideoSource
from backend.pipeline.pose import PoseEstimator


def main():
    parser = argparse.ArgumentParser(description="Human Activity Recognition (HAR) Pipeline Test")
    parser.add_argument("--source", type=str, default="", help="Video source (default: from .env)")
    parser.add_argument("--no-display", action="store_true", help="Run without cv2.imshow")
    parser.add_argument("--seconds", type=int, default=0, help="Run for N seconds then exit")
    args = parser.parse_args()

    settings = get_settings()
    video_source_path = args.source if args.source else settings.VIDEO_SOURCE
    is_webcam = is_webcam_source(video_source_path)

    print("=" * 60)
    print("Human Activity Recognition (HAR) Pipeline Test")
    print("=" * 60)
    print(f"Video Source:    {video_source_path}")
    print(f"HAR Mode:        {'WEBCAM (Standing / Sitting / Walking only)' if is_webcam else 'VIDEO / MP4 (5 classes: walking, running, standing, sitting, climbing)'}")
    print(f"Sequence Length: {SEQUENCE_LENGTH} frames")
    print(f"Model Path:      {settings.HAR_CHECKPOINT_PATH}")

    recognizer = ActivityRecognizer(
        settings.HAR_CHECKPOINT_PATH,
        settings.HAR_DEVICE,
        is_webcam=is_webcam,
    )

    if not recognizer.is_ready:
        print(f"Warning: No trained checkpoint found at '{settings.HAR_CHECKPOINT_PATH}'.")
        print("Continuing with posture/kinematic heuristics...\n")

    source = VideoSource(video_source_path, settings.SOURCE_FPS, settings.PROCESSING_FPS)
    if not source.open():
        print(f"[ERROR] Could not open video source: '{video_source_path}'")
        sys.exit(1)

    tracker = PersonTracker(
        model_path=settings.DETECTOR_MODEL,
        device=settings.DETECTOR_DEVICE,
        conf_threshold=settings.DETECTOR_CONF_THRESHOLD,
        img_size=settings.DETECTOR_IMG_SIZE,
        tracker_config=settings.TRACKER_CONFIG,
    )
    pose_estimator = PoseEstimator()
    feature_manager = TemporalFeatureManager()

    start = time.monotonic()
    last_print = start
    frame_count = 0

    print("\nStarting pipeline loop... Press 'q' to quit.\n")

    try:
        while True:
            frame_result = source.read()
            if not frame_result.ok:
                print("Stream ended or frame read failed — stopping.")
                break

            frame = frame_result.frame
            frame_count += 1
            h, w = frame.shape[:2]
            tracked_people = tracker.track_frame(frame)
            active_ids = set()

            for person in tracked_people:
                x1, y1, x2, y2 = (max(0, int(v)) for v in person.bbox_xyxy)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 - x1 < 20 or y2 - y1 < 20:
                    continue

                crop = frame[y1:y2, x1:x2]
                pose = pose_estimator.estimate(crop)
                if pose is None:
                    continue

                active_ids.add(person.track_id)
                buf = feature_manager.update(person.track_id, pose, person.bbox_xyxy, (w, h))

                label_text = f"ID {person.track_id} | buf {len(buf.features)}/{SEQUENCE_LENGTH}"
                if buf.is_full and recognizer.is_ready:
                    prediction = recognizer.predict(buf.as_array(), is_webcam=is_webcam)
                    if prediction:
                        label_text = f"ID {person.track_id} | {prediction.label.upper()} ({prediction.confidence:.2f})"
                        if frame_count % 20 == 0:
                            probs_str = ", ".join(f"{k}: {v:.0%}" for k, v in prediction.probabilities.items())
                            print(f"  [Frame {frame_count:4d}] Person #{person.track_id}: {prediction.label.upper()} ({probs_str})")

                if not args.no_display:
                    bx1, by1, bx2, by2 = (int(v) for v in person.bbox_xyxy)
                    # Color code by activity
                    box_color = (0, 220, 0)
                    cv2.rectangle(frame, (bx1, by1), (bx2, by2), box_color, 2)
                    cv2.putText(
                        frame,
                        label_text,
                        (bx1, max(20, by1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (255, 255, 255),
                        2,
                    )

            feature_manager.prune_stale(active_ids)

            if not args.no_display:
                # Top HUD Banner
                mode_label = "MODE: WEBCAM (STAND / SIT / WALK)" if is_webcam else "MODE: VIDEO (.MP4 - 5 CLASSES)"
                hud_text = f"{mode_label} | FPS: {tracker.inference_fps:<4.1f} | People: {len(tracked_people)}"
                cv2.rectangle(frame, (0, 0), (w, 32), (25, 25, 25), -1)
                cv2.putText(frame, hud_text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 200), 2)

                cv2.imshow("Activity Recognition (press q to quit)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            now = time.monotonic()
            if now - last_print >= 2.0:
                print(
                    f"  frame={frame_count:4d} | inference_fps={tracker.inference_fps:<5.1f} | "
                    f"tracked={len(tracked_people)} | har_ready={recognizer.is_ready}"
                )
                last_print = now

            if args.seconds and (now - start) >= args.seconds:
                print(f"Completed duration target of {args.seconds} seconds.")
                break

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        source.release()
        pose_estimator.close()
        if not args.no_display:
            cv2.destroyAllWindows()
        print("\nFinal Recognizer status:", recognizer.status())


if __name__ == "__main__":
    main()

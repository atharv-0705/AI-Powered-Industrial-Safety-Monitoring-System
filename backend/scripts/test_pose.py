"""
Manual exit-criteria test for Week 3 (SRS §16):
  "Pose overlays and stored temporal feature vectors."

Pipeline: VideoSource -> PersonTracker (YOLO11n+ByteTrack) -> crop per
track -> PoseEstimator -> TemporalFeatureManager (32-frame buffer/track).

Usage:
  python backend/scripts/test_pose.py
  python backend/scripts/test_pose.py --no-display --seconds 30
  python backend/scripts/test_pose.py --save-buffer 40   # dump the first track to
                                                          # reach a full 32-frame
                                                          # buffer as a .npy file,
                                                          # proving the exit criteria
"""
import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from backend.app.core.config import get_settings  # noqa: E402
from backend.pipeline.detector import PersonTracker  # noqa: E402
from backend.pipeline.features import TemporalFeatureManager  # noqa: E402
from backend.pipeline.pose import PoseEstimator  # noqa: E402
from backend.pipeline.ingestion import VideoSource  # noqa: E402

# MediaPipe's pose connections, indexed to match the 33-landmark layout
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),   # shoulders/arms
    (11, 23), (12, 24), (23, 24),                         # torso
    (23, 25), (25, 27), (24, 26), (26, 28),                # legs
]


def draw_pose_overlay(frame, bbox_xyxy, pose_landmarks, track_id, buffer_len):
    x1, y1, x2, y2 = (int(v) for v in bbox_xyxy)
    w, h = x2 - x1, y2 - y1
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)

    pts = [(int(x1 + lx * w), int(y1 + ly * h)) for lx, ly, *_ in pose_landmarks]
    for a, b in POSE_CONNECTIONS:
        cv2.line(frame, pts[a], pts[b], (255, 180, 0), 2)
    for p in pts:
        cv2.circle(frame, p, 2, (0, 0, 255), -1)

    label = f"ID {track_id} | buf {buffer_len}/32"
    cv2.putText(frame, label, (x1, max(0, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 0), 2)
    return frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--seconds", type=int, default=0)
    parser.add_argument("--save-buffer", type=int, default=0, metavar="SECONDS_TIMEOUT",
                         help="If >0, save the first track's completed 32-frame buffer to "
                              "a .npy file and exit, or give up after this many seconds.")
    args = parser.parse_args()

    settings = get_settings()

    source = VideoSource(settings.VIDEO_SOURCE, settings.SOURCE_FPS, settings.PROCESSING_FPS)
    if not source.open():
        print(f"FAILED to open video source: '{settings.VIDEO_SOURCE}'")
        sys.exit(1)

    print("Loading YOLO11n + ByteTrack + MediaPipe Pose ...")
    tracker = PersonTracker(
        model_path=settings.DETECTOR_MODEL,
        device=settings.DETECTOR_DEVICE,
        conf_threshold=settings.DETECTOR_CONF_THRESHOLD,
        img_size=settings.DETECTOR_IMG_SIZE,
        tracker_config=settings.TRACKER_CONFIG,
    )
    pose_estimator = PoseEstimator()
    feature_manager = TemporalFeatureManager()
    print(f"Detector device: {tracker.device}\n")

    start = time.monotonic()
    last_print = start
    saved = False

    try:
        while True:
            frame_result = source.read()
            if not frame_result.ok:
                print("Stream ended or frame read failed — stopping.")
                break

            frame = frame_result.frame
            frame_h, frame_w = frame.shape[:2]
            tracked_people = tracker.track_frame(frame)
            active_ids = set()

            for person in tracked_people:
                x1, y1, x2, y2 = (max(0, int(v)) for v in person.bbox_xyxy)
                x2, y2 = min(frame_w, x2), min(frame_h, y2)
                crop = frame[y1:y2, x1:x2]
                pose = pose_estimator.estimate(crop)
                if pose is None:
                    continue

                active_ids.add(person.track_id)
                buf = feature_manager.update(person.track_id, pose, person.bbox_xyxy, (frame_w, frame_h))

                if not args.no_display:
                    draw_pose_overlay(frame, person.bbox_xyxy, pose.landmarks, person.track_id, len(buf.features))

                if args.save_buffer and buf.is_full and not saved:
                    out_path = Path("buffer_example.npy")
                    np.save(out_path, buf.as_array())
                    print(f"\nSaved a full 32-frame buffer for track {person.track_id} "
                          f"-> {out_path} (shape={buf.as_array().shape})")
                    saved = True

            feature_manager.prune_stale(active_ids)

            if not args.no_display:
                cv2.imshow("MediaPipe Pose (press q to quit)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            now = time.monotonic()
            if now - last_print >= 1.0:
                status = feature_manager.status()
                print(
                    f"inference_fps={tracker.inference_fps:<6} "
                    f"active_buffers={status['active_buffers']:<3} "
                    f"ready_for_har={status['ready_for_har']}"
                )
                last_print = now

            if args.save_buffer and saved:
                break
            if args.save_buffer and (now - start) >= args.save_buffer:
                print("Timed out waiting for a full buffer — try again with a person "
                      "steadily in frame, or lower PROCESSING_FPS if pose is too slow to keep up.")
                break
            if args.seconds and (now - start) >= args.seconds:
                print("Reached --seconds limit — stopping.")
                break
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        source.release()
        pose_estimator.close()
        if not args.no_display:
            cv2.destroyAllWindows()
        print("\nFinal feature manager status:", feature_manager.status())


if __name__ == "__main__":
    main()

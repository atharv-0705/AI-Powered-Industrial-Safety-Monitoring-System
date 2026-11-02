"""
Manual exit-criteria test for Week 2 (SRS §16):
  "Tracked people with IDs and stable FPS measurement."

This measures TWO FPS numbers, deliberately kept separate:
  - ingestion_fps : how fast VideoSource is delivering frames
  - inference_fps : how fast YOLO11n+ByteTrack is processing them (this is
                    the number to compare against NFR-01's 10-15 FPS target)

Usage:
  python backend/scripts/test_tracking.py
  python backend/scripts/test_tracking.py --no-display --seconds 30
"""
import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import cv2  # noqa: E402

from backend.app.core.config import get_settings  # noqa: E402
from backend.pipeline.detector import PersonTracker  # noqa: E402
from backend.pipeline.ingestion import VideoSource  # noqa: E402


def draw_tracks(frame, tracked_people):
    for person in tracked_people:
        x1, y1, x2, y2 = (int(v) for v in person.bbox_xyxy)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
        label = f"ID {person.track_id} ({person.confidence:.2f})"
        cv2.putText(
            frame, label, (x1, max(0, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 0), 2,
        )
    return frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--seconds", type=int, default=0)
    args = parser.parse_args()

    settings = get_settings()

    source = VideoSource(
        source=settings.VIDEO_SOURCE,
        source_fps=settings.SOURCE_FPS,
        processing_fps=settings.PROCESSING_FPS,
    )
    if not source.open():
        print(f"FAILED to open video source: '{settings.VIDEO_SOURCE}'")
        sys.exit(1)

    print("Loading YOLO11n + ByteTrack ... (first run downloads weights)")
    tracker = PersonTracker(
        model_path=settings.DETECTOR_MODEL,
        device=settings.DETECTOR_DEVICE,
        conf_threshold=settings.DETECTOR_CONF_THRESHOLD,
        img_size=settings.DETECTOR_IMG_SIZE,
        tracker_config=settings.TRACKER_CONFIG,
    )
    print(f"Detector device: {tracker.device} | FP16: {tracker.half}\n")

    start = time.monotonic()
    last_print = start
    seen_track_ids: set[int] = set()

    try:
        while True:
            frame_result = source.read()
            if not frame_result.ok:
                print("Stream ended or frame read failed — stopping.")
                break

            tracked_people = tracker.track_frame(frame_result.frame)
            for p in tracked_people:
                seen_track_ids.add(p.track_id)

            if not args.no_display:
                annotated = draw_tracks(frame_result.frame, tracked_people)
                cv2.imshow("YOLO11n + ByteTrack (press q to quit)", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            now = time.monotonic()
            if now - last_print >= 1.0:
                ing = source.status()
                print(
                    f"ingestion_fps={ing['measured_fps']:<6} "
                    f"inference_fps={tracker.inference_fps:<6} "
                    f"active_tracks={len(tracked_people):<3} "
                    f"unique_ids_seen={len(seen_track_ids)}"
                )
                last_print = now

            if args.seconds and (now - start) >= args.seconds:
                print("Reached --seconds limit — stopping.")
                break
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        source.release()
        if not args.no_display:
            cv2.destroyAllWindows()
        print("\n=== Summary ===")
        print("Ingestion:", source.status())
        print("Tracker:  ", tracker.status())
        print(f"Unique track IDs observed: {sorted(seen_track_ids)}")


if __name__ == "__main__":
    main()

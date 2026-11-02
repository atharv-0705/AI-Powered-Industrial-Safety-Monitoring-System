"""
Manual exit-criteria test for FR-01/FR-03 (Week 1):
  "Video stream/file works" + processing FPS is measured, not assumed.

Usage:
  python backend/scripts/test_video_source.py                # shows a preview window
  python backend/scripts/test_video_source.py --no-display    # headless, prints FPS only
  python backend/scripts/test_video_source.py --seconds 15    # auto-stop after N seconds
"""
import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.core.config import get_settings  # noqa: E402
from backend.pipeline.ingestion import VideoSource  # noqa: E402

import cv2  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-display", action="store_true", help="Run headless (no preview window)")
    parser.add_argument("--seconds", type=int, default=0, help="Auto-stop after N seconds (0 = run until 'q' / Ctrl+C)")
    args = parser.parse_args()

    settings = get_settings()
    source = VideoSource(
        source=settings.VIDEO_SOURCE,
        source_fps=settings.SOURCE_FPS,
        processing_fps=settings.PROCESSING_FPS,
    )

    if not source.open():
        print(f"FAILED to open video source: '{settings.VIDEO_SOURCE}'")
        print("Check .env VIDEO_SOURCE — must be a webcam index (e.g. 0) or a valid file path.")
        sys.exit(1)

    print(f"Opened source '{settings.VIDEO_SOURCE}' — target processing FPS: {source.processing_fps}")
    print("Press 'q' in the preview window to quit (or Ctrl+C in headless mode).\n")

    start = time.monotonic()
    last_print = start
    try:
        while True:
            result = source.read()
            if not result.ok:
                print("Stream ended or frame read failed — stopping.")
                break

            if not args.no_display:
                cv2.imshow("Video Ingestion Test (press q to quit)", result.frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            now = time.monotonic()
            if now - last_print >= 1.0:
                s = source.status()
                print(
                    f"measured_fps={s['measured_fps']:<6} "
                    f"processed={s['processed_frames']:<6} "
                    f"dropped={s['dropped_frames']}"
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
        print("\nFinal status:", source.status())


if __name__ == "__main__":
    main()

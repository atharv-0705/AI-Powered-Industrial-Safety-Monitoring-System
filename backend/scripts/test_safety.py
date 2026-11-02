"""
Manual exit-criteria test for Weeks 6-7 (SRS §16, FR-09..FR-12):
  "Safety rules detect falls, missing PPE, zone intrusion, and dangerous climbing."

Full Pipeline:
  VideoSource -> PersonTracker -> PoseEstimator -> TemporalFeatureManager
  -> ActivityRecognizer -> PPEDetector -> SafetyEngine

Zone setup:
  Press 'z' to draw a restricted zone polygon on the video. Click points to
  define vertices, then press 'z' again to close the polygon and activate it.
  Press 'c' to clear all zones.

Usage:
  python backend/scripts/test_safety.py
  python backend/scripts/test_safety.py --no-display --seconds 30
  python backend/scripts/test_safety.py --source data/raw/walking/sample.avi
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
from backend.pipeline.ingestion import VideoSource
from backend.pipeline.pose import PoseEstimator
from backend.pipeline.features import TemporalFeatureManager
from backend.pipeline.har import ActivityRecognizer
from backend.pipeline.ppe import PPEDetector
from backend.pipeline.safety_engine import SafetyEngine, SafetyViolation, ZonePolygon


# ── Severity colors ─────────────────────────────────────────────────────────
SEVERITY_COLORS = {
    "LOW":      (0, 180, 0),     # Green
    "MEDIUM":   (0, 200, 255),   # Orange
    "HIGH":     (0, 100, 255),   # Red-orange
    "CRITICAL": (0, 0, 255),     # Red
}

VIOLATION_ICONS = {
    "FALL":            "⚠ FALL",
    "MISSING_HELMET":  "🔴 NO HELMET",
    "MISSING_VEST":    "🟠 NO VEST",
    "RESTRICTED_ZONE": "⛔ ZONE",
    "DANGEROUS_CLIMB": "⚠ CLIMB",
}


# ── Zone drawing state ──────────────────────────────────────────────────────
zone_drawing_mode = False
zone_points: list[tuple[int, int]] = []
zone_counter = 0


def mouse_callback(event, x, y, flags, param):
    global zone_points
    if zone_drawing_mode and event == cv2.EVENT_LBUTTONDOWN:
        zone_points.append((x, y))


def draw_safety_overlay(
    frame: np.ndarray,
    tracked_persons: list,
    activities: dict[int, str],
    ppe_statuses: dict,
    violations: list[SafetyViolation],
    zones: list[ZonePolygon],
    fps: float,
    zone_drawing: bool,
    zone_pts: list[tuple[int, int]],
) -> np.ndarray:
    """Renders full safety overlay: boxes, activities, PPE status, violation alerts, zones."""
    out = frame.copy()
    h, w = out.shape[:2]

    # ── Draw restricted zones ──
    for zone in zones:
        pts = np.array(zone.vertices, dtype=np.int32)
        cv2.polylines(out, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
        # Semi-transparent red fill
        overlay = out.copy()
        cv2.fillPoly(overlay, [pts], (0, 0, 180))
        cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)
        # Zone label
        cx = int(np.mean([v[0] for v in zone.vertices]))
        cy = int(np.mean([v[1] for v in zone.vertices]))
        cv2.putText(out, f"RESTRICTED: {zone.name}", (cx - 60, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # ── Draw zone-in-progress ──
    if zone_drawing and zone_pts:
        for i, pt in enumerate(zone_pts):
            cv2.circle(out, pt, 5, (255, 0, 255), -1)
            if i > 0:
                cv2.line(out, zone_pts[i - 1], pt, (255, 0, 255), 2)

    # ── Draw persons with activity + PPE ──
    violation_ids = {v.track_id for v in violations}
    for person in tracked_persons:
        tid = person.track_id
        px1, py1, px2, py2 = (int(v) for v in person.bbox_xyxy)

        # Box color based on violation status
        if tid in violation_ids:
            box_color = (0, 0, 255)  # Red for violations
        else:
            box_color = (0, 220, 0)  # Green for safe
        cv2.rectangle(out, (px1, py1), (px2, py2), box_color, 2)

        # Activity label
        activity = activities.get(tid, "...")
        label_y = max(20, py1 - 8)
        cv2.putText(out, f"#{tid} {activity}", (px1, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # PPE status
        ppe = ppe_statuses.get(tid)
        if ppe is not None:
            h_txt = "H:OK" if ppe.has_helmet else "H:NO"
            v_txt = "V:OK" if ppe.has_vest else "V:NO"
            h_col = (0, 255, 0) if ppe.has_helmet else (0, 0, 255)
            v_col = (0, 255, 0) if ppe.has_vest else (0, 0, 255)
            cv2.putText(out, h_txt, (px1, py2 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, h_col, 2)
            cv2.putText(out, v_txt, (px1 + 55, py2 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, v_col, 2)

    # ── Draw violation alerts ──
    alert_y = 65
    for v in violations:
        color = SEVERITY_COLORS.get(v.severity, (255, 255, 255))
        icon = VIOLATION_ICONS.get(v.violation_type, v.violation_type)
        alert_text = f"{icon} | ID #{v.track_id} | {v.severity} | {v.confidence:.0%}"

        # Alert background
        (tw, th), _ = cv2.getTextSize(alert_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(out, (8, alert_y - th - 4), (16 + tw, alert_y + 4), (30, 30, 30), -1)
        cv2.putText(out, alert_text, (12, alert_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        alert_y += th + 12

    # ── HUD bar ──
    cv2.rectangle(out, (0, 0), (w, 48), (20, 20, 20), -1)
    n_persons = len(tracked_persons)
    n_violations = len(violations)
    n_zones = len(zones)

    hud = f"FPS: {fps:4.1f} | Workers: {n_persons} | Violations: {n_violations} | Zones: {n_zones}"
    cv2.putText(out, hud, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 2)

    mode_text = "[Z] Draw Zone | [C] Clear Zones | [Q] Quit"
    if zone_drawing:
        mode_text = f"ZONE DRAWING: {len(zone_pts)} pts | [Z] Finish | [ESC] Cancel"
    cv2.putText(out, mode_text, (12, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

    return out


def main():
    global zone_drawing_mode, zone_points, zone_counter

    parser = argparse.ArgumentParser(description="Week 6-7 Safety Rules Pipeline Test")
    parser.add_argument("--source", type=str, default="", help="Video source (default: from .env)")
    parser.add_argument("--no-display", action="store_true", help="Run headless without cv2.imshow")
    parser.add_argument("--seconds", type=int, default=0, help="Run for N seconds then exit")
    args = parser.parse_args()

    settings = get_settings()
    video_source_path = args.source if args.source else settings.VIDEO_SOURCE

    print("=" * 60)
    print("Weeks 6-7: Live Safety Rules Pipeline Test")
    print("=" * 60)
    print(f"Video Source:    {video_source_path}")
    print(f"Detector Model:  {settings.DETECTOR_MODEL}")

    # ── Initialize pipeline components ──
    tracker = PersonTracker(
        model_path=settings.DETECTOR_MODEL,
        device=settings.DETECTOR_DEVICE,
        conf_threshold=settings.DETECTOR_CONF_THRESHOLD,
        img_size=settings.DETECTOR_IMG_SIZE,
        tracker_config=settings.TRACKER_CONFIG,
    )

    pose_estimator = PoseEstimator()
    feature_manager = TemporalFeatureManager()

    from backend.pipeline.har import is_webcam_source
    is_webcam = is_webcam_source(video_source_path)
    har = ActivityRecognizer(settings.HAR_CHECKPOINT_PATH, settings.HAR_DEVICE, is_webcam=is_webcam)
    print(f"HAR Status:      {'Ready' if har.is_ready else 'Degraded (no checkpoint)'} | Mode: {'Webcam (stand/sit/walk)' if is_webcam else 'Video (5 classes)'}")

    ppe_detector = PPEDetector(
        model_path="models/ppe_yolo11n.pt",
        device=settings.DETECTOR_DEVICE,
        conf_threshold=0.30,
    )
    print(f"PPE Status:      {'Ready' if ppe_detector.is_ready else 'Degraded (no model)'}")

    safety_engine = SafetyEngine(
        fall_frames_confirmation=5,
        zone_frames_confirmation=3,
        require_helmet=True,
        require_vest=True,
    )
    print(f"Safety Engine:   Active (4 rules)")

    source = VideoSource(video_source_path, settings.SOURCE_FPS, settings.PROCESSING_FPS)
    if not source.open():
        print(f"[ERROR] Could not open video source: '{video_source_path}'")
        sys.exit(1)

    if not args.no_display:
        cv2.namedWindow("Safety Rules Test", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("Safety Rules Test", mouse_callback)

    t_start = time.time()
    frame_count = 0
    fps = 0.0
    t_prev = time.time()
    total_violations = 0

    print("\nStarting pipeline loop... Press 'q' to quit.")
    print("  [Z] Toggle zone drawing | [C] Clear zones")
    print()

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

            frame_h, frame_w = frame.shape[:2]

            # 1. Track persons
            tracked_persons = tracker.track_frame(frame)

            # 2. Pose estimation + feature buffering + activity recognition
            poses: dict[int, object] = {}
            activities: dict[int, str] = {}
            for person in tracked_persons:
                x1, y1, x2, y2 = (int(v) for v in person.bbox_xyxy)
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(frame_w, x2)
                y2 = min(frame_h, y2)
                if x2 - x1 < 20 or y2 - y1 < 20:
                    continue

                crop = frame[y1:y2, x1:x2]
                pose_result = pose_estimator.estimate(crop)
                if pose_result is not None:
                    poses[person.track_id] = pose_result
                    buf = feature_manager.update(
                        person.track_id, pose_result, person.bbox_xyxy, (frame_w, frame_h)
                    )
                    if buf.is_full and har.is_ready:
                        pred = har.predict(buf.as_array(), is_webcam=is_webcam)
                        if pred:
                            activities[person.track_id] = pred.label

            feature_manager.prune_stale({p.track_id for p in tracked_persons})

            # 3. PPE detection
            ppe_statuses: dict[int, object] = {}
            if ppe_detector.is_ready:
                ppe_dets = ppe_detector.detect_ppe(frame)
                for person in tracked_persons:
                    ppe_statuses[person.track_id] = ppe_detector.associate_ppe_to_person(
                        person.track_id, person.bbox_xyxy, ppe_dets
                    )

            # 4. Safety engine evaluation
            violations = safety_engine.evaluate(
                tracked_persons, poses, activities, ppe_statuses, now
            )
            total_violations += len(violations)

            # Print violations to console
            for v in violations:
                print(f"  ⚠ [{v.severity}] {v.violation_type}: {v.description}")

            # 5. Telemetry
            if frame_count % 30 == 0:
                print(
                    f"  frame={frame_count:4d} | fps={fps:4.1f} | "
                    f"persons={len(tracked_persons)} | "
                    f"violations_this_frame={len(violations)} | "
                    f"total_violations={total_violations}"
                )

            # 6. Display
            if not args.no_display:
                annotated = draw_safety_overlay(
                    frame, tracked_persons, activities, ppe_statuses,
                    violations, safety_engine.restricted_zones,
                    fps, zone_drawing_mode, zone_points,
                )
                cv2.imshow("Safety Rules Test", annotated)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break
                elif key == ord("z"):
                    if not zone_drawing_mode:
                        zone_drawing_mode = True
                        zone_points = []
                        print("  Zone drawing: Click to add vertices, press 'z' to finish.")
                    else:
                        # Finish polygon
                        if len(zone_points) >= 3:
                            zone_counter += 1
                            zone = ZonePolygon(
                                name=f"Zone-{zone_counter}",
                                vertices=[(float(x), float(y)) for x, y in zone_points],
                            )
                            safety_engine.add_zone(zone)
                            print(f"  ✓ Created '{zone.name}' with {len(zone_points)} vertices.")
                        else:
                            print("  Need at least 3 points to create a zone.")
                        zone_drawing_mode = False
                        zone_points = []
                elif key == ord("c"):
                    safety_engine.clear_zones()
                    zone_counter = 0
                    print("  ✓ All zones cleared.")
                elif key == 27:  # ESC
                    if zone_drawing_mode:
                        zone_drawing_mode = False
                        zone_points = []
                        print("  Zone drawing cancelled.")

            if args.seconds > 0 and (now - t_start) >= args.seconds:
                print(f"Completed duration target of {args.seconds} seconds.")
                break

    finally:
        source.release()
        pose_estimator.close()
        if not args.no_display:
            cv2.destroyAllWindows()

    print(f"\n{'=' * 60}")
    print(f"Final Test Summary")
    print(f"{'=' * 60}")
    print(f"  Frames processed:   {frame_count}")
    print(f"  Average FPS:        {fps:.1f}")
    print(f"  Total violations:   {total_violations}")
    print(f"  Safety Engine:      {safety_engine.status()}")
    print(f"  HAR Status:         {'Ready' if har.is_ready else 'Degraded'}")
    print(f"  PPE Status:         {'Ready' if ppe_detector.is_ready else 'Degraded'}")


if __name__ == "__main__":
    main()

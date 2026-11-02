"""
Manual and automated exit-criteria test for Week 8 (SRS §16, FR-13..FR-15):
  "Composite deterministic risk scoring engine computes per-person (0-100)
   and scene-level threat metrics with explainable factor breakdown."

Key Formula & Factors:
  Risk = min(100, w1*ViolationSeverity + w2*ActivityRisk + w3*ZoneProximity + w4*Persistence)
  - Factor 1: Violation Severity (FALL: 60, CLIMB: 50, ZONE: 35, HELMET: 25, VEST: 15)
  - Factor 2: Activity Risk (climbing: +25, running: +20, walking: +5, standing/sitting: 0)
  - Factor 3: Zone Proximity (inside hazard zone: +35, near zone boundary: +15)
  - Factor 4: Persistence Escalation (+2.0 pts/sec of ongoing uncorrected violation)
  - Exponential Decay: Half-life = 3.0s on incident resolution (prevents UI flicker)
  - Scene Threat Assessment: max(PersonRisks) + 0.2 * avg(RemainingWorkers)

Interactive Controls:
  - Press 'z' to draw a hazard zone polygon with mouse clicks. Press 'z' again to close it.
  - Press 'c' to clear all zones.
  - Press 'q' to quit.

Usage:
  python backend/scripts/test_risk_engine.py --unit-tests
  python backend/scripts/test_risk_engine.py
  python backend/scripts/test_risk_engine.py --source source/cctv_27c12fe4.mp4
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from backend.app.core.config import get_settings
from backend.pipeline.detector import PersonTracker, TrackedPerson
from backend.pipeline.features import SEQUENCE_LENGTH, TemporalFeatureManager
from backend.pipeline.har import ActivityRecognizer, is_webcam_source
from backend.pipeline.ingestion import VideoSource
from backend.pipeline.pose import PoseEstimator
from backend.pipeline.ppe import PPEDetector
from backend.pipeline.risk_engine import RiskEngine, RiskScore, SceneRiskScore
from backend.pipeline.safety_engine import SafetyEngine, SafetyViolation, ZonePolygon


# ── Color mappings for Risk Levels ──────────────────────────────────────────
RISK_COLORS = {
    "LOW":      (0, 200, 0),      # Green
    "MEDIUM":   (0, 215, 255),    # Yellow-Gold
    "HIGH":     (0, 100, 255),    # Orange
    "CRITICAL": (0, 0, 255),      # Red
}

# ── Zone drawing interactive state ──
zone_drawing_mode = False
zone_points: list[tuple[int, int]] = []
zone_counter = 0


def mouse_callback(event, x, y, flags, param):
    global zone_points
    if zone_drawing_mode and event == cv2.EVENT_LBUTTONDOWN:
        zone_points.append((x, y))


def run_unit_tests() -> bool:
    """Executes automated verification of all Risk Engine mathematical properties."""
    print("=" * 65)
    print("Week 8: Running Automated Risk Engine Unit Tests (FR-13..FR-15)")
    print("=" * 65)

    engine = RiskEngine()
    ts = 100.0

    # ── Test 1: LOW RISK (Compliant worker standing) ──
    r1 = engine.compute_person_risk(
        track_id=1,
        violations=[],
        activity="standing",
        in_hazard_zone=False,
        timestamp=ts,
    )
    print(f"Test 1 [Compliant Worker]: Score={r1.score:.1f} | Level={r1.level}")
    assert r1.score == 0.0, f"Expected 0.0, got {r1.score}"
    assert r1.level == "LOW", f"Expected LOW, got {r1.level}"

    # ── Test 2: Factor 1 + Factor 2 (Missing vest while walking) ──
    v_vest = SafetyViolation(
        violation_type="MISSING_VEST",
        track_id=2,
        severity="MEDIUM",
        confidence=0.9,
        description="Missing high-vis vest",
        timestamp=ts,
        bbox_xyxy=(10, 10, 50, 100),
    )
    r2 = engine.compute_person_risk(
        track_id=2,
        violations=[v_vest],
        activity="walking",
        in_hazard_zone=False,
        timestamp=ts,
    )
    # vest (15) + walking (5) = 20 pts -> LOW
    print(f"Test 2 [Missing Vest + Walking]: Score={r2.score:.1f} | Level={r2.level}")
    assert r2.score == 20.0, f"Expected 20.0, got {r2.score}"

    # ── Test 3: Factor 3 (Zone Proximity & Intrusion) ──
    # Proximity near boundary (+15 pts) vs inside hazard zone (+35 pts)
    r_near = engine.compute_person_risk(
        track_id=5,
        violations=[],
        activity="walking",
        in_hazard_zone=False,
        near_hazard_zone=True,
        timestamp=ts,
    )
    # near_zone (15) + walking (5) = 20 pts
    print(f"Test 3a [Zone Proximity Boundary]: Score={r_near.score:.1f} | Factors={r_near.contributing_factors}")
    assert r_near.zone_score == 15.0

    v_helmet = SafetyViolation(
        violation_type="MISSING_HELMET",
        track_id=3,
        severity="HIGH",
        confidence=0.9,
        description="Missing safety helmet",
        timestamp=ts,
        bbox_xyxy=(10, 10, 50, 100),
    )
    v_zone = SafetyViolation(
        violation_type="RESTRICTED_ZONE",
        track_id=3,
        severity="HIGH",
        confidence=0.9,
        description="Inside restricted zone",
        timestamp=ts,
        bbox_xyxy=(10, 10, 50, 100),
    )
    r3 = engine.compute_person_risk(
        track_id=3,
        violations=[v_helmet, v_zone],
        activity="walking",
        in_hazard_zone=True,
        timestamp=ts,
    )
    # helmet (25) + zone_viol (35) + in_zone (35) + walking (5) = 100 -> CRITICAL
    print(f"Test 3b [No Helmet + In Hazard Zone]: Score={r3.score:.1f} | Level={r3.level}")
    assert r3.level == "CRITICAL"
    assert r3.score == 100.0

    # ── Test 4: Critical Fall Emergency ──
    v_fall = SafetyViolation(
        violation_type="FALL",
        track_id=4,
        severity="CRITICAL",
        confidence=0.95,
        description="Fall detected",
        timestamp=ts,
        bbox_xyxy=(10, 10, 100, 40),
    )
    r4 = engine.compute_person_risk(
        track_id=4,
        violations=[v_fall],
        activity="sitting",
        in_hazard_zone=False,
        timestamp=ts,
    )
    print(f"Test 4 [Fall Emergency]: Score={r4.score:.1f} | Level={r4.level}")
    assert r4.score == 60.0
    assert r4.level == "HIGH"

    # ── Test 5: Factor 4 Persistence Escalation (+2.0 pts/sec) ──
    # Person 2 with missing vest continues unresolved for 6 seconds
    r2_escalated = engine.compute_person_risk(
        track_id=2,
        violations=[v_vest],
        activity="walking",
        in_hazard_zone=False,
        timestamp=ts + 6.0,
    )
    # 20 base + 6s * 2.0 pts/sec = 32 pts -> transitions to MEDIUM!
    print(f"Test 5 [Persistence Escalation +6s]: Score={r2_escalated.score:.1f} | Level={r2_escalated.level}")
    assert r2_escalated.score == 32.0, f"Expected 32.0, got {r2_escalated.score}"
    assert r2_escalated.level == "MEDIUM"

    # ── Test 6: Exponential Decay on Resolution (Half-Life = 3.0s) ──
    # Person 2 puts on vest at t = ts + 9.0s (3s after escalation)
    r2_resolved = engine.compute_person_risk(
        track_id=2,
        violations=[],
        activity="standing",
        in_hazard_zone=False,
        timestamp=ts + 9.0,
    )
    # Decayed from 32 by ~1 half-life (3s) -> ~16 pts residual
    print(f"Test 6 [Resolution Half-Life Decay]: Score={r2_resolved.score:.1f} | Level={r2_resolved.level}")
    assert 14.0 <= r2_resolved.score <= 18.0, f"Expected ~16.0, got {r2_resolved.score}"

    # ── Test 7: Scene-Level Composite Aggregation (FR-15) ──
    scene = engine.compute_scene_risk(
        person_risks=[r1, r3, r4],
        all_violations=[v_helmet, v_zone, v_fall],
        timestamp=ts,
    )
    print(f"Test 7 [Scene Aggregation]: Overall={scene.overall_score:.1f} | Level={scene.overall_level}")
    print(f"        Summary: {scene.summary}")
    assert scene.overall_level == "CRITICAL"
    assert scene.workers_at_risk >= 2
    assert scene.critical_workers >= 1
    assert scene.highest_risk_track_id == 3

    print("\n✓ ALL 7 UNIT TESTS PASSED SUCCESSFULLY!\n")
    return True


def draw_risk_hud(
    frame: np.ndarray,
    tracked_persons: list[TrackedPerson],
    activities: dict[int, str],
    ppe_statuses: dict,
    violations: list[SafetyViolation],
    person_risks: dict[int, RiskScore],
    scene_risk: SceneRiskScore,
    zones: list[ZonePolygon],
    fps: float,
    is_drawing: bool,
    draw_pts: list[tuple[int, int]],
) -> np.ndarray:
    """Renders comprehensive HUD with worker risk tags, scene gauge, zone overlays, and factor audit."""
    out = frame.copy()
    h, w = out.shape[:2]

    # ── 1. Draw Zones & Proximity Buffers ──
    for zone in zones:
        pts = np.array(zone.vertices, dtype=np.int32)
        # Red hazard polygon
        cv2.polylines(out, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
        overlay = out.copy()
        cv2.fillPoly(overlay, [pts], (0, 0, 180))
        cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)

        # Proximity buffer (perimeter line)
        cv2.polylines(out, [pts], isClosed=True, color=(0, 200, 255), thickness=1)

        cx = int(np.mean([v[0] for v in zone.vertices]))
        cy = int(np.mean([v[1] for v in zone.vertices]))
        cv2.putText(out, f"HAZARD: {zone.name} (+35 pts)", (cx - 70, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 0, 255), 2)

    # In-progress zone drawing
    if is_drawing and draw_pts:
        for i, pt in enumerate(draw_pts):
            cv2.circle(out, pt, 5, (255, 0, 255), -1)
            if i > 0:
                cv2.line(out, draw_pts[i - 1], pt, (255, 0, 255), 2)

    # ── 2. Top Scene Threat Bar & Gauge ──
    scene_color = RISK_COLORS.get(scene_risk.overall_level, (200, 200, 200))
    cv2.rectangle(out, (0, 0), (w, 54), (20, 20, 20), -1)

    # Scene Threat Gauge
    gauge_w = 180
    gauge_h = 16
    gauge_x = w - gauge_w - 20
    gauge_y = 18
    cv2.rectangle(out, (gauge_x, gauge_y), (gauge_x + gauge_w, gauge_y + gauge_h), (50, 50, 50), -1)
    fill_w = int(gauge_w * (scene_risk.overall_score / 100.0))
    if fill_w > 0:
        cv2.rectangle(out, (gauge_x, gauge_y), (gauge_x + fill_w, gauge_y + gauge_h), scene_color, -1)
    cv2.rectangle(out, (gauge_x, gauge_y), (gauge_x + gauge_w, gauge_y + gauge_h), (255, 255, 255), 1)

    gauge_label = f"SCENE THREAT: {scene_risk.overall_score:.1f} [{scene_risk.overall_level}]"
    cv2.putText(out, gauge_label, (gauge_x, gauge_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, scene_color, 1)

    # Top Telemetry
    hud_main = f"FPS: {fps:4.1f} | Workers: {scene_risk.total_workers} | At-Risk: {scene_risk.workers_at_risk} | Violations: {scene_risk.active_violations_count}"
    cv2.putText(out, hud_main, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 200), 2)
    cv2.putText(out, scene_risk.summary, (12, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

    # ── 3. Per-Person Bounding Boxes & Risk Badges ──
    for person in tracked_persons:
        tid = person.track_id
        px1, py1, px2, py2 = (int(v) for v in person.bbox_xyxy)
        risk = person_risks.get(tid)

        score_val = risk.score if risk else 0.0
        level_str = risk.level if risk else "LOW"
        color = RISK_COLORS.get(level_str, (0, 200, 0))

        # Person bounding box
        box_thickness = 3 if level_str in ("HIGH", "CRITICAL") else 2
        cv2.rectangle(out, (px1, py1), (px2, py2), color, box_thickness)

        # Header Badge: ID + Activity + Risk Score
        act_label = activities.get(tid, "...")
        tag_text = f"#{tid} {act_label.upper()} | RISK: {score_val:.0f} [{level_str}]"
        (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 2)
        tag_y = max(th + 6, py1 - 8)
        cv2.rectangle(out, (px1, tag_y - th - 4), (px1 + tw + 6, tag_y + 4), (25, 25, 25), -1)
        cv2.putText(out, tag_text, (px1 + 3, tag_y), cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 2)

        # PPE badges
        ppe = ppe_statuses.get(tid)
        if ppe:
            h_col = (0, 255, 0) if ppe.has_helmet else (0, 0, 255)
            v_col = (0, 255, 0) if ppe.has_vest else (0, 0, 255)
            cv2.putText(out, "H:OK" if ppe.has_helmet else "NO HELMET",
                        (px1, py2 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, h_col, 2)
            cv2.putText(out, "V:OK" if ppe.has_vest else "NO VEST",
                        (px1 + 90, py2 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, v_col, 2)

        # Contributing factor details for transparency
        if risk and risk.contributing_factors:
            offset_y = py2 + 36
            for factor in risk.contributing_factors[:2]:  # show top 2 factors
                cv2.putText(out, factor, (px1, offset_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)
                offset_y += 14

    return out


def main():
    global zone_drawing_mode, zone_points, zone_counter

    parser = argparse.ArgumentParser(description="Week 8 Risk Scoring Engine Test")
    parser.add_argument("--unit-tests", action="store_true", help="Run automated mathematical unit tests only")
    parser.add_argument("--source", type=str, default="", help="Video source (default: from .env)")
    parser.add_argument("--no-display", action="store_true", help="Run headless without cv2.imshow")
    parser.add_argument("--seconds", type=int, default=0, help="Run for N seconds then exit")
    args = parser.parse_args()

    if args.unit_tests:
        run_unit_tests()
        return

    settings = get_settings()
    video_source_path = args.source if args.source else settings.VIDEO_SOURCE
    is_webcam = is_webcam_source(video_source_path)

    # Always verify unit tests first
    run_unit_tests()

    print("=" * 65)
    print("Week 8: Live Risk Scoring Engine Pipeline Test")
    print("=" * 65)
    print(f"Video Source:    {video_source_path}")
    print(f"Mode:            {'Webcam' if is_webcam else 'Video File (.mp4)'}")
    print(f"Detector Model:  {settings.DETECTOR_MODEL}")

    tracker = PersonTracker(
        model_path=settings.DETECTOR_MODEL,
        device=settings.DETECTOR_DEVICE,
        conf_threshold=settings.DETECTOR_CONF_THRESHOLD,
        img_size=settings.DETECTOR_IMG_SIZE,
        tracker_config=settings.TRACKER_CONFIG,
    )
    pose_estimator = PoseEstimator()
    feature_manager = TemporalFeatureManager()
    har = ActivityRecognizer(settings.HAR_CHECKPOINT_PATH, settings.HAR_DEVICE, is_webcam=is_webcam)
    ppe_detector = PPEDetector(model_path="models/ppe_yolo11n.pt", device=settings.DETECTOR_DEVICE, conf_threshold=0.30)
    safety_engine = SafetyEngine(fall_frames_confirmation=5, zone_frames_confirmation=3)
    risk_engine = RiskEngine()

    source = VideoSource(video_source_path, settings.SOURCE_FPS, settings.PROCESSING_FPS)
    if not source.open():
        print(f"[ERROR] Could not open video source: '{video_source_path}'")
        sys.exit(1)

    if not args.no_display:
        cv2.namedWindow("Week 8 - Risk Scoring Engine", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("Week 8 - Risk Scoring Engine", mouse_callback)

    t_start = time.time()
    frame_count = 0
    fps = 0.0
    t_prev = time.time()

    print("\nStarting pipeline loop... Press 'q' to quit.")
    print("  [Z] Toggle hazard zone drawing | [C] Clear zones\n")

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

            # 2. Pose + Features + Activity
            poses = {}
            activities = {}
            for person in tracked_persons:
                x1, y1, x2, y2 = (int(v) for v in person.bbox_xyxy)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame_w, x2), min(frame_h, y2)
                if x2 - x1 < 20 or y2 - y1 < 20:
                    continue

                crop = frame[y1:y2, x1:x2]
                pose_result = pose_estimator.estimate(crop)
                if pose_result is not None:
                    poses[person.track_id] = pose_result
                    buf = feature_manager.update(person.track_id, pose_result, person.bbox_xyxy, (frame_w, frame_h))
                    if buf.is_full and har.is_ready:
                        pred = har.predict(buf.as_array(), is_webcam=is_webcam)
                        if pred:
                            activities[person.track_id] = pred.label

            feature_manager.prune_stale({p.track_id for p in tracked_persons})

            # 3. PPE detection
            ppe_statuses = {}
            if ppe_detector.is_ready:
                ppe_dets = ppe_detector.detect_ppe(frame)
                for person in tracked_persons:
                    ppe_statuses[person.track_id] = ppe_detector.associate_ppe_to_person(
                        person.track_id, person.bbox_xyxy, ppe_dets
                    )

            # 4. Safety rule evaluation
            violations = safety_engine.evaluate(tracked_persons, poses, activities, ppe_statuses, now)

            # 5. Zone Proximity evaluation (Factor 3)
            in_hazard_zones = {
                p.track_id: any(v.track_id == p.track_id and v.violation_type == "RESTRICTED_ZONE" for v in violations)
                for p in tracked_persons
            }
            near_hazard_zones = {}
            if safety_engine.restricted_zones:
                for p in tracked_persons:
                    bx = (p.bbox_xyxy[0] + p.bbox_xyxy[2]) / 2.0
                    by = p.bbox_xyxy[3]  # foot point
                    is_near = False
                    for zone in safety_engine.restricted_zones:
                        for vx, vy in zone.vertices:
                            if math.hypot(bx - vx, by - vy) < 80.0:
                                is_near = True
                                break
                        if is_near:
                            break
                    near_hazard_zones[p.track_id] = is_near and not in_hazard_zones.get(p.track_id, False)

            # 6. Risk Scoring Engine evaluation (FR-13..FR-15)
            person_risks, scene_risk = risk_engine.evaluate(
                tracked_persons, violations, activities, in_hazard_zones, now,
                near_hazard_zones=near_hazard_zones,
            )

            # Telemetry logging every 30 frames
            if frame_count % 30 == 0:
                print(
                    f"  frame={frame_count:4d} | fps={fps:4.1f} | workers={len(tracked_persons)} | "
                    f"scene_risk={scene_risk.overall_score:.1f} [{scene_risk.overall_level}] | "
                    f"at_risk={scene_risk.workers_at_risk} | violations={len(violations)}"
                )

            # Display
            if not args.no_display:
                annotated = draw_risk_hud(
                    frame, tracked_persons, activities, ppe_statuses,
                    violations, person_risks, scene_risk, safety_engine.restricted_zones,
                    fps, zone_drawing_mode, zone_points,
                )
                cv2.imshow("Week 8 - Risk Scoring Engine", annotated)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break
                elif key == ord("z"):
                    if not zone_drawing_mode:
                        zone_drawing_mode = True
                        zone_points = []
                        print("  Hazard zone drawing: Click to add vertices, press 'z' to finish.")
                    else:
                        if len(zone_points) >= 3:
                            zone_counter += 1
                            zone = ZonePolygon(
                                name=f"Hazard-{zone_counter}",
                                vertices=[(float(x), float(y)) for x, y in zone_points],
                                zone_type="hazard",
                            )
                            safety_engine.add_zone(zone)
                            print(f"  ✓ Created hazard zone '{zone.name}' (+35 inside / +15 near).")
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

    print("\n" + "=" * 65)
    print("Final Pipeline Summary:")
    print(f"  Processed {frame_count} frames at {fps:.1f} FPS.")
    print("  Risk Engine Status:", risk_engine.status())


if __name__ == "__main__":
    main()

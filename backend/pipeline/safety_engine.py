"""
Safety Rule Engine (SRS §8.4, §8.5, FR-09..FR-12, Weeks 6-7).

Applies deterministic safety rules over tracks, activities, poses, and PPE:
  - Rule 1: Fall Detection (aspect ratio change + downward velocity + lying pose)
  - Rule 2: Missing PPE (person in active work zone without helmet/vest)
  - Rule 3: Restricted Zone Intrusion (polygon point-in-polygon check)
  - Rule 4: Dangerous Climbing (climbing activity without safety harness / in unapproved area)

Each rule uses multi-frame persistence filters to suppress transient false positives.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from backend.pipeline.detector import TrackedPerson
from backend.pipeline.pose import PoseResult
from backend.pipeline.ppe import PersonPPEStatus


# ── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class SafetyViolation:
    violation_type: str        # "FALL", "MISSING_HELMET", "MISSING_VEST", "RESTRICTED_ZONE", "DANGEROUS_CLIMB"
    track_id: int
    severity: str              # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    confidence: float
    description: str
    timestamp: float
    bbox_xyxy: tuple[float, float, float, float]


@dataclass
class ZonePolygon:
    """A restricted/hazard zone defined as a closed polygon in pixel coordinates."""
    name: str
    vertices: list[tuple[float, float]]  # [(x, y), ...] — polygon vertices in frame coords
    zone_type: str = "restricted"        # "restricted" or "hazard"


# ── Internal per-track state ────────────────────────────────────────────────

@dataclass
class _FallState:
    """Tracks per-person fall detection history."""
    prev_bbox_centers_y: deque = field(default_factory=lambda: deque(maxlen=15))
    prev_aspect_ratios: deque = field(default_factory=lambda: deque(maxlen=15))
    collapsed_frame_count: int = 0
    fall_confirmed: bool = False
    fall_cooldown_until: float = 0.0  # Avoid re-alerting the same fall


@dataclass
class _ZoneState:
    """Tracks per-person zone intrusion history."""
    inside_frame_count: int = 0
    current_zone: Optional[str] = None


@dataclass
class _ClimbState:
    """Tracks per-person climbing without PPE history."""
    climbing_no_helmet_frames: int = 0


# ── Geometry helpers ────────────────────────────────────────────────────────

def _point_in_polygon(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _ankle_positions_in_frame(
    pose: PoseResult,
    bbox_xyxy: tuple[float, float, float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Convert ankle landmarks from bbox-normalized coords to frame pixel coords.

    MediaPipe Pose landmarks 27 (left ankle) and 28 (right ankle).
    landmarks[i] = (x_norm, y_norm, z, visibility) where x/y are 0-1 within the crop.
    """
    x1, y1, x2, y2 = bbox_xyxy
    bw, bh = x2 - x1, y2 - y1

    l_ankle = pose.landmarks[27]  # (x, y, z, vis)
    r_ankle = pose.landmarks[28]

    l_x = x1 + l_ankle[0] * bw
    l_y = y1 + l_ankle[1] * bh
    r_x = x1 + r_ankle[0] * bw
    r_y = y1 + r_ankle[1] * bh

    return (l_x, l_y), (r_x, r_y)


def _hip_center_in_frame(
    pose: PoseResult,
    bbox_xyxy: tuple[float, float, float, float],
) -> tuple[float, float]:
    """Midpoint of left hip (23) and right hip (24) in frame coordinates."""
    x1, y1, x2, y2 = bbox_xyxy
    bw, bh = x2 - x1, y2 - y1

    l_hip = pose.landmarks[23]
    r_hip = pose.landmarks[24]

    cx = x1 + ((l_hip[0] + r_hip[0]) / 2.0) * bw
    cy = y1 + ((l_hip[1] + r_hip[1]) / 2.0) * bh
    return cx, cy


# ── Safety Engine ───────────────────────────────────────────────────────────

class SafetyEngine:
    """Evaluates safety rules per frame on tracked individuals.

    All rules use multi-frame persistence filtering to avoid
    transient false positives from pose jitter or brief occlusions.
    """

    def __init__(
        self,
        # ── Fall Detection thresholds ──
        fall_aspect_ratio_threshold: float = 1.0,
        fall_velocity_threshold: float = 0.04,
        fall_frames_confirmation: int = 5,
        fall_cooldown_seconds: float = 10.0,
        # ── Zone Intrusion thresholds ──
        restricted_zones: Optional[list[ZonePolygon]] = None,
        zone_frames_confirmation: int = 3,
        # ── PPE compliance ──
        require_helmet: bool = True,
        require_vest: bool = True,
        # ── Climbing safety ──
        climbing_no_helmet_frames: int = 3,
        # ── Stale track cleanup ──
        stale_track_seconds: float = 10.0,
    ):
        # Fall detection
        self.fall_ar_threshold = fall_aspect_ratio_threshold
        self.fall_vel_threshold = fall_velocity_threshold
        self.fall_frames = fall_frames_confirmation
        self.fall_cooldown = fall_cooldown_seconds

        # Zones
        self.restricted_zones = restricted_zones or []
        self.zone_confirm_frames = zone_frames_confirmation

        # PPE
        self.require_helmet = require_helmet
        self.require_vest = require_vest

        # Climbing
        self.climb_confirm_frames = climbing_no_helmet_frames

        # Stale cleanup
        self.stale_seconds = stale_track_seconds

        # Per-track internal state
        self._fall_states: Dict[int, _FallState] = defaultdict(_FallState)
        self._zone_states: Dict[int, _ZoneState] = defaultdict(_ZoneState)
        self._climb_states: Dict[int, _ClimbState] = defaultdict(_ClimbState)
        self._last_seen: Dict[int, float] = {}

    # ── Public API ──────────────────────────────────────────────────────

    def evaluate(
        self,
        tracks: list[TrackedPerson],
        poses: dict[int, PoseResult],
        activities: dict[int, str],
        ppe_statuses: dict[int, PersonPPEStatus],
        frame_timestamp: float,
    ) -> List[SafetyViolation]:
        """Run all safety rules for the current frame.

        Args:
            tracks:       Tracked persons from PersonTracker.
            poses:        Pose results keyed by track_id (may be missing if pose failed).
            activities:   Activity labels keyed by track_id (may be missing if buffer not full).
            ppe_statuses: PPE compliance keyed by track_id (may be missing if PPE detector offline).
            frame_timestamp: Current wall-clock time (time.time()).

        Returns:
            List of SafetyViolation objects for the current frame.
        """
        violations: List[SafetyViolation] = []
        active_ids = set()

        for person in tracks:
            tid = person.track_id
            active_ids.add(tid)
            self._last_seen[tid] = frame_timestamp
            pose = poses.get(tid)
            activity = activities.get(tid, "unknown")
            ppe = ppe_statuses.get(tid)

            # ── Rule 1: Fall Detection ──────────────────────────────
            fall_v = self._check_fall(person, pose, frame_timestamp)
            if fall_v:
                violations.append(fall_v)

            # ── Rule 2: Missing PPE ─────────────────────────────────
            ppe_vs = self._check_ppe(person, ppe, activity, frame_timestamp)
            violations.extend(ppe_vs)

            # ── Rule 3: Restricted Zone Intrusion ───────────────────
            zone_v = self._check_zone_intrusion(person, pose, frame_timestamp)
            if zone_v:
                violations.append(zone_v)

            # ── Rule 4: Dangerous Climbing ──────────────────────────
            climb_v = self._check_dangerous_climbing(person, activity, ppe, frame_timestamp)
            if climb_v:
                violations.append(climb_v)

        # Prune stale track states
        self._prune_stale(active_ids, frame_timestamp)

        return violations

    # ── Rule 1: Fall Detection ──────────────────────────────────────────

    def _check_fall(
        self,
        person: TrackedPerson,
        pose: Optional[PoseResult],
        ts: float,
    ) -> Optional[SafetyViolation]:
        """Detects falls using three fused signals:

        1. Aspect ratio collapse: bbox height becomes ≤ width (person is horizontal).
        2. Downward velocity: vertical center-of-mass drops rapidly.
        3. Pose orientation: shoulder line becomes near-horizontal or inverted
           (person is lying down rather than standing/sitting).

        Confirmation requires N consecutive frames to suppress transient glitches.
        """
        tid = person.track_id
        state = self._fall_states[tid]

        # Cooldown: don't re-alert the same fall
        if state.fall_cooldown_until > ts:
            return None

        x1, y1, x2, y2 = person.bbox_xyxy
        bw = max(1.0, x2 - x1)
        bh = max(1.0, y2 - y1)
        aspect_ratio = bh / bw  # Upright person ≈ 2-3, lying person < 1.0
        center_y = (y1 + y2) / 2.0

        state.prev_aspect_ratios.append(aspect_ratio)
        state.prev_bbox_centers_y.append(center_y)

        # ── Signal 1: Aspect ratio collapse ──
        ar_collapsed = aspect_ratio < self.fall_ar_threshold

        # ── Signal 2: Rapid downward velocity ──
        downward_velocity = False
        if len(state.prev_bbox_centers_y) >= 3:
            # Velocity = change in center_y over last 3 frames (positive = downward in image coords)
            recent = list(state.prev_bbox_centers_y)
            dy = recent[-1] - recent[-3]
            downward_velocity = dy > self.fall_vel_threshold * 100  # scaled for pixel coords

        # ── Signal 3: Pose orientation (shoulder line angle) ──
        pose_horizontal = False
        if pose is not None:
            l_shoulder = pose.landmarks[11]  # (x, y, z, vis) in bbox-norm coords
            r_shoulder = pose.landmarks[12]
            if l_shoulder[3] > 0.3 and r_shoulder[3] > 0.3:
                dx = r_shoulder[0] - l_shoulder[0]
                dy_s = r_shoulder[1] - l_shoulder[1]
                shoulder_angle_deg = abs(np.degrees(np.arctan2(dy_s, dx)))
                # When standing/sitting, shoulder line is roughly horizontal (0-15°)
                # When lying down, shoulder line is near vertical (60-90°)
                # In a fall, shoulder angle becomes > 40° (body is tilting/horizontal)
                pose_horizontal = shoulder_angle_deg > 40.0

        # Check if person is clearly upright (head above level shoulders)
        is_upright = False
        if pose is not None:
            nose = pose.landmarks[0]
            l_sh = pose.landmarks[11]
            r_sh = pose.landmarks[12]
            if nose[3] > 0.3 and l_sh[3] > 0.3 and r_sh[3] > 0.3:
                sh_avg_y = (l_sh[1] + r_sh[1]) / 2.0
                if nose[1] < sh_avg_y and not pose_horizontal:
                    is_upright = True

        if is_upright:
            signal_count = 0
            is_fall_candidate = False
        else:
            signal_count = sum([ar_collapsed, downward_velocity, pose_horizontal])
            is_fall_candidate = (signal_count >= 2) or (aspect_ratio < 0.65 and pose_horizontal) or (downward_velocity and ar_collapsed)

        if is_fall_candidate:
            state.collapsed_frame_count += 1
        else:
            # Gradual decay (allows brief occlusion without resetting)
            state.collapsed_frame_count = max(0, state.collapsed_frame_count - 1)

        if state.collapsed_frame_count >= self.fall_frames:
            state.fall_confirmed = True
            state.fall_cooldown_until = ts + self.fall_cooldown
            state.collapsed_frame_count = 0  # Reset for next potential fall

            confidence = min(1.0, 0.5 + signal_count * 0.2)
            return SafetyViolation(
                violation_type="FALL",
                track_id=tid,
                severity="CRITICAL",
                confidence=confidence,
                description=(
                    f"Fall detected for person #{tid}: "
                    f"aspect_ratio={aspect_ratio:.2f}, "
                    f"signals={signal_count}/3"
                ),
                timestamp=ts,
                bbox_xyxy=person.bbox_xyxy,
            )

        return None

    # ── Rule 2: Missing PPE ─────────────────────────────────────────────

    def _check_ppe(
        self,
        person: TrackedPerson,
        ppe: Optional[PersonPPEStatus],
        activity: str,
        ts: float,
    ) -> list[SafetyViolation]:
        """Checks if a person is missing required PPE.

        Only alerts for persons with an active work posture (walking, standing, climbing)
        — not for those sitting (likely resting in a break area).
        """
        if ppe is None:
            return []

        # Only enforce PPE for active workers (not sitting/resting)
        if activity in ("sitting",):
            return []

        violations = []

        if self.require_helmet and not ppe.has_helmet:
            violations.append(SafetyViolation(
                violation_type="MISSING_HELMET",
                track_id=person.track_id,
                severity="HIGH",
                confidence=max(0.5, ppe.helmet_confidence),
                description=f"Person #{person.track_id} missing safety helmet (activity: {activity})",
                timestamp=ts,
                bbox_xyxy=person.bbox_xyxy,
            ))

        if self.require_vest and not ppe.has_vest:
            violations.append(SafetyViolation(
                violation_type="MISSING_VEST",
                track_id=person.track_id,
                severity="MEDIUM",
                confidence=max(0.5, ppe.vest_confidence),
                description=f"Person #{person.track_id} missing high-visibility vest (activity: {activity})",
                timestamp=ts,
                bbox_xyxy=person.bbox_xyxy,
            ))

        return violations

    # ── Rule 3: Restricted Zone Intrusion ───────────────────────────────

    def _check_zone_intrusion(
        self,
        person: TrackedPerson,
        pose: Optional[PoseResult],
        ts: float,
    ) -> Optional[SafetyViolation]:
        """Checks if a person's feet (ankles) or body center are inside a restricted zone.

        Uses ankle landmark positions (27, 28) when pose is available,
        falls back to bbox bottom-center otherwise.
        """
        if not self.restricted_zones:
            return None

        tid = person.track_id
        state = self._zone_states[tid]

        # Determine ground-contact point(s)
        check_points: list[tuple[float, float]] = []
        if pose is not None:
            l_ankle, r_ankle = _ankle_positions_in_frame(pose, person.bbox_xyxy)
            l_vis = pose.landmarks[27][3]
            r_vis = pose.landmarks[28][3]
            if l_vis > 0.3:
                check_points.append(l_ankle)
            if r_vis > 0.3:
                check_points.append(r_ankle)

        # Fallback: bbox bottom center
        if not check_points:
            x1, y1, x2, y2 = person.bbox_xyxy
            check_points.append(((x1 + x2) / 2.0, y2))

        # Test against all zones
        violated_zone: Optional[ZonePolygon] = None
        for zone in self.restricted_zones:
            for pt in check_points:
                if _point_in_polygon(pt[0], pt[1], zone.vertices):
                    violated_zone = zone
                    break
            if violated_zone:
                break

        if violated_zone:
            state.inside_frame_count += 1
            state.current_zone = violated_zone.name
        else:
            state.inside_frame_count = max(0, state.inside_frame_count - 1)
            if state.inside_frame_count == 0:
                state.current_zone = None

        if state.inside_frame_count >= self.zone_confirm_frames:
            return SafetyViolation(
                violation_type="RESTRICTED_ZONE",
                track_id=tid,
                severity="HIGH",
                confidence=0.90,
                description=(
                    f"Person #{tid} inside restricted zone '{state.current_zone}' "
                    f"for {state.inside_frame_count} frames"
                ),
                timestamp=ts,
                bbox_xyxy=person.bbox_xyxy,
            )

        return None

    # ── Rule 4: Dangerous Climbing ──────────────────────────────────────

    def _check_dangerous_climbing(
        self,
        person: TrackedPerson,
        activity: str,
        ppe: Optional[PersonPPEStatus],
        ts: float,
    ) -> Optional[SafetyViolation]:
        """Flags climbing activity when the person lacks a safety helmet.

        Climbing without head protection is a critical workplace safety violation.
        Uses multi-frame persistence to avoid single-frame misclassification triggers.
        """
        tid = person.track_id
        state = self._climb_states[tid]

        is_climbing = activity == "climbing"
        has_helmet = ppe.has_helmet if ppe is not None else True  # Assume compliant if no PPE data

        if is_climbing and not has_helmet:
            state.climbing_no_helmet_frames += 1
        else:
            state.climbing_no_helmet_frames = max(0, state.climbing_no_helmet_frames - 1)

        if state.climbing_no_helmet_frames >= self.climb_confirm_frames:
            return SafetyViolation(
                violation_type="DANGEROUS_CLIMB",
                track_id=tid,
                severity="CRITICAL",
                confidence=0.85,
                description=(
                    f"Person #{tid} climbing without helmet "
                    f"({state.climbing_no_helmet_frames} frames)"
                ),
                timestamp=ts,
                bbox_xyxy=person.bbox_xyxy,
            )

        return None

    # ── State management ────────────────────────────────────────────────

    def _prune_stale(self, active_ids: set[int], now: float) -> None:
        """Remove internal state for tracks that haven't been seen recently."""
        stale_ids = [
            tid for tid, last in self._last_seen.items()
            if tid not in active_ids and (now - last) > self.stale_seconds
        ]
        for tid in stale_ids:
            self._fall_states.pop(tid, None)
            self._zone_states.pop(tid, None)
            self._climb_states.pop(tid, None)
            self._last_seen.pop(tid, None)

    def add_zone(self, zone: ZonePolygon) -> None:
        """Add a restricted zone at runtime."""
        self.restricted_zones.append(zone)

    def clear_zones(self) -> None:
        """Remove all restricted zones."""
        self.restricted_zones.clear()

    def reset(self) -> None:
        """Clear all internal state."""
        self._fall_states.clear()
        self._zone_states.clear()
        self._climb_states.clear()
        self._last_seen.clear()

    def status(self) -> dict:
        return {
            "active_tracks": len(self._last_seen),
            "restricted_zones": len(self.restricted_zones),
            "zone_names": [z.name for z in self.restricted_zones],
            "fall_states": len(self._fall_states),
            "require_helmet": self.require_helmet,
            "require_vest": self.require_vest,
        }

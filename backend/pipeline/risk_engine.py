"""
Risk Scoring Engine (SRS §8.5, FR-13..FR-15, Week 8 deliverable).

Computes a deterministic, transparent composite risk score (0–100) per tracked person
and a scene-level aggregate threat metric:
  Risk = min(100, w1*ViolationSeverity + w2*ActivityRisk + w3*ZoneProximity + w4*Persistence)

Severity Categorization:
  - 0–29:   LOW (Normal operations - Green)
  - 30–59:  MEDIUM (Caution / Minor warning - Yellow)
  - 60–79:  HIGH (Active violation alert - Orange)
  - 80–100: CRITICAL (Immediate danger / evacuation trigger - Red)

Properties:
  - Deterministic: 100% reproducible, zero stochastic drift.
  - Transparent: provides exact point breakdown in contributing_factors.
  - Temporal Smoothing & Persistence: escalates prolonged violations and decays
    gracefully upon correction to prevent single-frame flickering.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from backend.pipeline.safety_engine import SafetyViolation


# ── Severity Tier Weights ───────────────────────────────────────────────────

VIOLATION_WEIGHTS = {
    "FALL": 60.0,             # Immediate critical emergency
    "DANGEROUS_CLIMB": 50.0,  # Critical risk of fatal fall
    "RESTRICTED_ZONE": 35.0,  # High unauthorized access risk
    "MISSING_HELMET": 25.0,   # High head injury risk
    "MISSING_VEST": 15.0,     # Medium visibility risk
}

ACTIVITY_RISK_WEIGHTS = {
    "climbing": 25.0,         # High hazard activity at height
    "running": 20.0,          # Slip / trip / collision hazard
    "walking": 5.0,           # Dynamic motion / active worker
    "standing": 0.0,          # Stationary upright
    "sitting": 0.0,           # Stationary resting
}


@dataclass
class RiskScore:
    """Per-person deterministic safety risk metric."""
    track_id: int
    score: float                         # 0.0 to 100.0
    level: str                           # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    violation_score: float = 0.0
    activity_score: float = 0.0
    zone_score: float = 0.0
    persistence_score: float = 0.0
    contributing_factors: list[str] = field(default_factory=list)
    timestamp: float = 0.0

    @property
    def is_elevated(self) -> bool:
        return self.score >= 30.0

    @property
    def is_critical(self) -> bool:
        return self.score >= 80.0


@dataclass
class SceneRiskScore:
    """Scene-wide aggregate safety threat assessment."""
    overall_score: float                 # 0.0 to 100.0
    overall_level: str                   # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    total_workers: int = 0
    workers_at_risk: int = 0             # count with score >= 30
    critical_workers: int = 0            # count with score >= 80
    highest_risk_track_id: Optional[int] = None
    active_violations_count: int = 0
    violations_by_severity: dict[str, int] = field(default_factory=dict)
    timestamp: float = 0.0
    summary: str = "Normal operations"


def get_risk_level(score: float) -> str:
    """Categorizes 0-100 numerical score into SRS §8.5 severity tiers."""
    if score >= 80.0:
        return "CRITICAL"
    if score >= 60.0:
        return "HIGH"
    if score >= 30.0:
        return "MEDIUM"
    return "LOW"


class RiskEngine:
    """Calculates deterministic safety risk scores without stochastic drift.

    Implements:
      - FR-13: Per-person composite risk score (0-100).
      - FR-14: Persistence escalation (+2 pts/sec of ongoing violation).
      - FR-15: Scene-level aggregate risk with human-readable summary.
    """

    def __init__(
        self,
        persistence_escalation_rate: float = 2.0,  # +pts per second of ongoing violation
        persistence_max_points: float = 20.0,      # max escalation bonus
        risk_decay_halflife_seconds: float = 3.0,  # smooth exponential decay on resolution
        stale_track_seconds: float = 10.0,
    ):
        self.persistence_rate = persistence_escalation_rate
        self.persistence_max = persistence_max_points
        self.decay_halflife = risk_decay_halflife_seconds
        self.stale_seconds = stale_track_seconds

        # Per-person violation start timestamps: (track_id, violation_type) -> start_timestamp
        self._violation_start_ts: Dict[Tuple[int, str], float] = {}

        # Smoothed previous risk scores for decay: track_id -> (last_score, last_timestamp)
        self._previous_scores: Dict[int, Tuple[float, float]] = {}

        # Last seen timestamp for track pruning
        self._last_seen: Dict[int, float] = {}

    def compute_person_risk(
        self,
        track_id: int,
        violations: Sequence[SafetyViolation],
        activity: str,
        in_hazard_zone: bool,
        timestamp: float,
        near_hazard_zone: bool = False,
    ) -> RiskScore:
        """Computes deterministic risk score for an individual tracked worker.

        Args:
            track_id:         Persistent ByteTrack ID.
            violations:       List of active SafetyViolation objects for this person.
            activity:         Current recognized activity ('walking', 'climbing', etc.).
            in_hazard_zone:   True if person is inside a restricted/hazard zone.
            timestamp:        Current frame wall-clock timestamp.
            near_hazard_zone: True if within proximity buffer of a hazard boundary.

        Returns:
            RiskScore object with explainable factors.
        """
        self._last_seen[track_id] = timestamp
        factors: list[str] = []

        # ── 1. Violation Severity (w1) ──
        violation_pts = 0.0
        current_vtypes = set()
        for v in violations:
            vtype = v.violation_type
            current_vtypes.add(vtype)
            pts = VIOLATION_WEIGHTS.get(vtype, 20.0)
            violation_pts += pts
            factors.append(f"Violation [{vtype}]: +{pts:.0f} pts")

        # ── 2. Violation Persistence Escalation (w4) ──
        persistence_pts = 0.0
        # Update / prune violation timestamps
        for vtype in current_vtypes:
            key = (track_id, vtype)
            if key not in self._violation_start_ts:
                self._violation_start_ts[key] = timestamp
            duration = max(0.0, timestamp - self._violation_start_ts[key])
            if duration >= 1.0:
                bonus = min(self.persistence_max, duration * self.persistence_rate)
                persistence_pts = max(persistence_pts, bonus)

        if persistence_pts > 0:
            factors.append(f"Unresolved violation persistence: +{persistence_pts:.1f} pts")

        # Clear resolved violations for this track
        resolved_keys = [
            k for k in self._violation_start_ts
            if k[0] == track_id and k[1] not in current_vtypes
        ]
        for k in resolved_keys:
            del self._violation_start_ts[k]

        # ── 3. Activity Risk (w2) ──
        activity_pts = ACTIVITY_RISK_WEIGHTS.get(activity.lower(), 0.0)
        if activity_pts > 0:
            factors.append(f"Elevated motion [{activity}]: +{activity_pts:.0f} pts")

        # ── 4. Zone Proximity & Intrusion (w3) ──
        zone_pts = 0.0
        if in_hazard_zone:
            zone_pts = 35.0
            factors.append("Restricted zone presence: +35 pts")
        elif near_hazard_zone:
            zone_pts = 15.0
            factors.append("Restricted zone boundary proximity: +15 pts")

        # ── Composite Sum ──
        raw_score = violation_pts + persistence_pts + activity_pts + zone_pts

        # ── Exponential Decay Smoothing on Resolution ──
        # If raw_score dropped significantly (e.g. violation cleared), decay smoothly
        final_score = raw_score
        if track_id in self._previous_scores:
            prev_score, prev_ts = self._previous_scores[track_id]
            dt = max(0.0, timestamp - prev_ts)
            if raw_score < prev_score and dt > 0:
                decay_factor = math.exp(-dt * math.log(2) / self.decay_halflife)
                decayed = prev_score * decay_factor
                final_score = max(raw_score, decayed)
                if final_score > raw_score + 1.0:
                    factors.append(f"Residual incident decay: {final_score:.1f} pts")

        final_score = round(min(100.0, max(0.0, final_score)), 1)
        self._previous_scores[track_id] = (final_score, timestamp)

        return RiskScore(
            track_id=track_id,
            score=final_score,
            level=get_risk_level(final_score),
            violation_score=violation_pts,
            activity_score=activity_pts,
            zone_score=zone_pts,
            persistence_score=persistence_pts,
            contributing_factors=factors,
            timestamp=timestamp,
        )

    def compute_scene_risk(
        self,
        person_risks: Sequence[RiskScore],
        all_violations: Sequence[SafetyViolation],
        timestamp: float,
    ) -> SceneRiskScore:
        """Computes aggregate scene-level risk score across all active workers.

        Formulation:
          Scene Risk = max(person_risks) + 0.2 * average(remaining_person_risks)
        """
        if not person_risks:
            return SceneRiskScore(
                overall_score=0.0,
                overall_level="LOW",
                total_workers=0,
                workers_at_risk=0,
                critical_workers=0,
                highest_risk_track_id=None,
                active_violations_count=0,
                violations_by_severity={},
                timestamp=timestamp,
                summary="No workers in camera frame",
            )

        scores = [p.score for p in person_risks]
        max_score = max(scores)
        highest_person = max(person_risks, key=lambda p: p.score)

        # Aggregate formula: dominant person + weighted remainder
        if len(scores) > 1:
            remainder_avg = (sum(scores) - max_score) / (len(scores) - 1)
            overall_score = min(100.0, max_score + 0.20 * remainder_avg)
        else:
            overall_score = max_score

        overall_score = round(overall_score, 1)
        overall_level = get_risk_level(overall_score)

        # Violation severity counts
        sev_counts: dict[str, int] = {}
        for v in all_violations:
            sev_counts[v.severity] = sev_counts.get(v.severity, 0) + 1

        workers_at_risk = sum(1 for p in person_risks if p.is_elevated)
        critical_workers = sum(1 for p in person_risks if p.is_critical)

        # Human-readable summary for incident audits and VLM inputs
        if critical_workers > 0:
            summary = (
                f"CRITICAL: {critical_workers} worker(s) in immediate danger "
                f"({len(all_violations)} active violations)"
            )
        elif workers_at_risk > 0:
            summary = (
                f"WARNING: {workers_at_risk} worker(s) with elevated safety risk "
                f"({len(all_violations)} active violations)"
            )
        else:
            summary = f"NORMAL: {len(person_risks)} worker(s) compliant (all clear)"

        return SceneRiskScore(
            overall_score=overall_score,
            overall_level=overall_level,
            total_workers=len(person_risks),
            workers_at_risk=workers_at_risk,
            critical_workers=critical_workers,
            highest_risk_track_id=highest_person.track_id if max_score > 0 else None,
            active_violations_count=len(all_violations),
            violations_by_severity=sev_counts,
            timestamp=timestamp,
            summary=summary,
        )

    def evaluate(
        self,
        tracks: list,
        violations: list[SafetyViolation],
        activities: dict[int, str],
        in_hazard_zones: dict[int, bool],
        timestamp: float,
        near_hazard_zones: Optional[dict[int, bool]] = None,
    ) -> tuple[dict[int, RiskScore], SceneRiskScore]:
        """Convenience evaluation method for entire pipeline frame.

        Args:
            tracks:             List of TrackedPerson objects.
            violations:         List of SafetyViolation objects from SafetyEngine.
            activities:         Dict of track_id -> activity label.
            in_hazard_zones:    Dict of track_id -> bool (is in hazard zone).
            timestamp:          Current timestamp.
            near_hazard_zones:  Optional dict of track_id -> bool (is near zone perimeter).

        Returns:
            Tuple of (dict[track_id, RiskScore], SceneRiskScore).
        """
        # Map violations to each person
        person_viols: dict[int, list[SafetyViolation]] = {t.track_id: [] for t in tracks}
        for v in violations:
            if v.track_id in person_viols:
                person_viols[v.track_id].append(v)

        person_scores: dict[int, RiskScore] = {}
        for t in tracks:
            tid = t.track_id
            v_list = person_viols.get(tid, [])
            act = activities.get(tid, "standing")
            in_zone = in_hazard_zones.get(tid, False)
            near_zone = near_hazard_zones.get(tid, False) if near_hazard_zones else False

            score = self.compute_person_risk(
                track_id=tid,
                violations=v_list,
                activity=act,
                in_hazard_zone=in_zone,
                near_hazard_zone=near_zone,
                timestamp=timestamp,
            )
            person_scores[tid] = score

        # Aggregate scene score
        scene_score = self.compute_scene_risk(
            list(person_scores.values()), violations, timestamp
        )

        # Prune stale
        active_ids = {t.track_id for t in tracks}
        self.prune_stale(active_ids, timestamp)

        return person_scores, scene_score

    def prune_stale(self, active_track_ids: set[int], timestamp: float) -> None:
        """Drops memory records for workers no longer seen in frame."""
        stale_ids = [
            tid for tid, last in self._last_seen.items()
            if tid not in active_track_ids and (timestamp - last) > self.stale_seconds
        ]
        for tid in stale_ids:
            self._previous_scores.pop(tid, None)
            self._last_seen.pop(tid, None)
            keys_to_del = [k for k in self._violation_start_ts if k[0] == tid]
            for k in keys_to_del:
                del self._violation_start_ts[k]

    def reset(self) -> None:
        """Clears all running state."""
        self._violation_start_ts.clear()
        self._previous_scores.clear()
        self._last_seen.clear()

    def status(self) -> dict:
        return {
            "active_tracks": len(self._last_seen),
            "tracked_violations": len(self._violation_start_ts),
            "persistence_rate": self.persistence_rate,
            "decay_halflife": self.decay_halflife,
        }

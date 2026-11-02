"""
Database Models (SRS §8.6, FR-22, Week 10 deliverable).

Stores safety incidents, keyframe snapshots, risk metrics, and VLM audit logs.
SQLite backend with clean schema compatible with future PostgreSQL migration.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, List, Optional


@dataclass
class SafetyIncidentRecord:
    """Represents a logged safety violation or critical safety incident."""
    id: Optional[int] = None
    timestamp: float = field(default_factory=time.time)
    timestamp_iso: str = ""
    track_id: int = 0
    event_type: str = ""          # "FALL", "MISSING_HELMET", "MISSING_VEST", "RESTRICTED_ZONE", "DANGEROUS_CLIMB"
    risk_level: str = "LOW"       # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    risk_score: float = 0.0
    activity: str = "unknown"
    confidence: float = 0.0
    bbox_xyxy: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    snapshot_path: Optional[str] = None
    vlm_verified: bool = False
    vlm_summary: Optional[str] = None
    recommended_action: Optional[str] = None
    contributing_factors: list[str] = field(default_factory=list)
    resolved: bool = False
    resolved_at: Optional[float] = None

    def __post_init__(self):
        if not self.timestamp_iso:
            self.timestamp_iso = datetime.utcfromtimestamp(self.timestamp).isoformat() + "Z"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["bbox_xyxy"] = list(self.bbox_xyxy)
        return d

    @classmethod
    def from_row(cls, row: tuple) -> SafetyIncidentRecord:
        """Constructs an incident record from a database row tuple."""
        (
            id_,
            ts,
            ts_iso,
            track_id,
            event_type,
            risk_level,
            risk_score,
            activity,
            confidence,
            bbox_str,
            snapshot_path,
            vlm_verified,
            vlm_summary,
            recommended_action,
            factors_str,
            resolved,
            resolved_at,
        ) = row

        bbox = tuple(json.loads(bbox_str)) if bbox_str else (0.0, 0.0, 0.0, 0.0)
        factors = json.loads(factors_str) if factors_str else []

        return cls(
            id=id_,
            timestamp=ts,
            timestamp_iso=ts_iso,
            track_id=track_id,
            event_type=event_type,
            risk_level=risk_level,
            risk_score=risk_score,
            activity=activity,
            confidence=confidence,
            bbox_xyxy=bbox,
            snapshot_path=snapshot_path,
            vlm_verified=bool(vlm_verified),
            vlm_summary=vlm_summary,
            recommended_action=recommended_action,
            contributing_factors=factors,
            resolved=bool(resolved),
            resolved_at=resolved_at,
        )

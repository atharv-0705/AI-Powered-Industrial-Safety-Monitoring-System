"""
SQLite Incident Database Service (SRS §8.6, FR-22, Week 10 deliverable).

Provides local persistent storage for incidents, keyframe snapshots, and VLM audit reports.
Thread-safe with automatic schema migration and indexing.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, List, Optional

import cv2
import numpy as np

from backend.app.db.models import SafetyIncidentRecord

logger = logging.getLogger("safety-ai-mvp.db")

DEFAULT_DB_PATH = Path("data/safety_monitor.db")
DEFAULT_SNAPSHOT_DIR = Path("data/snapshots")


class IncidentDatabase:
    """Manages SQLite persistent storage for safety incident logs."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        snapshot_dir: str | Path = DEFAULT_SNAPSHOT_DIR,
    ):
        self.db_path = Path(db_path)
        self.snapshot_dir = Path(snapshot_dir)

        # Ensure parent directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL")  # Fast concurrent reads/writes
        return conn

    def _init_schema(self) -> None:
        """Initializes tables and indexes."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    timestamp_iso TEXT NOT NULL,
                    track_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    activity TEXT,
                    confidence REAL,
                    bbox_xyxy TEXT,
                    snapshot_path TEXT,
                    vlm_verified INTEGER DEFAULT 0,
                    vlm_summary TEXT,
                    recommended_action TEXT,
                    contributing_factors TEXT,
                    resolved INTEGER DEFAULT 0,
                    resolved_at REAL
                )
                """
            )
            # Create indexes for fast query filtering
            conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_risk_level ON incidents(risk_level)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_resolved ON incidents(resolved)")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(incidents)")}
            if "video_path" not in columns:
                conn.execute("ALTER TABLE incidents ADD COLUMN video_path TEXT")
            conn.commit()

        logger.info(f"Initialized incident database at {self.db_path}")

    def save_snapshot(
        self,
        frame: np.ndarray,
        incident_prefix: str = "incident",
    ) -> str:
        """Saves a keyframe JPEG snapshot and returns its relative/standardized path."""
        ts_str = int(time.time() * 1000)
        clean_prefix = incident_prefix.lower().replace(" ", "_")
        filename = f"{clean_prefix}_{ts_str}.jpg"
        file_path = self.snapshot_dir / filename
        cv2.imwrite(str(file_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return str(file_path).replace("\\", "/")

    def insert_incident(self, incident: SafetyIncidentRecord) -> int:
        """Inserts an incident record into the database."""
        return self.save_incident(incident, frame_bgr=None)

    def save_incident(
        self,
        incident: SafetyIncidentRecord,
        frame_bgr: Optional[np.ndarray] = None,
    ) -> int:
        """Saves a safety incident record and writes keyframe snapshot JPEG if provided."""
        # 1. Save keyframe snapshot if frame is provided
        if frame_bgr is not None and frame_bgr.size > 0:
            ts_str = int(incident.timestamp * 1000)
            clean_type = incident.event_type.lower().replace(" ", "_")
            filename = f"incident_{ts_str}_{clean_type}_id{incident.track_id}.jpg"
            file_path = self.snapshot_dir / filename
            try:
                # Optionally draw highlight box on snapshot
                snap = frame_bgr.copy()
                if incident.bbox_xyxy:
                    x1, y1, x2, y2 = (int(v) for v in incident.bbox_xyxy)
                    cv2.rectangle(snap, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(
                        snap,
                        f"{incident.event_type} (Risk {incident.risk_score:.0f})",
                        (x1, max(20, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 0, 255),
                        2,
                    )
                cv2.imwrite(str(file_path), snap, [cv2.IMWRITE_JPEG_QUALITY, 85])
                incident.snapshot_path = str(file_path).replace("\\", "/")
            except Exception as e:
                logger.warning(f"Could not save incident snapshot: {e}")

        # 2. Insert into database
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO incidents (
                    timestamp, timestamp_iso, track_id, event_type, risk_level,
                    risk_score, activity, confidence, bbox_xyxy, snapshot_path,
                    vlm_verified, vlm_summary, recommended_action, contributing_factors,
                    resolved, resolved_at, video_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident.timestamp,
                    incident.timestamp_iso,
                    incident.track_id,
                    incident.event_type,
                    incident.risk_level,
                    incident.risk_score,
                    incident.activity,
                    incident.confidence,
                    json.dumps(list(incident.bbox_xyxy)),
                    incident.snapshot_path,
                    1 if incident.vlm_verified else 0,
                    incident.vlm_summary,
                    incident.recommended_action,
                    json.dumps(incident.contributing_factors),
                    1 if incident.resolved else 0,
                    incident.resolved_at,
                    incident.video_path,
                ),
            )
            incident.id = cursor.lastrowid
            conn.commit()

        logger.info(f"Saved incident #{incident.id}: {incident.event_type} [{incident.risk_level}]")
        return incident.id

    def update_vlm_explanation(
        self,
        incident_id: int,
        vlm_summary: Any,
        recommended_action: str = "",
        vlm_verified: bool = True,
    ) -> bool:
        """Updates an existing incident record with asynchronous VLM audit results."""
        if hasattr(vlm_summary, "summary"):
            explanation_obj = vlm_summary
            vlm_summary_str = explanation_obj.summary
            rec_action_str = getattr(explanation_obj, "recommended_action", "")
            verified_bool = getattr(explanation_obj, "verified", True)
        else:
            vlm_summary_str = str(vlm_summary)
            rec_action_str = recommended_action
            verified_bool = vlm_verified

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE incidents
                SET vlm_summary = ?, recommended_action = ?, vlm_verified = ?
                WHERE id = ?
                """,
                (vlm_summary_str, rec_action_str, 1 if verified_bool else 0, incident_id),
            )
            conn.commit()
            return cursor.rowcount > 0


    def list_incidents(
        self,
        risk_level: Optional[str] = None,
        event_type: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SafetyIncidentRecord]:
        """Queries logged incidents with optional filtering and pagination."""
        query = "SELECT * FROM incidents WHERE 1=1"
        params: list[Any] = []

        if risk_level:
            query += " AND risk_level = ?"
            params.append(risk_level.upper())
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.upper())
        if resolved is not None:
            query += " AND resolved = ?"
            params.append(1 if resolved else 0)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [SafetyIncidentRecord.from_row(r) for r in rows]

    def get_incident(self, incident_id: int) -> Optional[SafetyIncidentRecord]:
        """Retrieves a single incident by its primary key ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,))
            row = cursor.fetchone()
            if row:
                return SafetyIncidentRecord.from_row(row)
        return None

    def resolve_incident(self, incident_id: int) -> bool:
        """Marks an active incident as resolved."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE incidents SET resolved = 1, resolved_at = ? WHERE id = ?",
                (time.time(), incident_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_statistics(self) -> dict[str, Any]:
        """Computes aggregate incident metrics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM incidents")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM incidents WHERE resolved = 0")
            unresolved = cursor.fetchone()[0]

            cursor.execute("SELECT risk_level, COUNT(*) FROM incidents GROUP BY risk_level")
            by_level = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT event_type, COUNT(*) FROM incidents GROUP BY event_type")
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "total_incidents": total,
            "unresolved_incidents": unresolved,
            "resolved_incidents": total - unresolved,
            "by_severity": {
                "CRITICAL": by_level.get("CRITICAL", 0),
                "HIGH": by_level.get("HIGH", 0),
                "MEDIUM": by_level.get("MEDIUM", 0),
                "LOW": by_level.get("LOW", 0),
            },
            "by_event_type": by_type,
        }

    def clear(self) -> None:
        """Clears all incident records (used for testing)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM incidents")
            conn.commit()


# Singleton database instance
_db_instance: Optional[IncidentDatabase] = None


def get_incident_db() -> IncidentDatabase:
    """Returns singleton database accessor."""
    global _db_instance
    if _db_instance is None:
        _db_instance = IncidentDatabase()
    return _db_instance

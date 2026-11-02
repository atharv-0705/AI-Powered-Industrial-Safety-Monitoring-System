"""
Evidence File Storage Service (Week 12).
Manages disk storage, naming, directory partitioning, and retention for event keyframe evidence.
Path structure: backend/storage/evidence/{year}/{month}/event_{event_id}_{idx}.jpg
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

logger = logging.getLogger("safety-ai-mvp.evidence")

BASE_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "evidence"


class EvidenceStorageService:
    """Manages event evidence JPEG captures with partitioned directory structure."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or BASE_STORAGE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_event_evidence(
        self,
        frame_bgr: np.ndarray,
        event_id: int,
        idx: int = 1,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """Saves an evidence frame to disk and returns its standardized relative path."""
        ts = timestamp or datetime.utcnow()
        year_str = f"{ts.year}"
        month_str = f"{ts.month:02d}"

        target_dir = self.base_dir / year_str / month_str
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"event_{event_id}_{idx}.jpg"
        file_path = target_dir / filename

        # Write JPEG with 85% quality compression
        cv2.imwrite(str(file_path), frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        logger.info(f"Saved evidence frame for Event #{event_id} to {file_path}")

        # Return web-accessible URL path: /api/evidence/{year}/{month}/{filename}
        return f"/api/evidence/{year_str}/{month_str}/{filename}"

    def get_file_path(self, year: str, month: str, filename: str) -> Optional[Path]:
        """Resolves file path while preventing path traversal attacks."""
        clean_filename = os.path.basename(filename)
        path = self.base_dir / year / month / clean_filename
        if path.is_file():
            return path
        return None

    def prune_old_evidence(self, retention_days: int = 30) -> int:
        """Removes evidence older than retention threshold."""
        deleted_count = 0
        now_ts = datetime.utcnow().timestamp()
        cutoff_seconds = retention_days * 86400

        for root, _, files in os.walk(self.base_dir):
            for file in files:
                if file.endswith(".jpg"):
                    file_path = Path(root) / file
                    if (now_ts - file_path.stat().st_mtime) > cutoff_seconds:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"Could not delete old evidence {file_path}: {e}")
        return deleted_count


_evidence_service_instance: Optional[EvidenceStorageService] = None


def get_evidence_service() -> EvidenceStorageService:
    global _evidence_service_instance
    if _evidence_service_instance is None:
        _evidence_service_instance = EvidenceStorageService()
    return _evidence_service_instance


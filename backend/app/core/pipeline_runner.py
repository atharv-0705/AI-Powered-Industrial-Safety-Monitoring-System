"""
Pipeline Orchestrator & Live Stream Runner (Weeks 9-10).

Integrates:
- Video Ingestion (Webcam or MP4 source via OpenCV / VideoSource)
- Person Tracking (YOLO11n + ByteTrack via PersonTracker)
- Pose Estimation & Feature Extraction (PoseEstimator, TemporalFeatureManager)
- Temporal Transformer HAR (ActivityRecognizer, webcam calibrated)
- PPE Inspection (PPEDetector)
- Safety Rule Engine (SafetyEngine: Falls, PPE, Restricted Zone, Climbing)
- Deterministic Risk Scoring Engine (RiskEngine: 4 factors, decay, scene metrics)
- Incident Storage (SQLite IncidentDatabase: snapshots, records, queries)
- Async Gemini 1.5 Flash Verification (GeminiVLMClient with graceful fallback)
- Low-latency WebSocket Streaming (ConnectionManager: live frames + JSON telemetry)
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from backend.app.api.websocket import get_connection_manager
from backend.app.core.config import get_settings
from backend.app.db.database import get_incident_db
from backend.app.db.models import SafetyIncidentRecord
from backend.app.vlm.gemini_client import VLMIncidentExplanation, get_vlm_client
from backend.pipeline.detector import PersonTracker, TrackedPerson
from backend.pipeline.features import TemporalFeatureManager
from backend.pipeline.har import ActivityRecognizer, is_webcam_source
from backend.pipeline.pose import PoseEstimator
from backend.pipeline.ppe import PPEDetector
from backend.pipeline.risk_engine import RiskEngine, RiskScore, SceneRiskScore
from backend.pipeline.safety_engine import SafetyEngine, SafetyViolation

logger = logging.getLogger("safety-ai-mvp.pipeline_runner")


class PipelineRunner:
    """Manages the background execution of the full multimodal safety pipeline."""

    def __init__(self):
        self.settings = get_settings()
        self.db = get_incident_db()
        self.vlm = get_vlm_client()
        self.ws_manager = get_connection_manager()

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._incident_cooldowns: Dict[str, float] = {}  # key: f"{track_id}:{event_type}" -> timestamp
        self._fps = 0.0
        self._frame_count = 0
        self._current_scene_risk = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "fps": round(self._fps, 1),
            "frame_count": self._frame_count,
            "scene_risk": round(self._current_scene_risk, 1),
            "video_source": self.settings.VIDEO_SOURCE,
        }

    async def start(self, source_override: Optional[str] = None):
        """Starts the pipeline processing loop in the background."""
        if self._running:
            logger.warning("Pipeline is already running.")
            return

        source = source_override if source_override is not None else self.settings.VIDEO_SOURCE
        self._running = True
        self._task = asyncio.create_task(self._run_loop(source))
        logger.info(f"Pipeline started with video source: {source}")

    async def stop(self):
        """Stops the active pipeline runner."""
        if not self._running:
            return

        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Pipeline stopped.")

    async def _run_loop(self, source: str):
        """Main asynchronous processing loop."""
        cap_arg = int(source) if source.isdigit() else source
        cap = cv2.VideoCapture(cap_arg)

        if not cap.isOpened():
            logger.error(f"Failed to open video source: {source}")
            self._running = False
            return

        is_webcam = is_webcam_source(source)

        # Initialize pipeline modules
        tracker = PersonTracker(
            model_path=self.settings.DETECTOR_MODEL,
            device=self.settings.DETECTOR_DEVICE,
            conf_threshold=self.settings.DETECTOR_CONF_THRESHOLD,
            img_size=self.settings.DETECTOR_IMG_SIZE,
            tracker_config=self.settings.TRACKER_CONFIG,
        )
        pose_estimator = PoseEstimator()
        feature_manager = TemporalFeatureManager()
        har = ActivityRecognizer(
            checkpoint_path=self.settings.HAR_CHECKPOINT_PATH,
            device=self.settings.HAR_DEVICE,
            is_webcam=is_webcam,
        )
        ppe_detector = PPEDetector(
            model_path=self.settings.PPE_MODEL_PATH,
            device=self.settings.PPE_DEVICE,
            conf_threshold=self.settings.PPE_CONF_THRESHOLD,
        )
        safety_engine = SafetyEngine(
            fall_frames_confirmation=self.settings.FALL_CONFIRMATION_FRAMES,
        )
        risk_engine = RiskEngine()

        t_prev = time.time()
        frame_interval = 1.0 / max(1, self.settings.PROCESSING_FPS)

        try:
            while self._running:
                loop_start = time.time()
                ret, frame = cap.read()

                if not ret:
                    if not is_webcam:
                        # Loop video file for continuous processing
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        await asyncio.sleep(0.05)
                        continue
                    else:
                        logger.warning("Empty frame read from webcam.")
                        await asyncio.sleep(0.1)
                        continue

                self._frame_count += 1
                now = time.time()
                dt = now - t_prev
                t_prev = now
                if dt > 0:
                    self._fps = 0.9 * self._fps + 0.1 * (1.0 / dt) if self._fps > 0 else (1.0 / dt)

                frame_h, frame_w = frame.shape[:2]

                # 1. Track Persons
                tracked_persons = tracker.track_frame(frame)

                # 2. Pose & Activity Recognition
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

                # 3. PPE Inspection
                ppe_statuses = {}
                if ppe_detector.is_ready:
                    ppe_dets = ppe_detector.detect_ppe(frame)
                    for person in tracked_persons:
                        ppe_statuses[person.track_id] = ppe_detector.associate_ppe_to_person(
                            person.track_id, person.bbox_xyxy, ppe_dets
                        )

                # 4. Safety Rules
                violations = safety_engine.evaluate(
                    tracked_persons=tracked_persons,
                    poses=poses,
                    activities=activities,
                    ppe_statuses=ppe_statuses,
                    timestamp=now,
                )

                # 5. Zone Proximities for Risk Factor 3
                in_hazard_zones = {
                    p.track_id: any(v.track_id == p.track_id and v.violation_type == "RESTRICTED_ZONE" for v in violations)
                    for p in tracked_persons
                }
                near_hazard_zones = {}
                if safety_engine.restricted_zones:
                    for p in tracked_persons:
                        bx = (p.bbox_xyxy[0] + p.bbox_xyxy[2]) / 2.0
                        by = p.bbox_xyxy[3]
                        near_hazard_zones[p.track_id] = any(
                            z.is_near_boundary((bx, by), proximity_threshold_px=45.0)
                            for z in safety_engine.restricted_zones.values()
                        )

                # 6. Multi-Factor Risk Scoring
                person_risks = risk_engine.update(
                    tracked_persons=tracked_persons,
                    violations=violations,
                    activities=activities,
                    in_hazard_zones=in_hazard_zones,
                    near_hazard_zones=near_hazard_zones,
                    timestamp=now,
                )
                scene_risk = risk_engine.compute_scene_threat(person_risks)
                self._current_scene_risk = scene_risk.overall_score

                # 7. Check for Incident Storage & VLM Verification
                await self._process_incidents(
                    frame=frame,
                    violations=violations,
                    person_risks=person_risks,
                    scene_risk=scene_risk,
                    activities=activities,
                    timestamp=now,
                )

                # 8. Live Telemetry Packet
                telemetry = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "frame_idx": self._frame_count,
                    "fps": round(self._fps, 1),
                    "scene_risk": {
                        "overall_score": round(scene_risk.overall_score, 1),
                        "overall_level": scene_risk.overall_level,
                        "summary": scene_risk.summary,
                        "workers_at_risk": scene_risk.workers_at_risk,
                        "active_violations_count": scene_risk.active_violations_count,
                    },
                    "workers_count": len(tracked_persons),
                    "tracks": [
                        {
                            "track_id": p.track_id,
                            "bbox": [round(c, 1) for c in p.bbox_xyxy],
                            "activity": activities.get(p.track_id, "unknown"),
                            "ppe": {
                                "has_helmet": ppe_statuses[p.track_id].has_helmet if p.track_id in ppe_statuses else None,
                                "has_vest": ppe_statuses[p.track_id].has_vest if p.track_id in ppe_statuses else None,
                            } if p.track_id in ppe_statuses else None,
                            "risk": {
                                "score": round(person_risks[p.track_id].score, 1),
                                "level": person_risks[p.track_id].level,
                                "factors": person_risks[p.track_id].contributing_factors,
                            } if p.track_id in person_risks else None,
                        }
                        for p in tracked_persons
                    ],
                    "violations": [
                        {
                            "track_id": v.track_id,
                            "event_type": v.violation_type,
                            "severity": v.severity,
                            "confidence": round(v.confidence, 2),
                            "description": v.description,
                        }
                        for v in violations
                    ],
                }

                # 9. WebSocket Keyframe + Telemetry Broadcast
                success, encoded_jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if success:
                    await self.ws_manager.broadcast_frame_and_telemetry(
                        frame_jpeg_bytes=encoded_jpeg.tobytes(),
                        telemetry=telemetry,
                    )

                # Rate pacing
                elapsed = time.time() - loop_start
                sleep_time = max(0.005, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in pipeline loop: {e}", exc_info=True)
        finally:
            cap.release()
            self._running = False
            logger.info("Pipeline video capture released.")

    async def _process_incidents(
        self,
        frame: np.ndarray,
        violations: List[SafetyViolation],
        person_risks: Dict[int, RiskScore],
        scene_risk: SceneRiskScore,
        activities: Dict[int, str],
        timestamp: float,
    ):
        """Saves snapshots, logs to SQLite DB, and triggers non-blocking Gemini VLM."""
        for v in violations:
            track_id = v.track_id
            event_type = v.violation_type
            cooldown_key = f"{track_id}:{event_type}"
            last_logged = self._incident_cooldowns.get(cooldown_key, 0.0)

            # 5-second cooldown per track per event type to prevent database spamming
            if timestamp - last_logged < 5.0:
                continue

            self._incident_cooldowns[cooldown_key] = timestamp
            risk_obj = person_risks.get(track_id)
            risk_score = risk_obj.score if risk_obj else 60.0
            risk_level = risk_obj.level if risk_obj else "HIGH"

            # 1. Save Snapshot Image
            snapshot_path = self.db.save_snapshot(
                frame=frame,
                incident_prefix=f"{event_type.lower()}_t{track_id}",
            )

            # 2. Insert DB Record
            record = SafetyIncidentRecord(
                timestamp=timestamp,
                track_id=track_id,
                event_type=event_type,
                risk_level=risk_level,
                risk_score=risk_score,
                activity=activities.get(track_id, "unknown"),
                confidence=v.confidence,
                snapshot_path=snapshot_path,
                contributing_factors=risk_obj.contributing_factors if risk_obj else [event_type],
                resolved=False,
            )
            incident_id = self.db.insert_incident(record)
            logger.info(f"Logged Incident #{incident_id}: {event_type} (Track #{track_id}, Risk: {risk_score:.1f})")

            # 3. Dispatch Async Gemini VLM Verification in background
            self._trigger_vlm_verification(
                incident_id=incident_id,
                frame=frame,
                event_type=event_type,
                track_id=track_id,
                risk_score=risk_score,
                activity=record.activity,
                contributing_factors=record.contributing_factors,
            )

    def _trigger_vlm_verification(
        self,
        incident_id: int,
        frame: np.ndarray,
        event_type: str,
        track_id: int,
        risk_score: float,
        activity: str,
        contributing_factors: List[str],
    ):
        """Asynchronously audits incident with Gemini 1.5 Flash in a background task."""
        async def _vlm_worker():
            try:
                explanation = await self.vlm.verify_incident_async(
                    image_bgr=frame,
                    event_type=event_type,
                    track_id=track_id,
                    risk_score=risk_score,
                    telemetry_context={
                        "activity": activity,
                        "contributing_factors": contributing_factors,
                    },
                )

                # Persist VLM audit summary to database
                self.db.update_vlm_explanation(incident_id, explanation)
                logger.info(
                    f"VLM verified incident #{incident_id}: "
                    f"Verified={explanation.verified}, Summary='{explanation.summary}'"
                )

                # Broadcast update to connected WebSocket frontend clients
                await self.ws_manager.broadcast_json({
                    "type": "INCIDENT_VERIFIED",
                    "incident_id": incident_id,
                    "vlm_explanation": explanation.to_dict(),
                })
            except Exception as e:
                logger.error(f"Failed VLM async verification for incident #{incident_id}: {e}")

        asyncio.create_task(_vlm_worker())


_runner: Optional[PipelineRunner] = None


def get_pipeline_runner() -> PipelineRunner:
    global _runner
    if _runner is None:
        _runner = PipelineRunner()
    return _runner

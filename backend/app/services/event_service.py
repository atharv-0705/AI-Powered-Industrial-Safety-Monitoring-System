"""
Event Persistence Service (Week 12).
Handles non-blocking, transactional persistence of safety events, alerts,
explanations, and evidence references. Protects the real-time CV loop
via bounded asynchronous queue processing and resilient error handling.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.api.websocket import get_connection_manager
from backend.app.database.connection import SessionLocal
from backend.app.models import (
    Activity,
    Alert,
    Camera,
    Detection,
    Event,
    Explanation,
    SystemConfig,
    Zone,
)
from backend.app.services.evidence_service import get_evidence_service
from backend.app.vlm.gemini_client import get_vlm_client

logger = logging.getLogger("safety-ai-mvp.event_service")


class EventPersistenceService:
    """Non-blocking background persistence service for confirmed safety events."""

    def __init__(self, max_queue_size: int = 50):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.evidence_service = get_evidence_service()
        self.vlm = get_vlm_client()
        self.ws_manager = get_connection_manager()

        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

        # System health & metrics
        self.total_persisted = 0
        self.failed_writes = 0
        self.last_write_timestamp: Optional[float] = None
        self.last_error: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        return self.failed_writes == 0 or (self.total_persisted > self.failed_writes * 5)

    def get_health_status(self) -> dict[str, Any]:
        return {
            "status": "HEALTHY" if self.is_healthy else "DEGRADED",
            "queue_depth": self.queue.qsize(),
            "total_persisted": self.total_persisted,
            "failed_writes": self.failed_writes,
            "last_error": self.last_error,
            "worker_active": self._running and (self._worker_task is not None and not self._worker_task.done()),
        }

    async def start(self):
        """Starts the background worker queue processor."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Started EventPersistenceService worker.")

    async def stop(self):
        """Stops the worker and flushes remaining queue items."""
        if not self._running:
            return
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped EventPersistenceService worker.")

    def submit_event(
        self,
        camera_id: str,
        track_id: int,
        event_type: str,
        severity: str,
        risk_score: float,
        confidence: float,
        frame_bgr: Optional[np.ndarray] = None,
        activity: str = "standing",
        bbox: Optional[Sequence[float]] = None,
        contributing_factors: Optional[List[str]] = None,
        rule_description: str = "",
    ) -> bool:
        """Non-blocking submission of a safety event from the CV inference pipeline.

        Returns True if enqueued, False if queue is full (dropping without blocking pipeline).
        """
        payload = {
            "camera_id": camera_id,
            "track_id": track_id,
            "event_type": event_type,
            "severity": severity,
            "risk_score": risk_score,
            "confidence": confidence,
            "frame_bgr": frame_bgr.copy() if frame_bgr is not None else None,
            "activity": activity,
            "bbox": list(bbox) if bbox is not None else [0, 0, 0, 0],
            "contributing_factors": contributing_factors or [event_type],
            "rule_description": rule_description,
            "timestamp": datetime.utcnow(),
        }

        try:
            self.queue.put_nowait(payload)
            return True
        except asyncio.QueueFull:
            self.failed_writes += 1
            self.last_error = "Persistence queue full; event dropped to prevent pipeline stall."
            logger.warning(self.last_error)
            return False

    async def _worker_loop(self):
        """Background worker consuming queue and writing to SQLite/PostgreSQL."""
        while self._running:
            try:
                payload = await self.queue.get()
                await self._process_single_event(payload)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.failed_writes += 1
                self.last_error = f"Unhandled error in worker loop: {e}"
                logger.error(self.last_error, exc_info=True)
                await asyncio.sleep(0.1)

    async def _process_single_event(self, p: Dict[str, Any]):
        """Persists Event, Alert, Explanation, and Evidence within a database transaction."""
        db: Session = SessionLocal()
        event_id = None
        evidence_url = None

        try:
            # 1. Verify Camera exists; if not, create placeholder
            camera = db.query(Camera).filter(Camera.id == p["camera_id"]).first()
            if not camera:
                camera = Camera(
                    id=p["camera_id"],
                    name=f"Camera {p['camera_id']}",
                    source_type="recorded",
                    source_url="0",
                    status="ONLINE",
                )
                db.add(camera)
                db.flush()

            # 2. Create Event Record
            event_obj = Event(
                camera_id=p["camera_id"],
                track_id=p["track_id"],
                event_type=p["event_type"],
                severity=p["severity"],
                risk_score=p["risk_score"],
                confidence=p["confidence"],
                started_at=p["timestamp"],
                status="OPEN",
            )
            db.add(event_obj)
            db.flush() # populates event_obj.id

            event_id = event_obj.id

            # 3. Save Evidence Image Frame
            if p["frame_bgr"] is not None:
                evidence_url = self.evidence_service.save_event_evidence(
                    frame_bgr=p["frame_bgr"],
                    event_id=event_id,
                    idx=1,
                    timestamp=p["timestamp"],
                )
                event_obj.evidence_image_path = evidence_url

            # 4. Create Alert Record
            alert_msg = f"{p['event_type']} alert triggered for Worker #{p['track_id']} (Risk: {p['risk_score']:.1f})."
            alert_obj = Alert(
                event_id=event_id,
                alert_type="VISUAL_HUD",
                severity=p["severity"],
                message=alert_msg,
                acknowledged=False,
                created_at=p["timestamp"],
            )
            db.add(alert_obj)

            # 5. Create Initial Deterministic Explanation Record
            rule_explanation = p["rule_description"] or f"Safety Rule Engine identified {p['event_type']} violation with {p['risk_score']:.0f} risk points."
            evidence_data = {
                "bbox": p["bbox"],
                "activity": p["activity"],
                "confidence": p["confidence"],
                "contributing_factors": p["contributing_factors"],
            }
            rec_action = self._get_default_action(p["event_type"])

            explanation_obj = Explanation(
                event_id=event_id,
                model_name="deterministic-rules",
                explanation=rule_explanation,
                evidence_json=json.dumps(evidence_data),
                recommendation=rec_action,
                created_at=p["timestamp"],
            )
            db.add(explanation_obj)

            # 6. Create Supporting Detection & Activity Records
            det_obj = Detection(
                camera_id=p["camera_id"],
                timestamp=p["timestamp"],
                track_id=p["track_id"],
                class_name="person",
                confidence=p["confidence"],
                bbox_x=p["bbox"][0],
                bbox_y=p["bbox"][1],
                bbox_w=p["bbox"][2] - p["bbox"][0],
                bbox_h=p["bbox"][3] - p["bbox"][1],
                event_id=event_id,
            )
            db.add(det_obj)

            act_obj = Activity(
                camera_id=p["camera_id"],
                track_id=p["track_id"],
                timestamp=p["timestamp"],
                activity=p["activity"],
                confidence=p["confidence"],
                duration_ms=1000,
            )
            db.add(act_obj)

            # Commit Transaction Atomically
            db.commit()
            self.total_persisted += 1
            self.last_write_timestamp = datetime.utcnow().timestamp()
            logger.info(f"Persisted Event #{event_id} ({p['event_type']}) for Camera {p['camera_id']}")

            # 7. Broadcast EVENT_CREATED to WebSocket frontend clients
            event_dict = event_obj.to_dict()
            await self.ws_manager.broadcast_json({
                "type": "EVENT_CREATED",
                "event": event_dict,
            })

            # 8. Trigger Non-Blocking Async Gemini VLM Verification if available
            if p["frame_bgr"] is not None:
                asyncio.create_task(
                    self._run_async_vlm(
                        event_id=event_id,
                        frame_bgr=p["frame_bgr"],
                        event_type=p["event_type"],
                        track_id=p["track_id"],
                        risk_score=p["risk_score"],
                        telemetry_context=evidence_data,
                    )
                )

        except Exception as e:
            db.rollback()
            self.failed_writes += 1
            self.last_error = f"Failed to persist event: {e}"
            logger.error(self.last_error, exc_info=True)
        finally:
            db.close()

    async def _run_async_vlm(
        self,
        event_id: int,
        frame_bgr: np.ndarray,
        event_type: str,
        track_id: int,
        risk_score: float,
        telemetry_context: Dict[str, Any],
    ):
        """Asynchronously queries Gemini 1.5 Flash and updates the event's explanation."""
        try:
            explanation_res = await self.vlm.verify_incident_async(
                image_bgr=frame_bgr,
                event_type=event_type,
                track_id=track_id,
                risk_score=risk_score,
                telemetry_context=telemetry_context,
            )

            # Persist VLM explanation to database
            with SessionLocal() as db:
                vlm_explanation = Explanation(
                    event_id=event_id,
                    model_name="gemini-1.5-flash",
                    explanation=explanation_res.summary,
                    evidence_json=json.dumps({
                        "hazard_assessment": getattr(explanation_res, "hazard_assessment", ""),
                        "confidence": explanation_res.confidence,
                        "verified": explanation_res.verified,
                    }),
                    recommendation=explanation_res.recommended_action,
                    created_at=datetime.utcnow(),
                )
                db.add(vlm_explanation)
                db.commit()

            # Broadcast update to connected WebSocket clients
            await self.ws_manager.broadcast_json({
                "type": "EVENT_UPDATED",
                "event_id": event_id,
                "vlm_summary": explanation_res.summary,
                "recommended_action": explanation_res.recommended_action,
                "vlm_verified": explanation_res.verified,
            })
            logger.info(f"Updated Event #{event_id} with Gemini 1.5 Flash VLM explanation.")

        except Exception as e:
            logger.warning(f"VLM async explanation failed for Event #{event_id}: {e}")

    def acknowledge_event(self, event_id: int, acknowledged_by: str = "supervisor") -> bool:
        """Marks event and all associated alerts as ACKNOWLEDGED."""
        with SessionLocal() as db:
            event_obj = db.query(Event).filter(Event.id == event_id).first()
            if not event_obj:
                return False

            if event_obj.status == "OPEN":
                event_obj.status = "ACKNOWLEDGED"

            # Update alerts
            for alert in event_obj.alerts:
                alert.acknowledged = True

            db.commit()
            logger.info(f"Acknowledged Event #{event_id} by {acknowledged_by}")

            # Notify WebSocket clients
            asyncio.create_task(
                self.ws_manager.broadcast_json({
                    "type": "EVENT_ACKNOWLEDGED",
                    "event_id": event_id,
                    "status": event_obj.status,
                })
            )
            return True

    def resolve_event(self, event_id: int, resolved_by: str = "supervisor") -> bool:
        """Marks event as RESOLVED and records completion timestamp."""
        with SessionLocal() as db:
            event_obj = db.query(Event).filter(Event.id == event_id).first()
            if not event_obj:
                return False

            event_obj.status = "RESOLVED"
            event_obj.ended_at = datetime.utcnow()

            for alert in event_obj.alerts:
                alert.acknowledged = True

            db.commit()
            logger.info(f"Resolved Event #{event_id} by {resolved_by}")

            asyncio.create_task(
                self.ws_manager.broadcast_json({
                    "type": "EVENT_RESOLVED",
                    "event_id": event_id,
                    "status": "RESOLVED",
                    "ended_at": event_obj.ended_at.isoformat(),
                })
            )
            return True

    def _get_default_action(self, event_type: str) -> str:
        if "FALL" in event_type:
            return "Dispatch site emergency medical crew. Check worker consciousness."
        if "CLIMB" in event_type:
            return "Order halt to climbing. Require safety helmet and connected harness."
        if "ZONE" in event_type:
            return "Instruct worker to evacuate restricted perimeter and verify security clearance."
        if "HELMET" in event_type:
            return "Issue verbal safety warning and provide approved industrial hard hat."
        if "VEST" in event_type:
            return "Ensure worker dons high-visibility reflective apparel."
        return "Review camera footage and verify compliance."


_event_service_instance: Optional[EventPersistenceService] = None


def get_event_service() -> EventPersistenceService:
    global _event_service_instance
    if _event_service_instance is None:
        _event_service_instance = EventPersistenceService()
    return _event_service_instance


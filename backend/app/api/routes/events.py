"""
Events & Alerts REST API Endpoints (Week 12).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.models import Alert, Event
from backend.app.schemas.alert import AlertOut
from backend.app.schemas.event import (
    AcknowledgeRequest,
    EventDetailOut,
    EventOut,
)
from backend.app.services.event_service import get_event_service

router = APIRouter(tags=["events"])


@router.get("/events", response_model=List[EventOut])
def list_events(
    severity: Optional[str] = Query(None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    status: Optional[str] = Query(None, description="Filter by status: OPEN, ACKNOWLEDGED, RESOLVED"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=200, description="Page limit"),
    db: Session = Depends(get_db),
):
    """Retrieves paginated, filtered safety events."""
    query = db.query(Event)

    if severity and severity != "ALL":
        query = query.filter(Event.severity == severity.upper())
    if event_type and event_type != "ALL":
        query = query.filter(Event.event_type == event_type.upper())
    if camera_id and camera_id != "ALL":
        query = query.filter(Event.camera_id == camera_id)
    if status and status != "ALL":
        query = query.filter(Event.status == status.upper())

    offset = (page - 1) * limit
    events = query.order_by(Event.started_at.desc()).offset(offset).limit(limit).all()

    return [e.to_dict() for e in events]


@router.get("/events/{event_id}", response_model=EventDetailOut)
def get_event_details(event_id: int, db: Session = Depends(get_db)):
    """Retrieves single event with associated alerts and 3-tier explanations."""
    event_obj = db.query(Event).filter(Event.id == event_id).first()
    if not event_obj:
        raise HTTPException(status_code=404, detail=f"Event #{event_id} not found")

    d = event_obj.to_dict()
    d["alerts"] = [a.to_dict() for a in event_obj.alerts]
    d["explanations"] = [exp.to_dict() for exp in event_obj.explanations]
    return d


@router.post("/events/{event_id}/acknowledge")
def acknowledge_event(
    event_id: int,
    req: AcknowledgeRequest = AcknowledgeRequest(),
):
    """Marks an event and its alerts as ACKNOWLEDGED by a supervisor."""
    service = get_event_service()
    success = service.acknowledge_event(event_id, acknowledged_by=req.acknowledged_by or "supervisor")
    if not success:
        raise HTTPException(status_code=404, detail=f"Event #{event_id} not found")
    return {"success": True, "message": f"Event #{event_id} acknowledged."}


@router.post("/events/{event_id}/resolve")
def resolve_event(
    event_id: int,
    req: AcknowledgeRequest = AcknowledgeRequest(),
):
    """Marks an event as RESOLVED and records conclusion timestamp."""
    service = get_event_service()
    success = service.resolve_event(event_id, resolved_by=req.acknowledged_by or "supervisor")
    if not success:
        raise HTTPException(status_code=404, detail=f"Event #{event_id} not found")
    return {"success": True, "message": f"Event #{event_id} resolved."}


@router.get("/alerts", response_model=List[AlertOut])
def list_alerts(
    unacknowledged_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Retrieves safety alerts across all cameras."""
    query = db.query(Alert)
    if unacknowledged_only:
        query = query.filter(Alert.acknowledged == False)
    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()
    return [a.to_dict() for a in alerts]


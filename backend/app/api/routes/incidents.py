"""
Incident REST API Endpoints (SRS §8.6, FR-22, Week 10).

Provides CRUD operations, status filtering, resolution tracking,
and statistics for safety incidents.
"""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.db.database import get_incident_db
from backend.app.db.models import SafetyIncidentRecord

router = APIRouter(prefix="/incidents", tags=["incidents"])


class ResolveResponse(BaseModel):
    success: bool
    incident_id: int
    message: str


@router.get("", response_model=List[dict])
def list_incidents(
    risk_level: Optional[str] = Query(None, description="Filter by risk tier: LOW, MEDIUM, HIGH, CRITICAL"),
    event_type: Optional[str] = Query(None, description="Filter by violation type: FALL, MISSING_HELMET, etc."),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
):
    """Lists logged safety incidents with optional severity and status filters."""
    db = get_incident_db()
    records = db.list_incidents(
        risk_level=risk_level,
        event_type=event_type,
        resolved=resolved,
        limit=limit,
        offset=offset,
    )
    return [r.to_dict() for r in records]


@router.get("/stats/summary")
def get_incident_statistics() -> dict[str, Any]:
    """Returns incident counts, resolution status, and severity distributions."""
    db = get_incident_db()
    return db.get_statistics()


@router.get("/{incident_id}", response_model=dict)
def get_incident(incident_id: int):
    """Retrieves a single incident by ID."""
    db = get_incident_db()
    incident = db.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident #{incident_id} not found")
    return incident.to_dict()


@router.post("/{incident_id}/resolve", response_model=ResolveResponse)
def resolve_incident(incident_id: int):
    """Marks an active incident as resolved."""
    db = get_incident_db()
    success = db.resolve_incident(incident_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Incident #{incident_id} not found")
    return ResolveResponse(
        success=True,
        incident_id=incident_id,
        message=f"Incident #{incident_id} marked as resolved.",
    )

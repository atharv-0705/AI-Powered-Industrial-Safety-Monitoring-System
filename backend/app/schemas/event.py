"""
Pydantic Event Schemas (Week 12).
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from backend.app.schemas.alert import AlertOut


class EventBase(BaseModel):
    camera_id: str
    track_id: int
    event_type: str
    severity: str
    risk_score: float
    confidence: float = 1.0


class EventCreate(EventBase):
    pass


class EventOut(EventBase):
    id: int
    camera_name: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    status: str
    evidence_image_path: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    alerts_count: int = 0
    vlm_summary: Optional[str] = None
    recommended_action: Optional[str] = None
    vlm_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class ExplanationOut(BaseModel):
    id: int
    event_id: int
    model_name: str
    explanation: str
    evidence: Dict[str, Any]
    recommendation: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EventDetailOut(EventOut):
    alerts: List[AlertOut] = []
    explanations: List[ExplanationOut] = []


class AcknowledgeRequest(BaseModel):
    acknowledged_by: Optional[str] = "supervisor"
    notes: Optional[str] = None


"""
Pydantic Alert Schemas (Week 12).
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    id: int
    event_id: int
    alert_type: str
    severity: str
    message: str
    acknowledged: bool
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


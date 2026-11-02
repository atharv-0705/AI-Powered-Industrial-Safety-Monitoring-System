"""
Pydantic Settings & System Config Schemas (Week 12).
"""
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class SafetySettingsSchema(BaseModel):
    fallAspectRatioThreshold: float = Field(0.8, ge=0.4, le=1.5)
    fallConfirmationFrames: int = Field(6, ge=1, le=30)
    helmetPersistenceFrames: int = Field(5, ge=1, le=30)
    zonePersistenceFrames: int = Field(3, ge=1, le=30)
    riskDecayHalfLifeSeconds: float = Field(3.0, ge=0.5, le=15.0)
    persistenceEscalationRate: float = Field(2.0, ge=0.5, le=10.0)
    vlmEnabled: bool = True
    vlmRateLimitSeconds: int = Field(10, ge=1, le=60)
    processingFps: int = Field(12, ge=1, le=60)
    detectionConfidenceThreshold: float = Field(0.4, ge=0.1, le=1.0)
    ppeConfidenceThreshold: float = Field(0.4, ge=0.1, le=1.0)


class SystemConfigOut(BaseModel):
    id: int
    key: str
    value: Dict[str, Any]
    version: int
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


"""
SQLAlchemy Event Model (Week 12).
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.database.base import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    camera_id = Column(String(50), ForeignKey("cameras.id"), nullable=False, index=True)
    track_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True) # FALL, NO_HELMET, RESTRICTED_ZONE_ENTRY, NO_VEST, DANGEROUS_CLIMB
    severity = Column(String(20), nullable=False, index=True) # LOW, MEDIUM, HIGH, CRITICAL
    risk_score = Column(Float, nullable=False)
    confidence = Column(Float, default=1.0)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False, default="OPEN", index=True) # OPEN, ACKNOWLEDGED, RESOLVED
    evidence_image_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    camera = relationship("Camera", back_populates="events")
    alerts = relationship("Alert", back_populates="event", cascade="all, delete-orphan")
    explanations = relationship("Explanation", back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_events_camera_severity", "camera_id", "severity"),
        Index("idx_events_type_status", "event_type", "status"),
        Index("idx_events_started_at_desc", started_at.desc()),
    )

    def to_dict(self):
        latest_explanation = self.explanations[-1] if self.explanations else None
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "camera_name": self.camera.name if self.camera else self.camera_id,
            "track_id": self.track_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
            "evidence_image_path": self.evidence_image_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "alerts_count": len(self.alerts) if self.alerts else 0,
            "vlm_summary": latest_explanation.explanation if latest_explanation else None,
            "recommended_action": latest_explanation.recommendation if latest_explanation else None,
            "vlm_verified": (latest_explanation.model_name == "gemini-1.5-flash") if latest_explanation else False,
        }


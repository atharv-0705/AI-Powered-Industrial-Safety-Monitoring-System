"""
SQLAlchemy Alert Model (Week 12).
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.database.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False) # VISUAL_HUD, SOUND_ALARM, NOTIFICATION
    severity = Column(String(20), nullable=False) # LOW, MEDIUM, HIGH, CRITICAL
    message = Column(Text, nullable=False)
    acknowledged = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    event = relationship("Event", back_populates="alerts")

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "acknowledged": self.acknowledged,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


"""
SQLAlchemy Activity Model (Week 12).
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String

from backend.app.database.base import Base


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    camera_id = Column(String(50), nullable=False, index=True)
    track_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    activity = Column(String(50), nullable=False, index=True) # standing, sitting, walking, climbing, running
    confidence = Column(Float, default=1.0)
    duration_ms = Column(Integer, default=1000)

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "activity": self.activity,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
        }


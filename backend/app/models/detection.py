"""
SQLAlchemy Detection Model (Week 12).
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from backend.app.database.base import Base


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    camera_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    track_id = Column(Integer, nullable=False, index=True)
    class_name = Column(String(50), nullable=False, default="person")
    confidence = Column(Float, nullable=False)
    bbox_x = Column(Float, nullable=False)
    bbox_y = Column(Float, nullable=False)
    bbox_w = Column(Float, nullable=False)
    bbox_h = Column(Float, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "track_id": self.track_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "bbox": [self.bbox_x, self.bbox_y, self.bbox_w, self.bbox_h],
            "event_id": self.event_id,
        }


"""
SQLAlchemy Camera Model (Week 12).
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.orm import relationship

from backend.app.database.base import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False, default="webcam") # webcam, rtsp, recorded, static
    source_url = Column(String(500), nullable=False, default="0")
    resolution = Column(String(50), default="1280x720")
    target_fps = Column(Float, default=12.0)
    status = Column(String(50), default="ONLINE") # ONLINE, OFFLINE, WARNING
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    zones = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="camera")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "resolution": self.resolution,
            "target_fps": self.target_fps,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


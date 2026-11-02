"""
SQLAlchemy Zone Model (Week 12).
"""
import json
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from backend.app.database.base import Base


class Zone(Base):
    __tablename__ = "zones"

    id = Column(String(50), primary_key=True, index=True)
    camera_id = Column(String(50), ForeignKey("cameras.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    polygon_json = Column(Text, nullable=False, default="[]") # JSON list of [x, y] coordinates
    zone_type = Column(String(50), default="restricted") # restricted, hazard, pedestrian
    risk_modifier = Column(Float, default=35.0)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    camera = relationship("Camera", back_populates="zones")

    @property
    def vertices(self):
        try:
            return json.loads(self.polygon_json)
        except Exception:
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "name": self.name,
            "polygon_json": self.polygon_json,
            "vertices": self.vertices,
            "zone_type": self.zone_type,
            "risk_modifier": self.risk_modifier,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


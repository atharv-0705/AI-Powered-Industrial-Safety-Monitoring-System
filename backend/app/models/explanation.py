"""
SQLAlchemy Explanation Model (Week 12).
"""
import json
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.database.base import Base


class Explanation(Base):
    __tablename__ = "explanations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    model_name = Column(String(100), nullable=False) # e.g. "gemini-1.5-flash", "deterministic-rules"
    explanation = Column(Text, nullable=False)
    evidence_json = Column(Text, nullable=True, default="{}")
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    event = relationship("Event", back_populates="explanations")

    @property
    def evidence(self):
        try:
            return json.loads(self.evidence_json)
        except Exception:
            return {}

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "model_name": self.model_name,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


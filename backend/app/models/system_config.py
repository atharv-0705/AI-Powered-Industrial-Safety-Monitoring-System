"""
SQLAlchemy SystemConfig Model (Week 12).
"""
import json
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.app.database.base import Base


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value_json = Column(Text, nullable=False, default="{}")
    version = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def value(self):
        try:
            return json.loads(self.value_json)
        except Exception:
            return {}

    @value.setter
    def value(self, val):
        self.value_json = json.dumps(val)

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "version": self.version,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


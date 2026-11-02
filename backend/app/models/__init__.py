"""
SQLAlchemy Database Models Package.
Exports all 8 core models for Week 12.
"""
from backend.app.database.base import Base
from backend.app.models.camera import Camera
from backend.app.models.zone import Zone
from backend.app.models.detection import Detection
from backend.app.models.activity import Activity
from backend.app.models.event import Event
from backend.app.models.alert import Alert
from backend.app.models.explanation import Explanation
from backend.app.models.system_config import SystemConfig

__all__ = [
    "Base",
    "Camera",
    "Zone",
    "Detection",
    "Activity",
    "Event",
    "Alert",
    "Explanation",
    "SystemConfig",
]


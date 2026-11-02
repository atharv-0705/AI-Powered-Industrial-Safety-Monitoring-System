"""
Pydantic Zone Schemas (Week 12).
"""
from typing import List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, field_validator


class ZoneBase(BaseModel):
    camera_id: str
    name: str
    vertices: List[Tuple[float, float]] # [(x, y), ...]
    zone_type: str = "restricted" # restricted, hazard, pedestrian
    risk_modifier: float = 35.0
    enabled: bool = True

    @field_validator("vertices")
    @classmethod
    def validate_vertices(cls, v):
        if len(v) < 3:
            raise ValueError("A polygon zone requires at least 3 vertices.")
        return v


class ZoneCreate(ZoneBase):
    id: Optional[str] = None


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    vertices: Optional[List[Tuple[float, float]]] = None
    zone_type: Optional[str] = None
    risk_modifier: Optional[float] = None
    enabled: Optional[bool] = None


class ZoneOut(ZoneBase):
    id: str
    polygon_json: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


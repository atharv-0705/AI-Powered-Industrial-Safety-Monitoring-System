"""
Pydantic Camera Schemas (Week 12).
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CameraBase(BaseModel):
    name: str
    source_type: str = "webcam" # webcam, rtsp, recorded, static
    source_url: str = "0"
    resolution: str = "1280x720"
    target_fps: float = 12.0
    status: str = "ONLINE"
    active: Optional[bool] = None


class CameraCreate(CameraBase):
    id: str


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    resolution: Optional[str] = None
    target_fps: Optional[float] = None
    status: Optional[str] = None


class CameraOut(CameraBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


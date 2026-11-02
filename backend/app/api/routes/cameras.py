"""
Cameras REST API Endpoints (Week 12).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.models import Camera
from backend.app.schemas.camera import CameraCreate, CameraOut, CameraUpdate

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("", response_model=List[CameraOut])
def list_cameras(db: Session = Depends(get_db)):
    cameras = db.query(Camera).all()
    return [c.to_dict() for c in cameras]


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    return cam.to_dict()


@router.post("", response_model=CameraOut)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    existing = db.query(Camera).filter(Camera.id == payload.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Camera {payload.id} already exists")

    cam = Camera(
        id=payload.id,
        name=payload.name,
        source_type=payload.source_type,
        source_url=payload.source_url,
        resolution=payload.resolution,
        target_fps=payload.target_fps,
        status=payload.status,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam.to_dict()


@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: str, payload: CameraUpdate, db: Session = Depends(get_db)):
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(cam, field, val)

    db.commit()
    db.refresh(cam)
    return cam.to_dict()


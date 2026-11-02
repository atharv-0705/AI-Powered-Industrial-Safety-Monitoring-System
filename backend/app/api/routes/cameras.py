"""
Cameras REST API Endpoints (Week 12).
"""
from pathlib import Path
import re
from typing import List
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.models import Camera
from backend.app.schemas.camera import CameraCreate, CameraOut, CameraUpdate

router = APIRouter(prefix="/cameras", tags=["cameras"])
VIDEO_DIR = Path("data/videos")
MAX_VIDEO_BYTES = 500 * 1024 * 1024


@router.get("", response_model=List[CameraOut])
def list_cameras(db: Session = Depends(get_db)):
    cameras = db.query(Camera).all()
    from backend.app.core.pipeline_runner import get_pipeline_runner
    runner = get_pipeline_runner()
    active_source = runner.get_status().get("video_source") if runner.is_running else None
    payload = [c.to_dict() for c in cameras]
    if active_source:
        matched = False
        for camera in payload:
            camera["active"] = str(camera["source_url"]) == str(active_source)
            if camera["active"]:
                matched = True
                camera["status"] = "ONLINE"
        if not matched:
            active_path = Path(str(active_source))
            payload.append({
                "id": "CUSTOM-VIDEO", "name": active_path.name or "Active Stream",
                "source_type": "recorded", "source_url": str(active_source),
                "resolution": "1280x720", "target_fps": 0, "status": "ONLINE",
                "active": True, "created_at": None, "updated_at": None,
            })
    return payload


async def save_uploaded_video(file: UploadFile = File(...)):
    """Store a browser-uploaded video for pipeline use and event history."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg"}:
        raise HTTPException(status_code=400, detail="Unsupported video format")
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    original_name = Path(file.filename or "video").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_name).stem).strip("._") or "video"
    path = VIDEO_DIR / f"{uuid4().hex}_{safe_name}{suffix}"
    total = 0
    try:
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="Video exceeds 500 MB limit")
                output.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return {"name": original_name, "source": str(path).replace("\\", "/"), "url": f"/videos/{path.name}", "size": total}


def list_uploaded_videos():
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    return [
        {"name": path.name.split("_", 1)[-1], "source": str(path).replace("\\", "/"), "url": f"/videos/{path.name}", "size": path.stat().st_size, "modified": path.stat().st_mtime}
        for path in sorted(VIDEO_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if path.is_file()
    ]


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


"""Persistent local storage for user-uploaded source videos."""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

VIDEO_DIR = Path("data/videos")
MAX_VIDEO_BYTES = 500 * 1024 * 1024
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg"}


def save_uploaded_video(file: UploadFile) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        file.file.close()
        raise HTTPException(status_code=400, detail="Unsupported video format")
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    original_name = Path(file.filename or "video").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original_name).stem).strip("._") or "video"
    path = VIDEO_DIR / f"{uuid4().hex}_{safe_name}{suffix}"
    total = 0
    try:
        with path.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="Video exceeds 500 MB limit")
                output.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()
    return {"name": original_name, "source": str(path).replace("\\", "/"), "url": f"/videos/{path.name}", "size": total}


def list_uploaded_videos() -> list[dict]:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    return [
        {"name": path.name.split("_", 1)[-1], "source": str(path).replace("\\", "/"), "url": f"/videos/{path.name}", "size": path.stat().st_size, "modified": path.stat().st_mtime}
        for path in sorted(VIDEO_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file()
    ]

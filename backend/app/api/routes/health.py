"""
GET /api/health (FR: system health and component status).

Week 1 scope: report API liveness + environment/GPU diagnostic.
From Week 10+ this will also report detector/tracker/DB/VLM component
status (SRS §13.2: "An application watchdog/health endpoint shall report
stream, detector, backend, database and optional VLM status").
"""
from fastapi import APIRouter

from backend.app.core.env_check import run_env_check

router = APIRouter()


@router.get("/health")
def health():
    env = run_env_check()
    return {
        "status": "ok",
        "api": "up",
        "environment": {
            "python_version": env.python_version,
            "opencv_ok": env.opencv_ok,
            "opencv_version": env.opencv_version,
            "ffmpeg_found": env.ffmpeg_found,
            "cuda_available": env.cuda_available,
            "gpu_name": env.gpu_name,
            "gpu_vram_gb": env.gpu_vram_gb,
        },
        # Placeholders — populated as each module comes online (Week 2+)
        "components": {
            "detector": "not_loaded",
            "tracker": "not_loaded",
            "pose": "not_loaded",
            "ppe": "not_loaded",
            "safety_engine": "not_loaded",
            "database": "not_configured",
            "vlm": "disabled",
        },
    }

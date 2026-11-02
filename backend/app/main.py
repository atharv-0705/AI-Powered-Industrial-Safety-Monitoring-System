"""
FastAPI skeleton (SRS §2.1, §7). Week 1 scope: app boots, CORS open for the
React dashboard, /api/health responds. WebSocket + detection/event routers
are added from Week 9-10 onward without changing this file's shape.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import websocket
from backend.app.api.routes import health, incidents
from backend.app.core.config import get_settings
from backend.app.core.pipeline_runner import get_pipeline_runner

settings = get_settings()

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("safety-ai-mvp")

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

# Local dev: React dashboard typically runs on :3000 or :5173 (Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open CORS for dev dashboard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for incident snapshots
snapshots_dir = Path("data/snapshots")
snapshots_dir.mkdir(parents=True, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=str(snapshots_dir)), name="snapshots")

# Mount API routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(incidents.router, prefix="/api")
app.include_router(websocket.router, tags=["websocket"])


@app.on_event("startup")
async def on_startup():
    logger.info(f"{settings.APP_NAME} starting up")
    logger.info(f"Configured video source: {settings.VIDEO_SOURCE}")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info(f"{settings.APP_NAME} shutting down...")
    runner = get_pipeline_runner()
    if runner.is_running:
        await runner.stop()


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} is running. See /api/health and /api/incidents."}


@app.post("/api/pipeline/start")
async def start_pipeline(source: str | None = None):
    runner = get_pipeline_runner()
    await runner.start(source_override=source)
    return {"status": "started", "details": runner.get_status()}


@app.post("/api/pipeline/stop")
async def stop_pipeline():
    runner = get_pipeline_runner()
    await runner.stop()
    return {"status": "stopped", "details": runner.get_status()}


@app.get("/api/pipeline/status")
def pipeline_status():
    runner = get_pipeline_runner()
    return runner.get_status()


"""
Database Engine, Session Management, and Initialization (Week 12).
Supports SQLite for development and PostgreSQL for production via DATABASE_URL.
"""
from __future__ import annotations

import json
import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import get_settings
from backend.app.database.base import Base
from backend.app.models import (
    Activity,
    Alert,
    Camera,
    Detection,
    Event,
    Explanation,
    SystemConfig,
    Zone,
)

logger = logging.getLogger("safety-ai-mvp.database")
settings = get_settings()

db_url = settings.DATABASE_URL

# Configure engine arguments
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Enable WAL mode and foreign keys for SQLite
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes schema and seeds default cameras and configurations if empty."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    logger.info("Initialized SQLAlchemy database schema.")

    # Seed default data
    db = SessionLocal()
    try:
        # Seed default cameras if none exist
        if db.query(Camera).count() == 0:
            default_cameras = [
                Camera(
                    id="CAM-01",
                    name="Tower Crane & Electrical Hub",
                    source_type="recorded",
                    source_url="source/Alone-man-climbing-SnapYT.App.mp4",
                    resolution="1920x1080",
                    target_fps=14.8,
                    status="ONLINE",
                ),
                Camera(
                    id="CAM-02",
                    name="Main Perimeter & Security Gate",
                    source_type="recorded",
                    source_url="source/cctv_27c12fe4.mp4",
                    resolution="1280x720",
                    target_fps=15.0,
                    status="ONLINE",
                ),
                Camera(
                    id="CAM-03",
                    name="Scaffolding & Facade Work",
                    source_type="static",
                    source_url="static_3",
                    resolution="1920x1080",
                    target_fps=12.0,
                    status="ONLINE",
                ),
                Camera(
                    id="CAM-04",
                    name="High-Voltage Transformer Bay",
                    source_type="static",
                    source_url="static_4",
                    resolution="1920x1080",
                    target_fps=11.4,
                    status="WARNING",
                ),
                Camera(
                    id="CAM-05",
                    name="Heavy Equipment Excavation Pit",
                    source_type="static",
                    source_url="static_5",
                    resolution="1920x1080",
                    target_fps=14.2,
                    status="ONLINE",
                ),
                Camera(
                    id="CAM-06",
                    name="Internal Warehouse & PPE Check",
                    source_type="webcam",
                    source_url="0",
                    resolution="1280x720",
                    target_fps=13.5,
                    status="ONLINE",
                ),
            ]
            db.add_all(default_cameras)
            db.commit()
            logger.info("Seeded 6 default cameras.")

        # Seed default restricted zones if none exist
        if db.query(Zone).count() == 0:
            default_zones = [
                Zone(
                    id="ZONE-01",
                    camera_id="CAM-01",
                    name="Crane Drop Perimeter",
                    polygon_json=json.dumps([[120, 320], [420, 310], [460, 470], [100, 475]]),
                    zone_type="hazard",
                    risk_modifier=35.0,
                    enabled=True,
                ),
                Zone(
                    id="ZONE-02",
                    camera_id="CAM-04",
                    name="High-Voltage Enclosure",
                    polygon_json=json.dumps([[240, 160], [580, 160], [600, 360], [210, 350]]),
                    zone_type="restricted",
                    risk_modifier=35.0,
                    enabled=True,
                ),
            ]
            db.add_all(default_zones)
            db.commit()
            logger.info("Seeded default hazard zones.")

        # Seed default system configs if none exist
        if db.query(SystemConfig).count() == 0:
            default_configs = [
                SystemConfig(
                    key="safety_thresholds",
                    value_json=json.dumps({
                        "fallAspectRatioThreshold": 0.8,
                        "fallConfirmationFrames": 6,
                        "helmetPersistenceFrames": 5,
                        "zonePersistenceFrames": 3,
                        "riskDecayHalfLifeSeconds": 3.0,
                        "persistenceEscalationRate": 2.0,
                        "vlmEnabled": True,
                        "vlmRateLimitSeconds": 10,
                        "processingFps": 12,
                        "detectionConfidenceThreshold": 0.4,
                        "ppeConfidenceThreshold": 0.4,
                    }),
                    version=1,
                ),
                SystemConfig(
                    key="evidence_retention",
                    value_json=json.dumps({
                        "retention_days": 30,
                        "max_snapshots_per_event": 3,
                        "compress_jpeg_quality": 85,
                    }),
                    version=1,
                ),
            ]
            db.add_all(default_configs)
            db.commit()
            logger.info("Seeded default system configs.")

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        db.rollback()
    finally:
        db.close()


"""
Externalized configuration (NFR-08: Configuration shall be externalized in
YAML/ENV configuration files). Everything downstream (ingestion, detection,
tracking, safety rules, VLM, DB) reads from this single Settings object
instead of hardcoded constants.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Multimodal Safety AI Monitor"
    HOST: str = "0.0.0.0"
    PORT: int = 8010
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Video ingestion (FR-01, FR-03)
    VIDEO_SOURCE: str = "0"          # "0" = webcam index 0, or a file path
    SOURCE_FPS: int = 30
    PROCESSING_FPS: int = 12
    MAX_QUEUE_SIZE: int = 2          # NFR: all queues shall be bounded

    # Detection + Tracking (FR-04, FR-06 — SRS §8.2 baseline table)
    DETECTOR_MODEL: str = "yolo11n.pt"   # baseline per SRS §8.2 — do not upgrade to yolo11s without profiling
    DETECTOR_CONF_THRESHOLD: float = 0.4
    DETECTOR_IMG_SIZE: int = 640          # SRS §8.2: 640-class input resolution
    DETECTOR_DEVICE: str = "auto"         # "auto" | "cuda:0" | "cpu"
    TRACKER_CONFIG: str = "bytetrack.yaml"

    # Human Activity Recognition (FR-08 — SRS §8.4)
    HAR_CHECKPOINT_PATH: str = "models/har_temporal_transformer.pt"
    HAR_DEVICE: str = "auto"

    # PPE Detection (Week 5, FR-05)
    PPE_MODEL_PATH: str = "models/ppe_yolo11n.pt"
    PPE_CONF_THRESHOLD: float = 0.4
    PPE_DEVICE: str = "auto"

    # Safety Rules & Thresholds (Week 6-8, FR-09..FR-15)
    FALL_ASPECT_RATIO_THRESHOLD: float = 0.8
    FALL_CONFIRMATION_FRAMES: int = 6
    RESTRICTED_ZONE_COORDS: str = "[]"  # JSON list of [x, y] polygon points (normalized 0-1)

    # VLM / Gemini API (Week 9, FR-16..FR-20)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    VLM_ENABLED: bool = False
    VLM_RATE_LIMIT_SECONDS: int = 10

    # Database (Week 10, FR-22)
    DATABASE_URL: str = "sqlite:///./data/safety_monitor.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()

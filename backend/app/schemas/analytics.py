"""
Pydantic Analytics Schemas (Week 12).
"""
from typing import Dict, List, Optional
from pydantic import BaseModel


class AnalyticsOverview(BaseModel):
    total_events: int
    open_alerts: int
    acknowledged_events: int
    resolved_events: int
    event_counts_by_camera: Dict[str, int]


class EventTypeCount(BaseModel):
    event_type: str
    count: int
    percentage: float


class SeverityDistribution(BaseModel):
    severity: str
    count: int
    percentage: float


class TimelinePoint(BaseModel):
    timestamp_bucket: str # Hourly, daily string
    total: int
    critical: int
    high: int
    medium: int
    low: int


class ActivityDistribution(BaseModel):
    activity: str
    count: int
    percentage: float


class PerformanceMetrics(BaseModel):
    avg_event_detection_latency_ms: float
    current_processing_fps: float
    system_status: str
    database_status: str
    false_alarm_count: int
    total_reviewed_count: int


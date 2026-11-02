"""
Computer vision and multimodal analysis pipeline stages:
Ingestion -> Detection/Tracking -> Pose -> Features -> HAR / PPE -> Safety Rules -> Risk Engine.
"""
from backend.pipeline.ingestion import VideoSource, FrameResult
from backend.pipeline.detector import PersonTracker, TrackedPerson
from backend.pipeline.pose import PoseEstimator, PoseResult
from backend.pipeline.features import TemporalFeatureManager
from backend.pipeline.har import ActivityRecognizer, ActivityPrediction
from backend.pipeline.ppe import PPEDetector, PersonPPEStatus, PPEDetection
from backend.pipeline.safety_engine import SafetyEngine, SafetyViolation, ZonePolygon
from backend.pipeline.risk_engine import RiskEngine, RiskScore, SceneRiskScore

__all__ = [
    "VideoSource",
    "FrameResult",
    "PersonTracker",
    "TrackedPerson",
    "PoseEstimator",
    "PoseResult",
    "TemporalFeatureManager",
    "ActivityRecognizer",
    "ActivityPrediction",
    "PPEDetector",
    "PersonPPEStatus",
    "PPEDetection",
    "SafetyEngine",
    "SafetyViolation",
    "ZonePolygon",
    "RiskEngine",
    "RiskScore",
    "SceneRiskScore",
]



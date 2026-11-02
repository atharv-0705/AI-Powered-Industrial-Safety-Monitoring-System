/**
 * Data contracts for Industrial Safety Monitoring (Weeks 1-11).
 * Aligned with FastAPI backend models and WebSocket streaming telemetry.
 */

export type SeverityLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ViolationType =
  | "FALL"
  | "MISSING_HELMET"
  | "MISSING_VEST"
  | "RESTRICTED_ZONE"
  | "DANGEROUS_CLIMB";

export type ActivityType =
  | "standing"
  | "sitting"
  | "walking"
  | "climbing"
  | "running"
  | "unknown";

export interface PPEStatus {
  has_helmet: boolean | null;
  has_vest: boolean | null;
}

export interface PersonTrack {
  track_id: number;
  bbox: [number, number, number, number]; // [x1, y1, x2, y2]
  activity: ActivityType;
  ppe?: PPEStatus | null;
  risk?: {
    score: number;
    level: SeverityLevel;
    factors: string[];
  } | null;
}

export interface LiveViolation {
  track_id: number;
  event_type: ViolationType;
  severity: SeverityLevel;
  confidence: number;
  description: string;
}

export interface SceneRiskTelemetry {
  overall_score: number;
  overall_level: SeverityLevel;
  summary: string;
  workers_at_risk: number;
  active_violations_count: number;
}

export interface StreamTelemetry {
  timestamp: string;
  frame_idx: number;
  fps: number;
  scene_risk: SceneRiskTelemetry;
  workers_count: number;
  tracks: PersonTrack[];
  violations: LiveViolation[];
}

export interface WebSocketFramePacket {
  type: "FRAME_UPDATE";
  frame: string; // Base64 data URL ("data:image/jpeg;base64,...")
  telemetry: StreamTelemetry;
}

export interface VLMExplanation {
  incident_id?: number | null;
  incident_type?: string;
  summary: string;
  risk_level: SeverityLevel;
  recommended_action: string;
  recommendations?: string[];
  confidence: number;
  verified: boolean;
  hazard_assessment?: string;
  timestamp?: number;
  model_used?: string;
}

export interface IncidentRecord {
  id?: number | null;
  timestamp: number;
  timestamp_iso: string;
  track_id: number;
  event_type: ViolationType;
  risk_level: SeverityLevel;
  risk_score: number;
  activity: string;
  confidence: number;
  bbox_xyxy: [number, number, number, number];
  snapshot_path?: string | null;
  video_path?: string | null;
  vlm_verified: boolean;
  vlm_summary?: string | null;
  recommended_action?: string | null;
  contributing_factors: string[];
  resolved: boolean;
  resolved_at?: number | null;
  camera_id?: string;
  camera_name?: string;
}

export interface IncidentStatsSummary {
  total_incidents: number;
  unresolved_incidents: number;
  resolved_incidents: number;
  by_severity: {
    CRITICAL: number;
    HIGH: number;
    MEDIUM: number;
    LOW: number;
  };
  by_event_type: Record<string, number>;
}

export interface PipelineStatus {
  running: boolean;
  fps: number;
  frame_count: number;
  scene_risk: number;
  video_source: string;
}

export interface SystemHealth {
  status: string;
  api: string;
  environment: {
    python_version: string;
    opencv_ok: boolean;
    opencv_version: string;
    ffmpeg_found: boolean;
    cuda_available: boolean;
    gpu_name: string;
    gpu_vram_gb: number;
  };
  components: {
    detector: string;
    tracker: string;
    pose: string;
    ppe: string;
    safety_engine: string;
    database: string;
    vlm: string;
  };
}


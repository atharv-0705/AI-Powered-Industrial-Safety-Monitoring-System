export interface SafetySettings {
  fallAspectRatioThreshold: number;
  fallConfirmationFrames: number;
  helmetPersistenceFrames: number;
  zonePersistenceFrames: number;
  riskDecayHalfLifeSeconds: number;
  persistenceEscalationRate: number;
  vlmEnabled: boolean;
  vlmRateLimitSeconds: number;
  processingFps: number;
  detectionConfidenceThreshold: number;
  ppeConfidenceThreshold: number;
}

export interface ModelHealthStatus {
  name: string;
  category: "DETECTOR" | "TRACKER" | "POSE" | "HAR" | "PPE" | "SAFETY" | "VLM" | "DB";
  status: "READY" | "DEGRADED" | "OFFLINE" | "LOADING";
  latencyMs: number;
  device: string;
  details: string;
}


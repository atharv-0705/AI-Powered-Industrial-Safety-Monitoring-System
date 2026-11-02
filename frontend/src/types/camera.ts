export interface CameraFeed {
  id: string;
  name: string;
  location: string;
  type: "webcam" | "rtsp" | "recorded" | "static";
  source: string; // "0" or file path or URL
  status: "ONLINE" | "OFFLINE" | "WARNING";
  currentFps: number;
  peopleCount: number;
  activeAlerts: number;
  resolution: string;
  thumbnailUrl?: string;
}

export interface ZonePolygon {
  id: string;
  name: string;
  cameraId: string;
  vertices: [number, number][]; // Normalized [x, y] in [0, 1] range or pixel coords
  zoneType: "restricted" | "hazard" | "pedestrian";
  color?: string;
  createdAt: string;
}


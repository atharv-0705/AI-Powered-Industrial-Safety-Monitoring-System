import React, { useRef, useEffect } from "react";
import { StreamTelemetry } from "@/types/safety";
import { ZonePolygon } from "@/types/camera";
import { OverlayVisibilityState } from "./OverlayControls";
import { AlertTriangle, VideoOff } from "lucide-react";

interface VideoCanvasProps {
  frame: string | null;
  telemetry: StreamTelemetry | null;
  zones?: ZonePolygon[];
  cameraName?: string;
  cameraId?: string;
  isLive?: boolean;
  isStale?: boolean;
  overlays?: OverlayVisibilityState;
  className?: string;
  onFullscreen?: () => void;
}

export const VideoCanvas: React.FC<VideoCanvasProps> = ({
  frame,
  telemetry,
  zones = [],
  cameraName = "CAM-01: Main Entrance & Crane Hub",
  cameraId = "CAM-01",
  isLive = true,
  isStale = false,
  overlays = {
    showBoundingBoxes: true,
    showLabels: true,
    showPPE: true,
    showZones: true,
    showRiskBadge: true,
  },
  className = "",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  // Initialize cached image object for drawing frames
  useEffect(() => {
    const img = new Image();
    imageRef.current = img;
  }, []);

  // Primary rendering loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // 1. Draw video background
    if (frame && imageRef.current) {
      imageRef.current.onload = () => {
        ctx.clearRect(0, 0, width, height);
        ctx.drawImage(imageRef.current!, 0, 0, width, height);
        drawOverlays(ctx, width, height);
      };
      imageRef.current.src = frame;
    } else {
      // Draw simulated synthetic industrial backdrop
      drawSyntheticBackdrop(ctx, width, height);
      drawOverlays(ctx, width, height);
    }
  }, [frame, telemetry, zones, overlays, isLive, isStale]);

  const drawSyntheticBackdrop = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number
  ) => {
    // Industrial dark blue-gray gradient
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, "#08101C");
    grad.addColorStop(0.6, "#0F1C30");
    grad.addColorStop(1, "#0A1322");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    // Architectural grid / scaffolding lines
    ctx.strokeStyle = "rgba(37, 51, 74, 0.4)";
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Scaffolding silhouette in background
    ctx.strokeStyle = "rgba(30, 41, 59, 0.8)";
    ctx.lineWidth = 2;
    // Crane boom
    ctx.beginPath();
    ctx.moveTo(100, height - 20);
    ctx.lineTo(100, 80);
    ctx.lineTo(width - 80, 50);
    ctx.stroke();

    // Crane cables
    ctx.strokeStyle = "rgba(51, 65, 85, 0.6)";
    ctx.beginPath();
    ctx.moveTo(width - 140, 52);
    ctx.lineTo(width - 140, 220);
    ctx.stroke();

    // Concrete floor boundary line
    ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
    ctx.fillRect(0, height - 70, width, 70);
    ctx.strokeStyle = "rgba(59, 130, 246, 0.25)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, height - 70);
    ctx.lineTo(width, height - 70);
    ctx.stroke();
  };

  const drawOverlays = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number
  ) => {
    // 1. Draw Restricted Hazard Zones
    if (overlays.showZones && zones.length > 0) {
      zones.forEach((zone) => {
        if (!zone.vertices || zone.vertices.length < 3) return;

        ctx.beginPath();
        const start = zone.vertices[0];
        ctx.moveTo((start[0] / 640) * width, (start[1] / 480) * height);
        for (let i = 1; i < zone.vertices.length; i++) {
          const v = zone.vertices[i];
          ctx.lineTo((v[0] / 640) * width, (v[1] / 480) * height);
        }
        ctx.closePath();

        // Fill with translucent hazard color
        ctx.fillStyle =
          zone.zoneType === "hazard"
            ? "rgba(239, 68, 68, 0.18)"
            : "rgba(249, 115, 22, 0.18)";
        ctx.fill();

        // Boundary stroke
        ctx.strokeStyle =
          zone.zoneType === "hazard" ? "#EF4444" : "#F97316";
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label
        const cx = (zone.vertices[0][0] / 640) * width + 8;
        const cy = (zone.vertices[0][1] / 480) * height + 16;
        ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
        ctx.fillRect(cx - 4, cy - 12, 140, 18);
        ctx.fillStyle = zone.zoneType === "hazard" ? "#EF4444" : "#F97316";
        ctx.font = "bold 10px monospace";
        ctx.fillText(`⛔ ${zone.name.toUpperCase()}`, cx, cy);
      });
    }

    // 2. Draw Tracked Persons and Violations
    if (telemetry && telemetry.tracks) {
      telemetry.tracks.forEach((track) => {
        // Normalize coordinates from 640x480 model space to canvas size
        const [rx1, ry1, rx2, ry2] = track.bbox;
        const x1 = (rx1 / 640) * width;
        const y1 = (ry1 / 480) * height;
        const w = ((rx2 - rx1) / 640) * width;
        const h = ((ry2 - ry1) / 480) * height;

        const riskScore = track.risk?.score || 0;
        const riskLevel = track.risk?.level || "LOW";

        const boxColor =
          riskLevel === "CRITICAL"
            ? "#EF4444"
            : riskLevel === "HIGH"
            ? "#F97316"
            : riskLevel === "MEDIUM"
            ? "#F59E0B"
            : "#10B981";

        // Draw Bounding Box
        if (overlays.showBoundingBoxes) {
          ctx.strokeStyle = boxColor;
          ctx.lineWidth = riskLevel === "CRITICAL" ? 3 : 2;
          ctx.strokeRect(x1, y1, w, h);

          // Corner accent ticks
          const tick = 10;
          ctx.fillStyle = boxColor;
          ctx.fillRect(x1 - 1, y1 - 1, tick, 3);
          ctx.fillRect(x1 - 1, y1 - 1, 3, tick);
          ctx.fillRect(x1 + w - tick + 1, y1 - 1, tick, 3);
          ctx.fillRect(x1 + w - 2, y1 - 1, 3, tick);
        }

        // Draw Header Badge: ID + Activity + Risk Score
        if (overlays.showLabels) {
          const badgeText = `#${track.track_id} ${track.activity.toUpperCase()} | ${riskScore.toFixed(0)} [${riskLevel}]`;
          ctx.font = "bold 11px monospace";
          const textWidth = ctx.measureText(badgeText).width;

          const tagY = Math.max(18, y1 - 6);
          ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
          ctx.fillRect(x1, tagY - 14, textWidth + 10, 18);

          ctx.strokeStyle = boxColor;
          ctx.lineWidth = 1;
          ctx.strokeRect(x1, tagY - 14, textWidth + 10, 18);

          ctx.fillStyle = boxColor;
          ctx.fillText(badgeText, x1 + 5, tagY);
        }

        // Draw PPE Badges
        if (overlays.showPPE && track.ppe) {
          const helmetText = track.ppe.has_helmet ? "H:OK" : "NO HELMET";
          const vestText = track.ppe.has_vest ? "V:OK" : "NO VEST";

          const ppeY = y1 + h + 16;
          ctx.font = "bold 10px monospace";

          // Helmet pill
          ctx.fillStyle = track.ppe.has_helmet ? "#10B981" : "#EF4444";
          ctx.fillText(helmetText, x1, ppeY);

          // Vest pill
          ctx.fillStyle = track.ppe.has_vest ? "#10B981" : "#F97316";
          ctx.fillText(vestText, x1 + 65, ppeY);
        }
      });
    }

    // 3. Top HUD Status Bar
    drawTopHUD(ctx, width);
  };

  const drawTopHUD = (ctx: CanvasRenderingContext2D, width: number) => {
    // Top bar background
    ctx.fillStyle = "rgba(11, 18, 32, 0.88)";
    ctx.fillRect(0, 0, width, 36);

    ctx.strokeStyle = "#25334A";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, 36);
    ctx.lineTo(width, 36);
    ctx.stroke();

    // Camera Name & ID
    ctx.fillStyle = "#38BDF8";
    ctx.font = "bold 12px sans-serif";
    ctx.fillText(`● REC | ${cameraId} : ${cameraName}`, 12, 23);

    // Live FPS and timestamp
    const fpsVal = telemetry?.fps ? telemetry.fps.toFixed(1) : "12.0";
    const frameIdx = telemetry?.frame_idx || 0;
    const workerCount = telemetry?.workers_count || 0;

    const statsText = `FPS: ${fpsVal} | FRAME: #${frameIdx} | WORKERS: ${workerCount}`;
    ctx.fillStyle = "#94A3B8";
    ctx.font = "11px monospace";
    ctx.fillText(statsText, width - 360, 23);

    // Scene Threat Gauge Indicator
    const sceneRisk = telemetry?.scene_risk?.overall_score || 0;
    const sceneLevel = telemetry?.scene_risk?.overall_level || "LOW";
    const threatColor =
      sceneLevel === "CRITICAL"
        ? "#EF4444"
        : sceneLevel === "HIGH"
        ? "#F97316"
        : sceneLevel === "MEDIUM"
        ? "#F59E0B"
        : "#10B981";

    ctx.fillStyle = threatColor;
    ctx.font = "bold 11px monospace";
    ctx.fillText(`THREAT: ${sceneRisk.toFixed(0)} [${sceneLevel}]`, width - 130, 23);
  };

  return (
    <div className={`relative w-full overflow-hidden rounded-xl bg-slate-950 border border-slate-800 shadow-2xl ${className}`}>
      {/* 16:9 Canvas container */}
      <div className="relative w-full aspect-video">
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          className="w-full h-full object-contain block bg-[#0B1220]"
        />

        {/* Live / Offline watermark indicator */}
        <div className="absolute top-11 left-3 flex items-center gap-2 pointer-events-none">
          <span
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase tracking-wider backdrop-blur-md ${
              isLive
                ? "bg-red-950/80 text-red-400 border border-red-700/60"
                : "bg-slate-900/80 text-slate-400 border border-slate-700/60"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isLive ? "bg-red-500 animate-pulse" : "bg-slate-500"
              }`}
            />
            {isLive ? "LIVE FEED" : "STANDBY"}
          </span>

          {isStale && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-amber-950/80 text-amber-300 border border-amber-700/60">
              <AlertTriangle className="w-3 h-3" />
              STREAM DELAY
            </span>
          )}
        </div>

        {/* Empty state fallback when camera feed is uninitialized */}
        {!frame && !telemetry && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-sm pointer-events-none">
            <VideoOff className="w-12 h-12 text-slate-600 mb-3" />
            <p className="text-slate-300 font-semibold text-sm">
              Connecting to Camera Stream...
            </p>
            <p className="text-slate-500 text-xs mt-1">
              Ensure FastAPI backend is running on :8010 or toggle DEMO MODE.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};


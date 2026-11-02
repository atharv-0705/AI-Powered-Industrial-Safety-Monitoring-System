import React, { useState, useEffect } from "react";
import { Link, useOutletContext } from "react-router-dom";
import {
  Camera,
  Users,
  AlertTriangle,
  Cpu,
  ArrowRight,
  ShieldAlert,
  Clock,
  Sparkles,
  CheckCircle2,
  HardHat,
} from "lucide-react";
import { VideoCanvas } from "@/components/video/VideoCanvas";
import { OverlayControls, OverlayVisibilityState } from "@/components/video/OverlayControls";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { RiskGauge } from "@/components/common/RiskGauge";
import { useSafetyWebSocket } from "@/hooks/useSafetyWebSocket";
import { apiService } from "@/services/api";
import { IncidentRecord, IncidentStatsSummary } from "@/types/safety";
import { ZonePolygon } from "@/types/camera";
import { formatDateTime, formatViolationName, formatSeverityColor } from "@/lib/utils";

export const Dashboard: React.FC = () => {
  const { selectedCameraId } = useOutletContext<{ selectedCameraId: string }>();
  const { frame, telemetry, isConnected, isStale, isDemoMode } = useSafetyWebSocket();

  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [stats, setStats] = useState<IncidentStatsSummary | null>(null);
  const [zones, setZones] = useState<ZonePolygon[]>([]);
  const [overlays, setOverlays] = useState<OverlayVisibilityState>({
    showBoundingBoxes: true,
    showLabels: true,
    showPPE: true,
    showZones: true,
    showRiskBadge: true,
  });

  // Load incidents, stats, and zones
  useEffect(() => {
    const loadData = async () => {
      const [incRes, statsRes, zonesRes] = await Promise.all([
        apiService.getIncidents({ limit: 10 }),
        apiService.getIncidentStats(),
        apiService.getZones(),
      ]);
      setIncidents(incRes.data);
      setStats(statsRes.data);
      setZones(zonesRes);
    };

    loadData();
    const timer = setInterval(loadData, 4000);
    return () => clearInterval(timer);
  }, []);

  const handleOverlayChange = (key: keyof OverlayVisibilityState, val: boolean) => {
    setOverlays((prev) => ({ ...prev, [key]: val }));
  };

  const activeIncidents = incidents.filter((i) => !i.resolved);
  const highestPriority = activeIncidents[0] || incidents[0] || null;

  const peopleCount = telemetry?.workers_count ?? 2;
  const fpsCount = telemetry?.fps ? telemetry.fps.toFixed(1) : "14.8";
  const sceneRisk = telemetry?.scene_risk?.overall_score ?? (highestPriority?.risk_score || 25);
  const sceneLevel = telemetry?.scene_risk?.overall_level ?? (highestPriority?.risk_level || "LOW");

  return (
    <div className="space-y-4">
      {/* 1. TOP OPERATIONAL KPI CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* KPI 1: Active Cameras */}
        <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A] flex items-center justify-between shadow-sm">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Active Cameras
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-mono font-extrabold text-white">6 / 6</span>
              <span className="text-[11px] font-medium text-emerald-400">100% Online</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
            <Camera className="w-5 h-5" />
          </div>
        </div>

        {/* KPI 2: People Detected */}
        <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A] flex items-center justify-between shadow-sm">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Workers Monitored
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-mono font-extrabold text-cyan-400">
                {peopleCount}
              </span>
              <span className="text-[11px] font-medium text-slate-400">In Active View</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <Users className="w-5 h-5" />
          </div>
        </div>

        {/* KPI 3: Active Safety Alerts */}
        <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A] flex items-center justify-between shadow-sm">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Active Safety Alerts
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-mono font-extrabold text-amber-400">
                {activeIncidents.length}
              </span>
              <span className="text-[11px] font-medium text-red-400">
                {stats?.by_severity.CRITICAL || 0} Critical
              </span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </div>

        {/* KPI 4: Processing FPS */}
        <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A] flex items-center justify-between shadow-sm">
          <div>
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Inference Speed
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-mono font-extrabold text-emerald-400">
                {fpsCount}
              </span>
              <span className="text-[11px] font-mono text-slate-400">FPS / Real-time</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Cpu className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* 2. MAIN WORKSPACE: LEFT LIVE VIDEO (DOMINANT) + RIGHT ALERT QUEUE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left: Dominant Live Video Feed (8 Cols) */}
        <div className="lg:col-span-8 flex flex-col space-y-2">
          {/* Stream Overlay Controls Header */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-200 tracking-wide uppercase font-mono">
                Primary Surveillance Channel: {selectedCameraId}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
                ByteTrack Active
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-900 border border-slate-700 text-slate-300">
                Site Threat:{" "}
                <strong
                  className={
                    sceneLevel === "CRITICAL"
                      ? "text-red-400"
                      : sceneLevel === "HIGH"
                      ? "text-orange-400"
                      : "text-emerald-400"
                  }
                >
                  {sceneRisk.toFixed(0)} [{sceneLevel}]
                </strong>
              </span>
            </div>

            <OverlayControls state={overlays} onChange={handleOverlayChange} />
          </div>

          {/* Large Video Canvas */}
          <VideoCanvas
            frame={frame}
            telemetry={telemetry}
            zones={zones}
            cameraId={selectedCameraId}
            cameraName={
              selectedCameraId === "CAM-01"
                ? "Tower Crane & Electrical Hub"
                : "Main Perimeter & Security Gate"
            }
            isLive={isConnected || isDemoMode}
            isStale={isStale}
            overlays={overlays}
          />
        </div>

        {/* Right Area: Priority Incident & Alert Queue (4 Cols) */}
        <div className="lg:col-span-4 flex flex-col space-y-3.5">
          {/* Highest Priority Alert Card */}
          {highestPriority && (
            <div className="p-4 rounded-xl bg-[#111C2E] border border-red-500/40 shadow-lg relative overflow-hidden">
              <div className="absolute top-0 right-0 w-28 h-28 bg-red-600/10 rounded-full blur-2xl pointer-events-none" />

              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-red-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                  HIGHEST PRIORITY INCIDENT
                </span>
                <SeverityBadge severity={highestPriority.risk_level} size="sm" />
              </div>

              <h4 className="text-sm font-bold text-white leading-snug">
                {formatViolationName(highestPriority.event_type)}
              </h4>
              <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                Worker #{highestPriority.track_id} triggered violation on{" "}
                {highestPriority.camera_name || "Sector 4 Elevated Grid"}.
              </p>

              {/* Risk Gauge Bar */}
              <div className="mt-3">
                <RiskGauge score={highestPriority.risk_score} label="Incident Risk Score" />
              </div>

              {/* Action Buttons */}
              <div className="mt-4 flex items-center gap-2 pt-3 border-t border-slate-800">
                <Link
                  to={`/events/${highestPriority.id}`}
                  className="flex-1 py-1.5 px-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow"
                >
                  <span>Review Evidence</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
                <button
                  onClick={async () => {
                    if (highestPriority.id) {
                      await apiService.resolveIncident(highestPriority.id);
                      setIncidents((prev) =>
                        prev.map((i) =>
                          i.id === highestPriority.id ? { ...i, resolved: true } : i
                        )
                      );
                    }
                  }}
                  className="py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1 transition-colors"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Resolve
                </button>
              </div>
            </div>
          )}

          {/* Active Alert Queue */}
          <div className="flex-1 p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A] flex flex-col justify-between">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800">
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-400" />
                Active Alert Queue ({activeIncidents.length})
              </span>
              <Link
                to="/events"
                className="text-[11px] text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1"
              >
                View All
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            <div className="space-y-2 overflow-y-auto max-h-[260px] pr-1">
              {activeIncidents.length === 0 ? (
                <div className="py-8 text-center text-slate-500 text-xs">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500/60 mx-auto mb-2" />
                  All clear. No active safety violations detected.
                </div>
              ) : (
                activeIncidents.map((incident) => {
                  const styles = formatSeverityColor(incident.risk_level);
                  return (
                    <Link
                      key={incident.id}
                      to={`/events/${incident.id}`}
                      className="p-2.5 rounded-lg bg-slate-900/70 border border-slate-800 hover:border-slate-700 transition flex items-center justify-between block group"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${styles.dot}`}
                          />
                          <p className="text-xs font-bold text-slate-200 group-hover:text-blue-300 transition">
                            {formatViolationName(incident.event_type)}
                          </p>
                        </div>
                        <p className="text-[10px] text-slate-400 font-mono">
                          Worker #{incident.track_id} • {incident.camera_id || "CAM-01"}
                        </p>
                      </div>

                      <div className="text-right">
                        <span className={`text-xs font-mono font-bold ${styles.text}`}>
                          {incident.risk_score.toFixed(0)} pts
                        </span>
                        <p className="text-[9px] text-slate-500 font-mono">
                          {new Date(incident.timestamp * 1000).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 3. LOWER AREA: RECENT TIMELINE + LATEST VLM EXPLANATION + SYSTEM HEALTH */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Recent Events Timeline (6 Cols) */}
        <div className="lg:col-span-6 p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-sm">
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-800">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
              <Clock className="w-4 h-4 text-cyan-400" />
              Recent Chronological Event Timeline
            </h3>
            <span className="text-[11px] text-slate-400 font-mono">Real-time Stream</span>
          </div>

          <div className="space-y-2.5">
            {incidents.slice(0, 4).map((inc) => (
              <div
                key={inc.id}
                className="flex items-start justify-between p-2 rounded-lg bg-slate-900/50 border border-slate-850"
              >
                <div className="flex items-start gap-2.5">
                  <div className="p-1.5 rounded bg-slate-800 text-slate-300 mt-0.5">
                    <HardHat className="w-3.5 h-3.5 text-blue-400" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-200">
                        {formatViolationName(inc.event_type)}
                      </span>
                      <SeverityBadge severity={inc.risk_level} size="sm" showDot={false} />
                    </div>
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                      Worker #{inc.track_id} | {inc.activity} | {formatDateTime(inc.timestamp)}
                    </p>
                  </div>
                </div>

                <Link
                  to={`/events/${inc.id}`}
                  className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center gap-1 self-center"
                >
                  Details
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            ))}
          </div>
        </div>

        {/* Latest VLM Decision-Support Explanation (6 Cols) */}
        <div className="lg:col-span-6 p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-800">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400" />
                Latest Gemini 1.5 Flash VLM Audit
              </h3>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950/70 border border-purple-700/50 text-purple-300">
                Multimodal Reasoning
              </span>
            </div>

            {highestPriority?.vlm_summary ? (
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-purple-950/20 border border-purple-500/20">
                  <p className="text-[10px] font-mono uppercase text-purple-400 font-bold mb-1">
                    Contextual Incident Assessment
                  </p>
                  <p className="text-xs text-slate-200 leading-relaxed font-sans">
                    "{highestPriority.vlm_summary}"
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/20">
                  <p className="text-[10px] font-mono uppercase text-emerald-400 font-bold mb-1">
                    Recommended Supervisor Procedure
                  </p>
                  <p className="text-xs text-emerald-300 font-medium">
                    {highestPriority.recommended_action ||
                      "Verify perimeter safety clearance and issue standard verbal guidance."}
                  </p>
                </div>
              </div>
            ) : (
              <div className="py-6 text-center text-slate-500 text-xs">
                No active VLM audit required. System running in nominal compliance.
              </div>
            )}
          </div>

          <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 font-mono">
            <span>Model: Gemini 1.5 Flash</span>
            <span>Latency: ~1.4s (Async)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

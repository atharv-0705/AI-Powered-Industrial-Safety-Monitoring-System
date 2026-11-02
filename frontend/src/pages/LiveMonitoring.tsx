import React, { useState, useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import {
  Play,
  Square,
  Upload,
  Camera,
  AlertTriangle,
  Users,
  RefreshCw,
} from "lucide-react";
import { VideoCanvas } from "@/components/video/VideoCanvas";
import { OverlayControls, OverlayVisibilityState } from "@/components/video/OverlayControls";
import { RiskGauge } from "@/components/common/RiskGauge";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { useSafetyWebSocket } from "@/hooks/useSafetyWebSocket";
import { apiService } from "@/services/api";
import { DEMO_CAMERAS } from "@/data/demoData";
import { CameraFeed, ZonePolygon } from "@/types/camera";
import { formatViolationName } from "@/lib/utils";

export const LiveMonitoring: React.FC = () => {
  const { selectedCameraId, cameras, isDemoMode: appDemoMode, setIsDemoMode: setAppDemoMode } = useOutletContext<{ selectedCameraId: string; cameras: CameraFeed[]; isDemoMode: boolean; setIsDemoMode: (value: boolean) => void }>();
  const { frame, telemetry, isConnected, isStale, isDemoMode, setIsDemoMode, reconnect } = useSafetyWebSocket();

  const [pipelineRunning, setPipelineRunning] = useState<boolean>(false);
  const [activeSource, setActiveSource] = useState<string>("0");
  const [zones, setZones] = useState<ZonePolygon[]>([]);
  const [customPath, setCustomPath] = useState<string>("");
  const [videoHistory, setVideoHistory] = useState<Array<{ name: string; source: string; url: string; size: number; modified: number }>>([]);
  const [uploadError, setUploadError] = useState<string>("");
  const [isStarting, setIsStarting] = useState<boolean>(false);

  useEffect(() => setIsDemoMode(appDemoMode), [appDemoMode, setIsDemoMode]);

  const [overlays, setOverlays] = useState<OverlayVisibilityState>({
    showBoundingBoxes: true,
    showLabels: true,
    showPPE: true,
    showZones: true,
    showRiskBadge: true,
  });

  // Check initial pipeline status & load zones
  useEffect(() => {
    const checkStatus = async () => {
      const [pipeRes, zonesRes] = await Promise.all([
        apiService.getPipelineStatus(),
        apiService.getZones(),
      ]);
      setPipelineRunning(pipeRes.data.running);
      setZones(zonesRes);
    };
    checkStatus();
    const interval = setInterval(checkStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    apiService.getVideoHistory().then(setVideoHistory).catch(() => setVideoHistory([]));
  }, []);

  const handleVideoUpload = async (file?: File) => {
    if (!file) return;
    setUploadError("");
    setAppDemoMode(false);
    setIsDemoMode(false);
    try {
      const uploaded = await apiService.uploadVideo(file);
      setVideoHistory(await apiService.getVideoHistory());
      setCustomPath(uploaded.source);
      setActiveSource(uploaded.source);
      await handleStartPipeline(uploaded.source);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Video upload failed");
    }
  };

  const handleStartPipeline = async (sourceToUse?: string) => {
    setIsStarting(true);
    const src = sourceToUse || activeSource;
    const res = await apiService.startPipeline(src);
    if (res.success) {
      setPipelineRunning(true);
    }
    setIsStarting(false);
  };

  const handleStopPipeline = async () => {
    const res = await apiService.stopPipeline();
    if (res.success) {
      setPipelineRunning(false);
    }
  };

  const currentCamera = cameras.find((c) => c.id === selectedCameraId) || DEMO_CAMERAS[0];

  const sceneScore = telemetry?.scene_risk?.overall_score ?? 15.0;
  const sceneLevel = telemetry?.scene_risk?.overall_level ?? "LOW";
  const workersCount = telemetry?.workers_count ?? 2;
  const activeViolations = telemetry?.violations || [];

  return (
    <div className="space-y-4">
      {/* 1. TOP MONITORING CONTROL BAR */}
      <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] flex flex-wrap items-center justify-between gap-3 shadow-md">
        {/* Source Selector & Pipeline Start/Stop */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 font-mono">
              <Camera className="w-4 h-4 text-cyan-400" />
              Source:
            </span>
            <select
              value={activeSource}
              onChange={(e) => setActiveSource(e.target.value)}
              disabled={pipelineRunning}
              className="px-3 py-1.5 text-xs font-mono bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            >
              {activeSource && !["0", "source/Alone-man-climbing-SnapYT.App.mp4", "source/cctv_27c12fe4.mp4"].includes(activeSource) && (
                <option value={activeSource}>Uploaded: {activeSource.split(/[\\/]/).pop()}</option>
              )}
              <option value="0">Default Webcam 0 (Live Device)</option>
              <option value="source/Alone-man-climbing-SnapYT.App.mp4">
                Test Clip: Pylon Climbing (MP4)
              </option>
              <option value="source/cctv_27c12fe4.mp4">
                Test Clip: Perimeter CCTV (MP4)
              </option>
            </select>
          </div>

          {/* Start / Stop Toggle Buttons */}
          {!pipelineRunning ? (
            <button
              onClick={() => handleStartPipeline()}
              disabled={isStarting}
              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold font-mono flex items-center gap-1.5 transition-colors shadow shadow-emerald-600/30 disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              {isStarting ? "Initializing..." : "Start Processing"}
            </button>
          ) : (
            <button
              onClick={handleStopPipeline}
              className="px-4 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold font-mono flex items-center gap-1.5 transition-colors shadow shadow-red-600/30"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              Stop Processing
            </button>
          )}

          <button
            onClick={reconnect}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono flex items-center gap-1 transition"
            title="Reconnect WebSocket Stream"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Live FPS & Telemetry Pill */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs font-mono">
            <span className="text-slate-400">FPS:</span>
            <span className="text-emerald-400 font-bold">
              {telemetry?.fps ? telemetry.fps.toFixed(1) : "14.8"}
            </span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs font-mono">
            <span className="text-slate-400">Stream:</span>
            <span
              className={`font-bold ${
                isConnected ? "text-emerald-400" : "text-amber-400"
              }`}
            >
              {isConnected ? "WS Active" : isDemoMode ? "Demo Mode" : "Idle"}
            </span>
          </div>

          <OverlayControls
            state={overlays}
            onChange={(key, val) => setOverlays((prev) => ({ ...prev, [key]: val }))}
          />
        </div>
      </div>

      {/* 2. DEDICATED FULL-SCALE MONITORING CANVAS WORKSPACE */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Large Viewport (9 Cols) */}
        <div className="lg:col-span-9 space-y-3">
          <VideoCanvas
            frame={frame}
            telemetry={telemetry}
            zones={zones}
            cameraId={selectedCameraId}
            cameraName={currentCamera.name}
            isLive={isConnected || isDemoMode}
            isStale={isStale}
            overlays={overlays}
          />

          {/* Quick Source Path Input for Custom Recorded MP4s */}
          <div className="p-3 rounded-xl bg-[#111C2E] border border-[#25334A] flex flex-wrap items-center gap-2 text-xs">
            <Upload className="w-4 h-4 text-cyan-400 flex-shrink-0" />
            <label className="text-slate-400 font-medium flex-shrink-0">Custom Video Source:</label>
            <input type="file" accept="video/*,.mkv" disabled={pipelineRunning}
              onChange={(e) => handleVideoUpload(e.target.files?.[0])}
              className="flex-1 min-w-[200px] px-2 py-1 bg-slate-900 border border-slate-700 rounded text-slate-300 text-xs file:mr-2 file:rounded file:border-0 file:bg-slate-700 file:px-2 file:py-1 file:text-slate-100" />
            <select value={customPath} onChange={(e) => { setCustomPath(e.target.value); setActiveSource(e.target.value); }} disabled={pipelineRunning}
              className="max-w-[240px] px-2 py-1 bg-slate-900 border border-slate-700 rounded text-slate-200 text-xs">
              <option value="">Video history</option>
              {videoHistory.map((video) => <option key={video.source} value={video.source}>{video.name}</option>)}
            </select>
            <button
              onClick={() => handleStartPipeline(activeSource)}
              disabled={!activeSource.trim() || pipelineRunning}
              className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-semibold text-xs"
            >
              Apply Source
            </button>
            {uploadError && <span className="w-full text-red-400">{uploadError}</span>}
            {videoHistory.length > 0 && <span className="w-full text-slate-500">{videoHistory.length} uploaded video(s) saved in history.</span>}
          </div>
        </div>

        {/* Live Channel Telemetry & Risk Sidebar (3 Cols) */}
        <div className="lg:col-span-3 space-y-3.5">
          {/* Scene Threat Gauge Card */}
          <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] flex flex-col items-center text-center shadow-sm">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              Aggregate Scene Threat
            </p>
            <RiskGauge score={sceneScore} level={sceneLevel} type="circular" size="lg" />
            <div className="mt-3">
              <SeverityBadge severity={sceneLevel} />
            </div>
            <p className="text-xs text-slate-300 mt-2 font-mono">
              {telemetry?.scene_risk?.summary || "Nominal compliance across perimeter."}
            </p>
          </div>

          {/* Tracked Workers in View */}
          <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A] space-y-2">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                <Users className="w-4 h-4 text-cyan-400" />
                Tracked Personnel ({workersCount})
              </span>
              <span className="text-[10px] text-slate-400 font-mono">ByteTrack</span>
            </div>

            <div className="space-y-2 max-h-[220px] overflow-y-auto">
              {telemetry?.tracks && telemetry.tracks.length > 0 ? (
                telemetry.tracks.map((t) => (
                  <div
                    key={t.track_id}
                    className="p-2 rounded-lg bg-slate-900/70 border border-slate-800 text-xs flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-slate-200">
                          Worker #{t.track_id}
                        </span>
                        <span className="text-[10px] px-1 rounded bg-slate-800 text-slate-300 font-mono">
                          {t.activity}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                        Helmet:{" "}
                        <span
                          className={
                            t.ppe?.has_helmet ? "text-emerald-400" : "text-red-400"
                          }
                        >
                          {t.ppe?.has_helmet ? "YES" : "MISSING"}
                        </span>{" "}
                        | Vest:{" "}
                        <span
                          className={
                            t.ppe?.has_vest ? "text-emerald-400" : "text-amber-400"
                          }
                        >
                          {t.ppe?.has_vest ? "YES" : "MISSING"}
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="font-mono font-bold text-slate-200">
                        {t.risk?.score.toFixed(0) || 0} pts
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-4 text-center text-slate-500 text-xs">
                  No personnel detected in active frame.
                </div>
              )}
            </div>
          </div>

          {/* Active Violations Instant Box */}
          <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A] space-y-2">
            <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 pb-2 border-b border-slate-800">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              Active Violations ({activeViolations.length})
            </span>

            {activeViolations.length === 0 ? (
              <p className="text-xs text-slate-500 py-3 text-center">
                All personnel compliant.
              </p>
            ) : (
              activeViolations.map((v, i) => (
                <div
                  key={i}
                  className="p-2 rounded bg-red-950/30 border border-red-500/30 text-xs"
                >
                  <p className="font-bold text-red-300">
                    {formatViolationName(v.event_type)}
                  </p>
                  <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                    Worker #{v.track_id} • Conf: {(v.confidence * 100).toFixed(0)}%
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

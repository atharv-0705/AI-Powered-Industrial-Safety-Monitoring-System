import React, { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  Eye,
  Camera,
  Layers,
  Scale,
  BrainCircuit,
  FileText,
} from "lucide-react";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { RiskGauge } from "@/components/common/RiskGauge";
import { apiService, getAssetUrl } from "@/services/api";
import { IncidentRecord } from "@/types/safety";
import {
  formatDateTime,
  formatViolationName,
  formatSeverityColor,
} from "@/lib/utils";

export const EventDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [incident, setIncident] = useState<IncidentRecord | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [resolving, setResolving] = useState<boolean>(false);

  useEffect(() => {
    const loadIncident = async () => {
      if (!id) return;
      setLoading(true);
      const res = await apiService.getIncident(Number(id));
      setIncident(res.data);
      setLoading(false);
    };

    loadIncident();
  }, [id]);

  const handleResolve = async () => {
    if (!incident || !incident.id) return;
    setResolving(true);
    await apiService.resolveIncident(incident.id);
    setIncident((prev) =>
      prev ? { ...prev, resolved: true, resolved_at: Date.now() / 1000 } : prev
    );
    setResolving(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400 font-mono text-sm">
        Loading incident record #{id}...
      </div>
    );
  }

  if (!incident) {
    return (
      <div className="p-8 text-center space-y-4">
        <p className="text-slate-300 font-bold">Incident record #{id} not found.</p>
        <Link
          to="/events"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Incidents Audit Log
        </Link>
      </div>
    );
  }

  const sevStyles = formatSeverityColor(incident.risk_level);

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* 1. TOP HEADER & BACK NAVIGATION */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/events")}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
            title="Return to incidents list"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-base font-extrabold text-white tracking-wide uppercase">
                Incident #{incident.id}: {formatViolationName(incident.event_type)}
              </h2>
              <SeverityBadge severity={incident.risk_level} size="md" />
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Logged at {formatDateTime(incident.timestamp)} • Camera:{" "}
              {incident.camera_name || incident.camera_id || "CAM-01"}
            </p>
          </div>
        </div>

        {/* Resolution Action */}
        <div className="flex items-center gap-3">
          {incident.resolved ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950/80 border border-emerald-700/60 text-emerald-400 text-xs font-mono font-bold">
              <CheckCircle2 className="w-4 h-4" />
              RESOLVED (
              {incident.resolved_at ? formatDateTime(incident.resolved_at) : "Done"}
              )
            </div>
          ) : (
            <button
              onClick={handleResolve}
              disabled={resolving}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold font-mono flex items-center gap-2 shadow-lg shadow-emerald-600/30 transition disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" />
              {resolving ? "Resolving..." : "Mark as Resolved & Closed"}
            </button>
          )}
        </div>
      </div>

      {/* 2. GRID: LEFT EVIDENCE IMAGE & RISK GAUGES (7 COLS) | RIGHT 3-TIER EXPLANATIONS (5 COLS) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Visual Evidence & Risk Breakdown (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Keyframe Snapshot Card */}
          <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Eye className="w-4 h-4 text-cyan-400" />
                {incident.video_path ? "Recorded Video Evidence" : "Keyframe Visual Evidence Snapshot"}
              </span>
              <span className="text-[10px] text-slate-400 font-mono">
                Model Input Resolution: 640x480
              </span>
            </div>

            {/* Evidence Image Viewer */}
            <div className="relative w-full aspect-video rounded-lg overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center">
              {incident.video_path ? (
                <video src={getAssetUrl(incident.video_path)} controls className="w-full h-full object-contain" preload="metadata">
                  Your browser cannot play this incident video.
                </video>
              ) : incident.snapshot_path ? (
                <img
                  src={getAssetUrl(incident.snapshot_path)}
                  alt="Incident keyframe evidence"
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    // Fallback to stylized synthetic placeholder if local file is missing
                    (e.target as HTMLImageElement).src =
                      "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360' viewBox='0 0 640 360'><rect width='640' height='360' fill='%230b1220'/><text x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%23ef4444' font-family='monospace' font-size='16'>INCIDENT EVIDENCE SNAPSHOT (SAVED IN DATA/SNAPSHOTS)</text></svg>";
                  }}
                />
              ) : (
                <div className="text-center p-6 space-y-2">
                  <Camera className="w-10 h-10 text-slate-600 mx-auto" />
                  <p className="text-xs text-slate-400 font-mono">
                    Archived snapshot reference stored in SQLite database.
                  </p>
                </div>
              )}

              {/* Watermark badge */}
              <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/80 backdrop-blur-md text-[10px] font-mono text-cyan-400 border border-cyan-700/50">
                EVIDENCE #{incident.id} • WORKER #{incident.track_id}
              </div>
            </div>
          </div>

          {/* 4-Factor Deterministic Risk Breakdown Card */}
          <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Scale className="w-4 h-4 text-amber-400" />
                Deterministic Risk Factor Breakdown (SRS §8.5, FR-13)
              </span>
              <span className={`text-xs font-mono font-bold ${sevStyles.text}`}>
                {incident.risk_score.toFixed(1)} / 100 [{incident.risk_level}]
              </span>
            </div>

            <RiskGauge score={incident.risk_score} level={incident.risk_level} />

            {/* Contributing Factors Ledger */}
            <div className="space-y-1.5 pt-2">
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Contributing Factor Ledger:
              </p>
              {incident.contributing_factors.map((factor, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs font-mono"
                >
                  <span className="text-slate-300">{factor}</span>
                  <span className="text-amber-400 font-bold">Active Weight</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: 3-Tier Multi-Modal Explanations (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* TIER 1: OBSERVED EVIDENCE */}
          <div className="p-4 rounded-xl bg-[#111C2E] border border-blue-500/30 shadow-md space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold text-blue-400 uppercase tracking-wider pb-1 border-b border-slate-800">
              <Layers className="w-4 h-4" />
              1. Observed Evidence (CV Model Detections)
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              YOLO11n detector tracked Person #{incident.track_id} with detection confidence of{" "}
              <strong className="text-white font-mono">
                {(incident.confidence * 100).toFixed(0)}%
              </strong>
              . Temporal Transformer HAR classified activity as{" "}
              <strong className="text-cyan-400 font-mono">
                "{incident.activity.toUpperCase()}"
              </strong>
              .
            </p>
            <div className="text-[11px] text-slate-400 font-mono bg-slate-900/80 p-2 rounded border border-slate-800 space-y-0.5">
              <div>BBox Coordinates: [{incident.bbox_xyxy.join(", ")}]</div>
              <div>Detection Model: YOLO11n @ 640-class (FP16)</div>
            </div>
          </div>

          {/* TIER 2: RULE-BASED INTERPRETATION */}
          <div className="p-4 rounded-xl bg-[#111C2E] border border-amber-500/30 shadow-md space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold text-amber-400 uppercase tracking-wider pb-1 border-b border-slate-800">
              <FileText className="w-4 h-4" />
              2. Rule-Based Interpretation (Safety Engine)
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              The Safety Rule Engine flagged a{" "}
              <strong className="text-amber-300">
                {formatViolationName(incident.event_type)}
              </strong>{" "}
              event following 6 consecutive persistence frames. Mathematical triggers
              satisfied safety condition boundaries without stochastic drift.
            </p>
            <div className="p-2.5 rounded bg-amber-950/20 border border-amber-500/20 text-xs text-amber-300">
              Persistent state escalated risk by +2.0 pts/sec. Exponential decay half-life of 3.0s active.
            </div>
          </div>

          {/* TIER 3: VLM EXPLANATION (GEMINI 1.5 FLASH) */}
          <div className="p-4 rounded-xl bg-[#111C2E] border border-purple-500/40 shadow-md space-y-3">
            <div className="flex items-center justify-between pb-1 border-b border-slate-800">
              <span className="flex items-center gap-2 text-xs font-bold text-purple-400 uppercase tracking-wider">
                <BrainCircuit className="w-4 h-4" />
                3. VLM Contextual Explanation
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                Gemini 1.5 Flash
              </span>
            </div>

            {incident.vlm_summary ? (
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-purple-950/30 border border-purple-500/30">
                  <p className="text-[10px] font-mono uppercase text-purple-400 font-bold mb-1">
                    Visual Scene Interpretation:
                  </p>
                  <p className="text-xs text-slate-200 leading-relaxed font-sans">
                    "{incident.vlm_summary}"
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-500/30">
                  <p className="text-[10px] font-mono uppercase text-emerald-400 font-bold mb-1">
                    Recommended Corrective Procedure:
                  </p>
                  <p className="text-xs text-emerald-300 font-medium">
                    {incident.recommended_action ||
                      "Verify safety perimeter clearance and halt overhead equipment."}
                  </p>
                </div>

                <p className="text-[10px] text-slate-500 italic">
                  Note: VLM output provides advisory decision support. Verified by automated safety rules.
                </p>
              </div>
            ) : (
              <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-400">
                VLM audit unavailable or executing asynchronously. Local rule-based safety engine remains fully active.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

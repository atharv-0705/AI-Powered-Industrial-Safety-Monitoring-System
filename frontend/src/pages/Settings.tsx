import React, { useState, useEffect } from "react";
import {
  Settings as SettingsIcon,
  Save,
  CheckCircle2,
  Cpu,
  Layers,
  Shield,
  Sliders,
  BrainCircuit,
  RotateCcw,
} from "lucide-react";
import { ZoneCanvasEditor } from "@/components/zones/ZoneCanvasEditor";
import { apiService } from "@/services/api";
import { SafetySettings } from "@/types/settings";
import { ZonePolygon } from "@/types/camera";
import { DEMO_MODEL_STATUS, DEMO_SETTINGS } from "@/data/demoData";

export const Settings: React.FC = () => {
  const [settings, setSettings] = useState<SafetySettings>(DEMO_SETTINGS);
  const [zones, setZones] = useState<ZonePolygon[]>([]);
  const models = DEMO_MODEL_STATUS;
  const [isSaved, setIsSaved] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"SAFETY" | "ZONES" | "MODELS" | "CAMERAS">("SAFETY");

  useEffect(() => {
    const load = async () => {
      const [savedSettings, savedZones] = await Promise.all([
        apiService.getSettings(),
        apiService.getZones(),
      ]);
      setSettings(savedSettings);
      setZones(savedZones);
    };
    load();
  }, []);

  const handleSaveSettings = async () => {
    await apiService.updateSettings(settings);
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
  };

  const handleSaveZone = async (newZone: ZonePolygon) => {
    const updated = [...zones, newZone];
    setZones(updated);
    await apiService.saveZones(updated);
  };

  const handleDeleteZone = async (id: string) => {
    const updated = zones.filter((z) => z.id !== id);
    setZones(updated);
    await apiService.saveZones(updated);
  };

  const handleResetDefaults = () => {
    setSettings(DEMO_SETTINGS);
  };

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* 1. TOP HEADER & TABS BAR */}
      <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] flex flex-wrap items-center justify-between gap-3 shadow-md">
        <div>
          <h2 className="text-base font-extrabold text-white tracking-wide uppercase flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-cyan-400" />
            System & Safety Configuration Center
          </h2>
          <p className="text-xs text-slate-400 font-medium">
            Fine-tune mathematical safety rule thresholds, polygon hazard zones, and model hardware bindings.
          </p>
        </div>

        {/* Tab Switchers */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
          <button
            onClick={() => setActiveTab("SAFETY")}
            className={`px-3 py-1.5 rounded-md transition font-semibold ${
              activeTab === "SAFETY"
                ? "bg-blue-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Safety Rules
          </button>
          <button
            onClick={() => setActiveTab("ZONES")}
            className={`px-3 py-1.5 rounded-md transition font-semibold ${
              activeTab === "ZONES"
                ? "bg-blue-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Polygon Zones
          </button>
          <button
            onClick={() => setActiveTab("MODELS")}
            className={`px-3 py-1.5 rounded-md transition font-semibold ${
              activeTab === "MODELS"
                ? "bg-blue-600 text-white shadow"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Model Status
          </button>
        </div>
      </div>

      {/* 2. TAB 1: SAFETY RULES & RISK ENGINE THRESHOLDS */}
      {activeTab === "SAFETY" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Fall Detection & Pose Parameters */}
            <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] space-y-4">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2 pb-2 border-b border-slate-800">
                <Shield className="w-4 h-4 text-cyan-400" />
                Fall Detection Parameters (SRS §8.4, FR-09)
              </h3>

              <div className="space-y-3 text-xs">
                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Aspect Ratio Collapse Threshold:</span>
                    <span className="font-bold text-cyan-400">
                      {settings.fallAspectRatioThreshold.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.5"
                    max="1.2"
                    step="0.05"
                    value={settings.fallAspectRatioThreshold}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        fallAspectRatioThreshold: parseFloat(e.target.value),
                      })
                    }
                    className="w-full accent-blue-500 cursor-pointer"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Triggered when bounding box width/height ratio collapses below threshold.
                  </p>
                </div>

                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Fall Confirmation Window (Frames):</span>
                    <span className="font-bold text-cyan-400">
                      {settings.fallConfirmationFrames} frames
                    </span>
                  </div>
                  <input
                    type="range"
                    min="3"
                    max="12"
                    step="1"
                    value={settings.fallConfirmationFrames}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        fallConfirmationFrames: parseInt(e.target.value),
                      })
                    }
                    className="w-full accent-blue-500 cursor-pointer"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Consecutive collapsed frames required to confirm fall event (suppresses bending/shoe-tying).
                  </p>
                </div>
              </div>
            </div>

            {/* Risk Engine Escalation & Decay */}
            <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] space-y-4">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2 pb-2 border-b border-slate-800">
                <Sliders className="w-4 h-4 text-amber-400" />
                Deterministic Risk Engine (SRS §8.5, FR-14)
              </h3>

              <div className="space-y-3 text-xs">
                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Persistence Escalation Rate:</span>
                    <span className="font-bold text-amber-400">
                      +{settings.persistenceEscalationRate.toFixed(1)} pts / sec
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1.0"
                    max="5.0"
                    step="0.5"
                    value={settings.persistenceEscalationRate}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        persistenceEscalationRate: parseFloat(e.target.value),
                      })
                    }
                    className="w-full accent-amber-500 cursor-pointer"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Escalates unresolved violations dynamically up to +20 points max bonus.
                  </p>
                </div>

                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Resolution Decay Half-Life:</span>
                    <span className="font-bold text-emerald-400">
                      {settings.riskDecayHalfLifeSeconds.toFixed(1)}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1.0"
                    max="8.0"
                    step="0.5"
                    value={settings.riskDecayHalfLifeSeconds}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        riskDecayHalfLifeSeconds: parseFloat(e.target.value),
                      })
                    }
                    className="w-full accent-emerald-500 cursor-pointer"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Smooth exponential decay duration upon violation clearing to eliminate UI flicker.
                  </p>
                </div>
              </div>
            </div>

            {/* PPE & Zone Persistence */}
            <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] space-y-4">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2 pb-2 border-b border-slate-800">
                <Layers className="w-4 h-4 text-purple-400" />
                PPE & Zone Persistence Filters (FR-10, FR-11)
              </h3>

              <div className="space-y-3 text-xs">
                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Missing Helmet Persistence:</span>
                    <span className="font-bold text-purple-400">
                      {settings.helmetPersistenceFrames} frames
                    </span>
                  </div>
                  <input
                    type="range"
                    min="2"
                    max="10"
                    step="1"
                    value={settings.helmetPersistenceFrames}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        helmetPersistenceFrames: parseInt(e.target.value),
                      })
                    }
                    className="w-full accent-purple-500 cursor-pointer"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Consecutive frames without helmet required before raising safety alarm.
                  </p>
                </div>

                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>Restricted Zone Persistence:</span>
                    <span className="font-bold text-purple-400">
                      {settings.zonePersistenceFrames} frames
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="8"
                    step="1"
                    value={settings.zonePersistenceFrames}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        zonePersistenceFrames: parseInt(e.target.value),
                      })
                    }
                    className="w-full accent-purple-500 cursor-pointer"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Point-in-polygon verification frames on ankle keypoints to prevent boundary jitter.
                  </p>
                </div>
              </div>
            </div>

            {/* VLM Gemini 1.5 Flash Configuration */}
            <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] space-y-4">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2 pb-2 border-b border-slate-800">
                <BrainCircuit className="w-4 h-4 text-emerald-400" />
                VLM Decision-Support API (SRS §8.5, FR-16..FR-20)
              </h3>

              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                  <div>
                    <p className="font-bold text-slate-200">Enable Gemini 1.5 Flash VLM</p>
                    <p className="text-[10px] text-slate-400">
                      Asynchronous keyframe snapshot and telemetry audit
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={settings.vlmEnabled}
                    onChange={(e) =>
                      setSettings({ ...settings, vlmEnabled: e.target.checked })
                    }
                    className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-slate-300 font-mono mb-1">
                    <span>VLM Request Rate Limit (Cooldown):</span>
                    <span className="font-bold text-cyan-400">
                      {settings.vlmRateLimitSeconds}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="30"
                    step="1"
                    value={settings.vlmRateLimitSeconds}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        vlmRateLimitSeconds: parseInt(e.target.value),
                      })
                    }
                    className="w-full accent-blue-500 cursor-pointer"
                  />
                  <p className="text-[10px] text-slate-500 mt-0.5">
                    Minimum interval between automated multimodal API queries to protect quota.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Action Bar */}
          <div className="flex items-center justify-between p-4 rounded-xl bg-[#111C2E] border border-[#25334A]">
            <button
              onClick={handleResetDefaults}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Factory Defaults
            </button>

            <button
              onClick={handleSaveSettings}
              className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold font-mono flex items-center gap-2 shadow-lg shadow-blue-600/30 transition"
            >
              {isSaved ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-emerald-300" />
                  <span>Configuration Applied</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Save Configuration</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* 3. TAB 2: RESTRICTED POLYGON ZONES CANVAS EDITOR */}
      {activeTab === "ZONES" && (
        <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md space-y-4">
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Interactive Restricted Zone Canvas Editor
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Click on the canvas below to place polygon boundary vertices. Ankle keypoint detection will check intrusion.
            </p>
          </div>

          <ZoneCanvasEditor
            zones={zones}
            onSaveZone={handleSaveZone}
            onDeleteZone={handleDeleteZone}
          />
        </div>
      )}

      {/* 4. TAB 3: MODEL HEALTH & COMPONENT STATUS */}
      {activeTab === "MODELS" && (
        <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Cpu className="w-4 h-4 text-emerald-400" />
                Pipeline Subsystem & Model Health Monitor
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time operational status, device allocations, and inference latencies.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {models.map((mod, i) => (
              <div
                key={i}
                className="p-3.5 rounded-lg bg-slate-900/70 border border-slate-800 space-y-2 hover:border-slate-700 transition"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-200">
                    {mod.name}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">
                    {mod.status}
                  </span>
                </div>

                <p className="text-[11px] text-slate-400 font-sans">
                  {mod.details}
                </p>

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-[10px] text-slate-500 font-mono">
                  <span>Device: {mod.device}</span>
                  <span className="text-cyan-400 font-bold">
                    Latency: ~{mod.latencyMs} ms
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

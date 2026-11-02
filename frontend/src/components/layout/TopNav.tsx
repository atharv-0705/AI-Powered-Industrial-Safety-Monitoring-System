import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Bell,
  Camera,
  Activity,
  SlidersHorizontal,
  Wifi,
  WifiOff,
} from "lucide-react";
import { CameraFeed } from "@/types/camera";

interface TopNavProps {
  isDemoMode: boolean;
  onToggleDemoMode: () => void;
  isConnected: boolean;
  selectedCameraId: string;
  onSelectCamera: (cameraId: string) => void;
  unresolvedCount?: number;
  cameras: CameraFeed[];
}

export const TopNav: React.FC<TopNavProps> = ({
  isDemoMode,
  onToggleDemoMode,
  isConnected,
  selectedCameraId,
  onSelectCamera,
  unresolvedCount = 0,
  cameras,
}) => {
  const location = useLocation();
  const [timeStr, setTimeStr] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const getPageTitle = (path: string) => {
    switch (path) {
      case "/":
        return "Dashboard Overview";
      case "/live":
        return "Live Video Monitoring Station";
      case "/events":
        return "Incident & Violation Audit Log";
      case "/analytics":
        return "Safety Analytics & Trends";
      case "/settings":
        return "System & Safety Rules Configuration";
      default:
        if (path.startsWith("/events/")) return "Incident Evidence Investigation";
        return "Safety AI Monitor";
    }
  };

  return (
    <header className="h-14 border-b border-[#25334A] bg-[#0F172A]/90 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30 select-none">
      {/* Left: Page Title & Breadcrumbs */}
      <div className="flex items-center gap-4">
        <div>
          <h2 className="text-sm font-bold text-white tracking-wide flex items-center gap-2">
            <span className="text-cyan-400 font-extrabold uppercase">
              AI Powered
            </span>
            <span>INDUSTRIAL SAFETY MONITOR</span>
          </h2>
          <p className="text-[11px] text-slate-400 font-medium">
            {getPageTitle(location.pathname)}
          </p>
        </div>
      </div>

      {/* Right Controls: Mode Toggle, Camera Selector, Connection, Clock */}
      <div className="flex items-center gap-3">
        {/* Mode Switcher Pill */}
        <button
          onClick={onToggleDemoMode}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold font-mono border transition-all ${
            isDemoMode
              ? "bg-amber-500/15 border-amber-500/50 text-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.2)]"
              : "bg-blue-600/20 border-blue-500/50 text-blue-300"
          }`}
          title="Toggle between Live FastAPI stream and realistic Demo simulation"
        >
          <Activity className="w-3.5 h-3.5" />
          <span>{isDemoMode ? "DEMO MODE (Simulated)" : "LIVE MODE (FastAPI)"}</span>
        </button>

        {/* Camera Selector Dropdown */}
        <div className="relative flex items-center">
          <Camera className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
          <select
            value={selectedCameraId}
            onChange={(e) => onSelectCamera(e.target.value)}
            className="pl-8 pr-7 py-1 text-xs font-mono font-medium bg-[#111C2E] border border-[#25334A] rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 cursor-pointer appearance-none"
          >
            {cameras.map((cam) => (
              <option key={cam.id} value={cam.id}>
                {cam.id}: {cam.name}
              </option>
            ))}
            {cameras.length === 0 && <option value="">No cameras available</option>}
          </select>
        </div>

        {/* Backend Connection Indicator */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono border ${
            isConnected
              ? "bg-emerald-950/60 border-emerald-700/60 text-emerald-400"
              : "bg-red-950/60 border-red-700/60 text-red-400"
          }`}
          title={isConnected ? "WebSocket stream connected to FastAPI :8010" : "WebSocket disconnected"}
        >
          {isConnected ? (
            <>
              <Wifi className="w-3.5 h-3.5 text-emerald-400" />
              <span>ONLINE</span>
            </>
          ) : (
            <>
              <WifiOff className="w-3.5 h-3.5 text-red-400" />
              <span>OFFLINE</span>
            </>
          )}
        </div>

        {/* Notification Bell Badge */}
        <Link
          to="/events"
          className="relative p-2 rounded-lg bg-[#111C2E] border border-[#25334A] text-slate-300 hover:text-white hover:bg-slate-800 transition"
          title="View Active Incidents"
        >
          <Bell className="w-4 h-4" />
          {unresolvedCount > 0 && (
            <span className="absolute -top-1 -right-1 px-1.5 py-0.2 bg-red-600 text-white font-mono font-bold text-[9px] rounded-full border border-slate-900 animate-pulse">
              {unresolvedCount}
            </span>
          )}
        </Link>

        {/* Settings Shortcut */}
        <Link
          to="/settings"
          className="p-2 rounded-lg bg-[#111C2E] border border-[#25334A] text-slate-300 hover:text-white hover:bg-slate-800 transition"
          title="Open Settings"
        >
          <SlidersHorizontal className="w-4 h-4" />
        </Link>

        {/* Live Clock */}
        <div className="font-mono text-xs font-bold text-slate-300 bg-[#111C2E] px-2.5 py-1 rounded-lg border border-[#25334A]">
          {timeStr}
        </div>
      </div>
    </header>
  );
};


import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Video,
  ShieldAlert,
  BarChart3,
  Settings,
  ShieldCheck,
  User,
  Radio,
} from "lucide-react";

export const Sidebar: React.FC = () => {
  const navItems = [
    { name: "Dashboard", path: "/", icon: LayoutDashboard },
    { name: "Live Monitoring", path: "/live", icon: Video },
    { name: "Events & Incidents", path: "/events", icon: ShieldAlert },
    { name: "Analytics", path: "/analytics", icon: BarChart3 },
    { name: "Settings", path: "/settings", icon: Settings },
  ];

  return (
    <aside className="w-64 flex-shrink-0 bg-[#0F172A] border-r border-[#25334A] flex flex-col justify-between h-screen sticky top-0 overflow-y-auto select-none">
      {/* Top Header & Brand */}
      <div>
        <div className="p-4 border-b border-[#25334A] flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-extrabold tracking-tight text-white leading-tight">
              SAFETY MONITOR
            </h1>
            <p className="text-[10px] text-cyan-400 font-mono font-medium tracking-wider uppercase">
              AI Decision Support
            </p>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                    isActive
                      ? "bg-blue-600 text-white shadow-md shadow-blue-600/30 border border-blue-400/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Middle/Lower: System Overview Gauge Widget (Inspired by Reference Design) */}
      <div className="p-3 mx-3 rounded-xl bg-[#111C2E] border border-[#25334A] my-2 shadow-inner">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
            System Overview
          </span>
          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-mono">
            <Radio className="w-2.5 h-2.5 animate-pulse" />
            Active
          </span>
        </div>

        {/* Circular Progress Gauge */}
        <div className="flex items-center gap-3 my-2">
          <div className="relative w-14 h-14 flex items-center justify-center">
            <svg className="w-14 h-14 -rotate-90 transform" viewBox="0 0 36 36">
              <path
                className="text-slate-800"
                strokeWidth="3.5"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className="text-cyan-400"
                strokeDasharray="94, 100"
                strokeWidth="3.5"
                strokeLinecap="round"
                stroke="currentColor"
                fill="none"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-xs font-bold text-white leading-none">94%</span>
              <span className="text-[7px] text-slate-400 uppercase tracking-tighter">Health</span>
            </div>
          </div>

          <div className="space-y-1 text-[10px] flex-1">
            <div className="flex justify-between text-slate-400">
              <span>Cameras:</span>
              <span className="text-emerald-400 font-mono font-bold">6 / 6 Online</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Pipeline:</span>
              <span className="text-cyan-400 font-mono font-bold">14.8 FPS</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>AI Models:</span>
              <span className="text-emerald-400 font-mono font-bold">Loaded</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom User Profile Section */}
      <div className="p-3 border-t border-[#25334A] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
            <User className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="leading-tight">
            <p className="text-xs font-bold text-slate-200">Atharv Gupta</p>
            <p className="text-[10px] text-slate-400 font-mono">Safety Supervisor</p>
          </div>
        </div>
        <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono border border-slate-700">
          v1.0
        </span>
      </div>
    </aside>
  );
};


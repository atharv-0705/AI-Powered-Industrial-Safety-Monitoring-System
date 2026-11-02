import React, { useState } from "react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  BarChart3,
  Calendar,
  Camera,
  TrendingUp,
} from "lucide-react";
import {
  DEMO_ACTIVITY_DISTRIBUTION,
  DEMO_ANALYTICS_TIMELINE,
  DEMO_CAMERAS,
  DEMO_SEVERITY_DISTRIBUTION,
  DEMO_STATS,
} from "@/data/demoData";

export const Analytics: React.FC = () => {
  const [selectedRange, setSelectedRange] = useState<string>("24h");
  const [selectedCamera, setSelectedCamera] = useState<string>("ALL");

  const cameraWiseData = DEMO_CAMERAS.map((cam) => ({
    name: cam.id,
    fullName: cam.name,
    incidents: cam.id === "CAM-01" ? 12 : cam.id === "CAM-04" ? 6 : cam.id === "CAM-02" ? 4 : 2,
  }));

  const eventsByTypeData = Object.entries(DEMO_STATS.by_event_type).map(([key, count]) => ({
    name: key.replace(/_/g, " "),
    count: count,
  }));

  return (
    <div className="space-y-4">
      {/* 1. TOP HEADER & FILTER BAR */}
      <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] flex flex-wrap items-center justify-between gap-3 shadow-md">
        <div>
          <h2 className="text-base font-extrabold text-white tracking-wide uppercase flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            Safety Intelligence & Quantitative Analytics
          </h2>
          <p className="text-xs text-slate-400 font-medium">
            Aggregated multi-camera violation trends, activity profiling, and severity metrics.
          </p>
        </div>

        {/* Date and Camera Filters */}
        <div className="flex items-center gap-2.5 text-xs font-mono">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-slate-200">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedRange}
              onChange={(e) => setSelectedRange(e.target.value)}
              className="bg-transparent focus:outline-none cursor-pointer"
            >
              <option value="24h">Past 24 Hours</option>
              <option value="7d">Past 7 Days</option>
              <option value="30d">Past 30 Days</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-slate-200">
            <Camera className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedCamera}
              onChange={(e) => setSelectedCamera(e.target.value)}
              className="bg-transparent focus:outline-none cursor-pointer"
            >
              <option value="ALL">All 6 Cameras</option>
              {DEMO_CAMERAS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} - {c.name.split("-")[0]}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 2. SYSTEM PERFORMANCE KPI ROW */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A]">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">
            Avg Event Detection Latency
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-mono font-extrabold text-cyan-400">38.4 ms</span>
            <span className="text-[10px] text-emerald-400 font-mono">Sub-frame</span>
          </div>
          <p className="text-[10px] text-slate-500 mt-1">YOLO11n + ByteTrack pipeline</p>
        </div>

        <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A]">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">
            Average Processing FPS
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-mono font-extrabold text-emerald-400">14.8 FPS</span>
            <span className="text-[10px] text-slate-400 font-mono">12.0 target</span>
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Real-time skip-sampling active</p>
        </div>

        <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A]">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">
            Total Incidents Logged
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-mono font-extrabold text-white">24</span>
            <span className="text-[10px] text-red-400 font-mono">2 Critical</span>
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Indexed in SQLite database</p>
        </div>

        <div className="p-3.5 rounded-xl bg-[#111C2E] border border-[#25334A]">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">
            Resolution Rate
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-mono font-extrabold text-blue-400">87.5%</span>
            <span className="text-[10px] text-emerald-400 font-mono">21 / 24</span>
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Supervisory acknowledgments</p>
        </div>
      </div>

      {/* 3. CHARTS GRID: ROW 1 (TIMELINE + SEVERITY) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Events Over Time (8 Cols) */}
        <div className="lg:col-span-8 p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md">
          <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-800">
            <div>
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-cyan-400" />
                Safety Incidents & Risk Score Over Time
              </h3>
              <p className="text-[10px] text-slate-400 font-mono">
                Hourly incident frequency vs average perimeter risk score
              </p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={DEMO_ANALYTICS_TIMELINE}>
                <defs>
                  <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="incidentGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#EF4444" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="time" stroke="#64748B" fontSize={11} />
                <YAxis stroke="#64748B" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0F172A",
                    borderColor: "#334155",
                    fontSize: "12px",
                    borderRadius: "8px",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "10px" }} />
                <Area
                  type="monotone"
                  dataKey="avgRisk"
                  name="Avg Risk Score"
                  stroke="#3B82F6"
                  fillOpacity={1}
                  fill="url(#riskGrad)"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="incidents"
                  name="Violations Count"
                  stroke="#EF4444"
                  fillOpacity={1}
                  fill="url(#incidentGrad)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Severity Distribution Donut (4 Cols) */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md flex flex-col justify-between">
          <div className="pb-2 mb-2 border-b border-slate-800">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Severity Distribution
            </h3>
            <p className="text-[10px] text-slate-400 font-mono">
              Categorized by 0-100 deterministic risk tiers
            </p>
          </div>

          <div className="h-52 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={DEMO_SEVERITY_DISTRIBUTION}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {DEMO_SEVERITY_DISTRIBUTION.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0F172A",
                    borderColor: "#334155",
                    fontSize: "12px",
                    borderRadius: "8px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Legend items */}
          <div className="grid grid-cols-2 gap-2 text-[11px] pt-2 border-t border-slate-800">
            {DEMO_SEVERITY_DISTRIBUTION.map((s) => (
              <div key={s.name} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                <span className="text-slate-300 font-mono">{s.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 4. CHARTS GRID: ROW 2 (ACTIVITY DISTRIBUTION + EVENTS BY TYPE + CAMERA BREAKDOWN) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Human Activity Distribution (4 Cols) */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md">
          <div className="pb-2 mb-3 border-b border-slate-800">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Activity Profiling (HAR Model)
            </h3>
            <p className="text-[10px] text-slate-400 font-mono">
              Classified actions via 205-dim Temporal Transformer
            </p>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={DEMO_ACTIVITY_DISTRIBUTION} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis type="number" stroke="#64748B" fontSize={11} />
                <YAxis dataKey="name" type="category" stroke="#94A3B8" fontSize={11} width={65} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0F172A",
                    borderColor: "#334155",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="value" name="% of Total" fill="#06B6D4" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Violations by Category (4 Cols) */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md">
          <div className="pb-2 mb-3 border-b border-slate-800">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Violations by Category
            </h3>
            <p className="text-[10px] text-slate-400 font-mono">
              Frequency of safety rule breaches
            </p>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={eventsByTypeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="name" stroke="#64748B" fontSize={10} angle={-15} textAnchor="end" height={40} />
                <YAxis stroke="#64748B" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0F172A",
                    borderColor: "#334155",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="count" name="Violations" fill="#F97316" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Camera-wise Distribution (4 Cols) */}
        <div className="lg:col-span-4 p-4 rounded-xl bg-[#111C2E] border border-[#25334A] shadow-md">
          <div className="pb-2 mb-3 border-b border-slate-800">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Camera-Wise Event Load
            </h3>
            <p className="text-[10px] text-slate-400 font-mono">
              Distribution of incidents by surveillance post
            </p>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cameraWiseData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="name" stroke="#64748B" fontSize={11} />
                <YAxis stroke="#64748B" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0F172A",
                    borderColor: "#334155",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="incidents" name="Incidents" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

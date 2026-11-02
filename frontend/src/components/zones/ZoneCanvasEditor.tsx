import React, { useState, useRef, useEffect } from "react";
import { ZonePolygon } from "@/types/camera";
import { Plus, Trash2, Check, ShieldAlert } from "lucide-react";

interface ZoneCanvasEditorProps {
  zones: ZonePolygon[];
  onSaveZone: (zone: ZonePolygon) => void;
  onDeleteZone: (id: string) => void;
  className?: string;
}

export const ZoneCanvasEditor: React.FC<ZoneCanvasEditorProps> = ({
  zones,
  onSaveZone,
  onDeleteZone,
  className = "",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [currentPoints, setCurrentPoints] = useState<[number, number][]>([]);
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [zoneName, setZoneName] = useState<string>("");
  const [zoneType, setZoneType] = useState<"restricted" | "hazard">("restricted");

  useEffect(() => {
    drawCanvas();
  }, [zones, currentPoints, isDrawing]);

  const drawCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;

    // Background
    ctx.fillStyle = "#0F172A";
    ctx.fillRect(0, 0, w, h);

    // Subtle blueprint grid
    ctx.strokeStyle = "#1E293B";
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 30) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 30) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Existing saved zones
    zones.forEach((z) => {
      if (z.vertices.length < 3) return;
      ctx.beginPath();
      ctx.moveTo(z.vertices[0][0], z.vertices[0][1]);
      for (let i = 1; i < z.vertices.length; i++) {
        ctx.lineTo(z.vertices[i][0], z.vertices[i][1]);
      }
      ctx.closePath();

      ctx.fillStyle =
        z.zoneType === "hazard"
          ? "rgba(239, 68, 68, 0.2)"
          : "rgba(249, 115, 22, 0.2)";
      ctx.fill();

      ctx.strokeStyle = z.zoneType === "hazard" ? "#EF4444" : "#F97316";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Label
      ctx.fillStyle = "#F8FAFC";
      ctx.font = "bold 11px monospace";
      ctx.fillText(z.name, z.vertices[0][0] + 5, z.vertices[0][1] + 15);
    });

    // In-progress points and rubberband lines
    if (currentPoints.length > 0) {
      ctx.strokeStyle = "#38BDF8";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);

      ctx.beginPath();
      ctx.moveTo(currentPoints[0][0], currentPoints[0][1]);
      for (let i = 1; i < currentPoints.length; i++) {
        ctx.lineTo(currentPoints[i][0], currentPoints[i][1]);
      }
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw vertices
      currentPoints.forEach((pt, idx) => {
        ctx.fillStyle = idx === 0 ? "#10B981" : "#38BDF8";
        ctx.beginPath();
        ctx.arc(pt[0], pt[1], 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#FFFFFF";
        ctx.lineWidth = 1;
        ctx.stroke();
      });
    }
  };

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((e.clientY - rect.top) / rect.height) * canvas.height;

    setCurrentPoints((prev) => [...prev, [Math.round(x), Math.round(y)]]);
  };

  const handleStartDrawing = () => {
    setIsDrawing(true);
    setCurrentPoints([]);
  };

  const handleFinishZone = () => {
    if (currentPoints.length < 3) {
      alert("A polygon zone requires at least 3 vertices.");
      return;
    }
    const finalName = zoneName.trim() || `Zone ${zones.length + 1}`;
    const newZone: ZonePolygon = {
      id: `ZONE-${Date.now().toString().slice(-4)}`,
      name: finalName,
      cameraId: "CAM-01",
      vertices: currentPoints,
      zoneType: zoneType,
      color: zoneType === "hazard" ? "#EF4444" : "#F97316",
      createdAt: new Date().toISOString(),
    };

    onSaveZone(newZone);
    setIsDrawing(false);
    setCurrentPoints([]);
    setZoneName("");
  };

  const handleCancel = () => {
    setIsDrawing(false);
    setCurrentPoints([]);
  };

  return (
    <div className={`flex flex-col gap-4 ${className}`}>
      {/* Action Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-slate-900 border border-slate-800">
        <div className="flex items-center gap-3">
          {!isDrawing ? (
            <button
              onClick={handleStartDrawing}
              className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors shadow"
            >
              <Plus className="w-4 h-4" />
              Draw New Polygon Zone
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Zone Name (e.g. Crane Drop Zone)"
                value={zoneName}
                onChange={(e) => setZoneName(e.target.value)}
                className="px-2.5 py-1 text-xs bg-slate-950 border border-slate-700 rounded text-slate-100 focus:outline-none focus:border-blue-500"
              />
              <select
                value={zoneType}
                onChange={(e) => setZoneType(e.target.value as any)}
                className="px-2 py-1 text-xs bg-slate-950 border border-slate-700 rounded text-slate-200"
              >
                <option value="restricted">Restricted Zone</option>
                <option value="hazard">Hazard / Exclusion</option>
              </select>
              <button
                onClick={handleFinishZone}
                disabled={currentPoints.length < 3}
                className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-semibold flex items-center gap-1"
              >
                <Check className="w-3.5 h-3.5" />
                Save Zone ({currentPoints.length} pts)
              </button>
              <button
                onClick={handleCancel}
                className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Cancel
              </button>
            </div>
          )}
        </div>

        <span className="text-xs text-slate-400 font-mono">
          {isDrawing
            ? "Click on canvas to add vertices. 3+ points required."
            : `${zones.length} active zones configured`}
        </span>
      </div>

      {/* Drawing Canvas */}
      <div className="relative w-full aspect-video rounded-xl overflow-hidden border border-slate-800 bg-slate-950 shadow-inner">
        <canvas
          ref={canvasRef}
          width={640}
          height={360}
          onClick={handleCanvasClick}
          className={`w-full h-full object-contain block ${
            isDrawing ? "cursor-crosshair" : "cursor-default"
          }`}
        />

        {isDrawing && (
          <div className="absolute top-3 left-3 px-2 py-1 rounded bg-blue-950/80 border border-blue-500/50 text-[11px] text-blue-300 font-mono">
            CLICK TO PLACE VERTEX #{currentPoints.length + 1}
          </div>
        )}
      </div>

      {/* Configured Zones List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {zones.map((z) => (
          <div
            key={z.id}
            className="flex items-center justify-between p-3 rounded-lg bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition"
          >
            <div className="flex items-center gap-2.5">
              <ShieldAlert
                className={`w-4 h-4 ${
                  z.zoneType === "hazard" ? "text-red-400" : "text-amber-400"
                }`}
              />
              <div>
                <p className="text-xs font-bold text-slate-200">{z.name}</p>
                <p className="text-[10px] text-slate-400 uppercase font-mono">
                  {z.zoneType} • {z.vertices.length} vertices
                </p>
              </div>
            </div>

            <button
              onClick={() => onDeleteZone(z.id)}
              className="p-1.5 rounded hover:bg-red-950 text-slate-400 hover:text-red-400 transition"
              title="Delete Zone"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};


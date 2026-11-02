import React from "react";
import { Eye, ShieldAlert, User, HardHat, Layers } from "lucide-react";

export interface OverlayVisibilityState {
  showBoundingBoxes: boolean;
  showLabels: boolean;
  showPPE: boolean;
  showZones: boolean;
  showRiskBadge: boolean;
}

interface OverlayControlsProps {
  state: OverlayVisibilityState;
  onChange: (key: keyof OverlayVisibilityState, value: boolean) => void;
  className?: string;
}

export const OverlayControls: React.FC<OverlayControlsProps> = ({
  state,
  onChange,
  className = "",
}) => {
  return (
    <div
      className={`flex flex-wrap items-center gap-2 p-1.5 rounded-lg bg-slate-900/80 backdrop-blur-md border border-slate-700/60 text-xs ${className}`}
    >
      <span className="text-slate-400 font-medium px-2 flex items-center gap-1.5 border-r border-slate-700/60 pr-2.5">
        <Layers className="w-3.5 h-3.5 text-blue-400" />
        Overlays
      </span>

      <button
        onClick={() => onChange("showBoundingBoxes", !state.showBoundingBoxes)}
        className={`px-2 py-1 rounded transition-colors flex items-center gap-1 font-medium ${
          state.showBoundingBoxes
            ? "bg-blue-600/30 text-blue-300 border border-blue-500/40"
            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
        }`}
        title="Toggle Person Bounding Boxes"
      >
        <Eye className="w-3 h-3" />
        Boxes
      </button>

      <button
        onClick={() => onChange("showLabels", !state.showLabels)}
        className={`px-2 py-1 rounded transition-colors flex items-center gap-1 font-medium ${
          state.showLabels
            ? "bg-blue-600/30 text-blue-300 border border-blue-500/40"
            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
        }`}
        title="Toggle Track IDs & Activity Labels"
      >
        <User className="w-3 h-3" />
        IDs & HAR
      </button>

      <button
        onClick={() => onChange("showPPE", !state.showPPE)}
        className={`px-2 py-1 rounded transition-colors flex items-center gap-1 font-medium ${
          state.showPPE
            ? "bg-blue-600/30 text-blue-300 border border-blue-500/40"
            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
        }`}
        title="Toggle PPE Helmet/Vest Badges"
      >
        <HardHat className="w-3 h-3" />
        PPE Badges
      </button>

      <button
        onClick={() => onChange("showZones", !state.showZones)}
        className={`px-2 py-1 rounded transition-colors flex items-center gap-1 font-medium ${
          state.showZones
            ? "bg-amber-600/30 text-amber-300 border border-amber-500/40"
            : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
        }`}
        title="Toggle Restricted Zone Boundaries"
      >
        <ShieldAlert className="w-3 h-3" />
        Hazard Zones
      </button>
    </div>
  );
};


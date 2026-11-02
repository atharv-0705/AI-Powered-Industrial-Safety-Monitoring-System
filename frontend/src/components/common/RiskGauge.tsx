import React from "react";
import { SeverityLevel } from "@/types/safety";
import { formatRiskScore, formatSeverityColor } from "@/lib/utils";

interface RiskGaugeProps {
  score: number;
  level?: SeverityLevel;
  type?: "circular" | "horizontal";
  size?: "sm" | "md" | "lg";
  label?: string;
  className?: string;
}

export const RiskGauge: React.FC<RiskGaugeProps> = ({
  score,
  level: overrideLevel,
  type = "horizontal",
  size = "md",
  label,
  className = "",
}) => {
  const { level: autoLevel, label: autoLabel } = formatRiskScore(score);
  const level = overrideLevel || autoLevel;
  const styles = formatSeverityColor(level);

  const clamped = Math.min(100, Math.max(0, score));

  if (type === "circular") {
    const radius = size === "sm" ? 32 : size === "lg" ? 54 : 42;
    const strokeWidth = size === "sm" ? 5 : size === "lg" ? 8 : 6;
    const normalizedRadius = radius - strokeWidth / 2;
    const circumference = normalizedRadius * 2 * Math.PI;
    const strokeDashoffset = circumference - (clamped / 100) * circumference;

    return (
      <div className={`relative flex flex-col items-center justify-center ${className}`}>
        <svg
          height={radius * 2}
          width={radius * 2}
          className="-rotate-90 transform"
        >
          {/* Background circle */}
          <circle
            stroke="#1E293B"
            fill="transparent"
            strokeWidth={strokeWidth}
            r={normalizedRadius}
            cx={radius}
            cy={radius}
          />
          {/* Progress circle */}
          <circle
            stroke={
              level === "CRITICAL"
                ? "#EF4444"
                : level === "HIGH"
                ? "#F97316"
                : level === "MEDIUM"
                ? "#F59E0B"
                : "#10B981"
            }
            fill="transparent"
            strokeWidth={strokeWidth}
            strokeDasharray={`${circumference} ${circumference}`}
            style={{ strokeDashoffset, transition: "stroke-dashoffset 0.5s ease" }}
            strokeLinecap="round"
            r={normalizedRadius}
            cx={radius}
            cy={radius}
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="font-mono font-bold text-slate-100 text-lg leading-tight">
            {clamped.toFixed(0)}
          </span>
          <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
            / 100
          </span>
        </div>
      </div>
    );
  }

  // Horizontal bar gauge
  return (
    <div className={`w-full ${className}`}>
      <div className="flex items-center justify-between mb-1 text-xs">
        <span className="text-slate-400 font-medium">
          {label || autoLabel}
        </span>
        <span className={`font-mono font-bold ${styles.text}`}>
          {clamped.toFixed(1)} <span className="text-slate-500 font-normal">/ 100</span>
        </span>
      </div>

      <div className="relative h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className={`h-full rounded-full transition-all duration-500 ${styles.solidBg}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
};


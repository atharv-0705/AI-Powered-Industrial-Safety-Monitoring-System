import React from "react";
import { SeverityLevel } from "@/types/safety";
import { formatSeverityColor } from "@/lib/utils";

interface SeverityBadgeProps {
  severity: SeverityLevel;
  className?: string;
  size?: "sm" | "md" | "lg";
  showDot?: boolean;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  className = "",
  size = "md",
  showDot = true,
}) => {
  const styles = formatSeverityColor(severity);

  const sizeClasses = {
    sm: "px-1.5 py-0.5 text-xs font-semibold gap-1",
    md: "px-2.5 py-1 text-xs font-semibold gap-1.5",
    lg: "px-3 py-1.5 text-sm font-bold gap-2",
  };

  return (
    <span
      className={`inline-flex items-center rounded-md border uppercase tracking-wider font-mono ${styles.badge} ${sizeClasses[size]} ${className}`}
    >
      {showDot && (
        <span
          className={`h-1.5 w-1.5 rounded-full ${styles.dot} ${
            severity === "CRITICAL" ? "animate-ping" : ""
          }`}
        />
      )}
      {severity}
    </span>
  );
};


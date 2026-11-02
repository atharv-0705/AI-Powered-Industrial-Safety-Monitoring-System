import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { SeverityLevel } from "@/types/safety";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSeverityColor(severity: SeverityLevel) {
  switch (severity) {
    case "CRITICAL":
      return {
        bg: "bg-red-500/15",
        text: "text-red-400",
        border: "border-red-500/40",
        solidBg: "bg-red-600",
        badge: "bg-red-950/70 border-red-700/50 text-red-300",
        dot: "bg-red-500",
        glow: "shadow-[0_0_12px_rgba(239,68,68,0.35)]",
      };
    case "HIGH":
      return {
        bg: "bg-orange-500/15",
        text: "text-orange-400",
        border: "border-orange-500/40",
        solidBg: "bg-orange-600",
        badge: "bg-orange-950/70 border-orange-700/50 text-orange-300",
        dot: "bg-orange-500",
        glow: "shadow-[0_0_12px_rgba(249,115,22,0.3)]",
      };
    case "MEDIUM":
      return {
        bg: "bg-amber-500/15",
        text: "text-amber-400",
        border: "border-amber-500/40",
        solidBg: "bg-amber-600",
        badge: "bg-amber-950/70 border-amber-700/50 text-amber-300",
        dot: "bg-amber-400",
        glow: "shadow-[0_0_10px_rgba(245,158,11,0.25)]",
      };
    case "LOW":
    default:
      return {
        bg: "bg-emerald-500/15",
        text: "text-emerald-400",
        border: "border-emerald-500/40",
        solidBg: "bg-emerald-600",
        badge: "bg-emerald-950/70 border-emerald-700/50 text-emerald-300",
        dot: "bg-emerald-400",
        glow: "shadow-[0_0_10px_rgba(16,185,129,0.25)]",
      };
  }
}

export function formatRiskScore(score: number): {
  level: SeverityLevel;
  label: string;
} {
  if (score >= 80) return { level: "CRITICAL", label: "Critical Hazard" };
  if (score >= 60) return { level: "HIGH", label: "High Risk" };
  if (score >= 30) return { level: "MEDIUM", label: "Elevated Risk" };
  return { level: "LOW", label: "Compliant" };
}

export function formatTimestamp(ts: number | string): string {
  if (!ts) return "--:--:--";
  const date = typeof ts === "number" ? new Date(ts > 10000000000 ? ts : ts * 1000) : new Date(ts);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatDateTime(ts: number | string): string {
  if (!ts) return "N/A";
  const date = typeof ts === "number" ? new Date(ts > 10000000000 ? ts : ts * 1000) : new Date(ts);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatViolationName(vType: string): string {
  switch (vType) {
    case "FALL":
      return "Potential Fall Detected";
    case "MISSING_HELMET":
      return "Missing Safety Helmet";
    case "MISSING_VEST":
      return "Missing Hi-Vis Vest";
    case "RESTRICTED_ZONE":
      return "Restricted Zone Intrusion";
    case "DANGEROUS_CLIMB":
      return "Dangerous Unprotected Climb";
    default:
      return vType.replace(/_/g, " ");
  }
}


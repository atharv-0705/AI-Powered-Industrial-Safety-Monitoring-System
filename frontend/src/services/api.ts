/**
 * Typed REST API service boundary.
 *
 * Implements communication with FastAPI backend endpoints:
 * - /api/health
 * - /api/incidents
 * - /api/incidents/stats/summary
 * - /api/incidents/{id}
 * - /api/incidents/{id}/resolve
 * - /api/pipeline/status
 * - /api/pipeline/start
 * - /api/pipeline/stop
 *
 * Provides transparent fallback to DEMO MODE if backend is unreachable.
 */

import { IncidentRecord, IncidentStatsSummary, PipelineStatus, SystemHealth } from "@/types/safety";
import { CameraFeed, ZonePolygon } from "@/types/camera";
import { SafetySettings } from "@/types/settings";
import {
  DEMO_CAMERAS,
  DEMO_HEALTH,
  DEMO_INCIDENTS,
  DEMO_SETTINGS,
  DEMO_STATS,
  DEMO_ZONES,
} from "@/data/demoData";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

// In-memory local stores for DEMO / local mode overrides
let localIncidents: IncidentRecord[] = [...DEMO_INCIDENTS];
let localZones: ZonePolygon[] = [...DEMO_ZONES];
let localSettings: SafetySettings = { ...DEMO_SETTINGS };

export const apiService = {
  /**
   * Health Check
   */
  async getHealth(): Promise<{ data: SystemHealth; isLive: boolean }> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/health`, { method: "GET" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { data, isLive: true };
    } catch {
      return { data: DEMO_HEALTH, isLive: false };
    }
  },

  /**
   * Incident History
   */
  async getIncidents(params?: {
    risk_level?: string;
    event_type?: string;
    resolved?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<{ data: IncidentRecord[]; isLive: boolean }> {
    try {
      const q = new URLSearchParams();
      if (params?.risk_level) q.set("risk_level", params.risk_level);
      if (params?.event_type) q.set("event_type", params.event_type);
      if (params?.resolved !== undefined) q.set("resolved", String(params.resolved));
      if (params?.limit) q.set("limit", String(params.limit));
      if (params?.offset) q.set("offset", String(params.offset));

      const res = await fetch(`${API_BASE_URL}/api/incidents?${q.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: IncidentRecord[] = await res.json();
      return { data, isLive: true };
    } catch {
      // Filter local demo incidents
      let filtered = [...localIncidents];
      if (params?.risk_level) {
        filtered = filtered.filter((i) => i.risk_level === params.risk_level);
      }
      if (params?.event_type) {
        filtered = filtered.filter((i) => i.event_type === params.event_type);
      }
      if (params?.resolved !== undefined) {
        filtered = filtered.filter((i) => i.resolved === params.resolved);
      }
      return { data: filtered, isLive: false };
    }
  },

  /**
   * Incident Details
   */
  async getIncident(id: number): Promise<{ data: IncidentRecord | null; isLive: boolean }> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/incidents/${id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { data, isLive: true };
    } catch {
      const incident = localIncidents.find((i) => i.id === id) || null;
      return { data: incident, isLive: false };
    }
  },

  /**
   * Resolve Incident
   */
  async resolveIncident(id: number): Promise<{ success: boolean; isLive: boolean }> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/incidents/${id}/resolve`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return { success: true, isLive: true };
    } catch {
      localIncidents = localIncidents.map((i) =>
        i.id === id ? { ...i, resolved: true, resolved_at: Date.now() / 1000 } : i
      );
      return { success: true, isLive: false };
    }
  },

  /**
   * Incident Statistics Summary
   */
  async getIncidentStats(): Promise<{ data: IncidentStatsSummary; isLive: boolean }> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/incidents/stats/summary`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { data, isLive: true };
    } catch {
      const unresolved = localIncidents.filter((i) => !i.resolved).length;
      return {
        data: {
          ...DEMO_STATS,
          total_incidents: localIncidents.length,
          unresolved_incidents: unresolved,
          resolved_incidents: localIncidents.length - unresolved,
        },
        isLive: false,
      };
    }
  },

  /**
   * Pipeline Status
   */
  async getPipelineStatus(): Promise<{ data: PipelineStatus; isLive: boolean }> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/pipeline/status`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { data, isLive: true };
    } catch {
      return {
        data: {
          running: false,
          fps: 12.0,
          frame_count: 0,
          scene_risk: 15.0,
          video_source: "0",
        },
        isLive: false,
      };
    }
  },

  /**
   * Start Pipeline
   */
  async startPipeline(source?: string): Promise<{ success: boolean; details?: unknown }> {
    try {
      const url = source
        ? `${API_BASE_URL}/api/pipeline/start?source=${encodeURIComponent(source)}`
        : `${API_BASE_URL}/api/pipeline/start`;
      const res = await fetch(url, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { success: true, details: data };
    } catch (e: unknown) {
      return { success: false, details: e instanceof Error ? e.message : String(e) };
    }
  },

  /**
   * Stop Pipeline
   */
  async stopPipeline(): Promise<{ success: boolean }> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/pipeline/stop`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return { success: true };
    } catch {
      return { success: false };
    }
  },

  /**
   * Camera List
   */
  async getCameras(): Promise<CameraFeed[]> {
    return DEMO_CAMERAS;
  },

  /**
   * Restricted Zones
   */
  async getZones(): Promise<ZonePolygon[]> {
    const saved = localStorage.getItem("industrial_safety_zones");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return localZones;
  },

  async saveZones(zones: ZonePolygon[]): Promise<boolean> {
    localZones = zones;
    localStorage.setItem("industrial_safety_zones", JSON.stringify(zones));
    return true;
  },

  /**
   * Settings
   */
  async getSettings(): Promise<SafetySettings> {
    const saved = localStorage.getItem("industrial_safety_settings");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return localSettings;
  },

  async updateSettings(settings: SafetySettings): Promise<boolean> {
    localSettings = settings;
    localStorage.setItem("industrial_safety_settings", JSON.stringify(settings));
    return true;
  },
};

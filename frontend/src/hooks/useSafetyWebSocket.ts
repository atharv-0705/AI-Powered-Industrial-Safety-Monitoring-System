import { useState, useEffect, useRef, useCallback } from "react";
import { WebSocketStatus, wsService } from "@/services/websocket";
import { StreamTelemetry, VLMExplanation, WebSocketFramePacket } from "@/types/safety";

export interface UseSafetyWebSocketResult {
  status: WebSocketStatus;
  isConnected: boolean;
  isStale: boolean;
  isDemoMode: boolean;
  setIsDemoMode: (val: boolean) => void;
  frame: string | null;
  telemetry: StreamTelemetry | null;
  latestVlmAlert: { incidentId: number; explanation: VLMExplanation } | null;
  reconnect: () => void;
}

export function useSafetyWebSocket(): UseSafetyWebSocketResult {
  const [status, setStatus] = useState<WebSocketStatus>(wsService.status);
  const [isDemoMode, setIsDemoMode] = useState<boolean>(false);
  const [frame, setFrame] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<StreamTelemetry | null>(null);
  const [latestVlmAlert, setLatestVlmAlert] = useState<{
    incidentId: number;
    explanation: VLMExplanation;
  } | null>(null);
  const [isStale, setIsStale] = useState<boolean>(false);

  const lastFrameTimeRef = useRef<number>(Date.now());
  const staleTimerRef = useRef<number | null>(null);
  const demoIntervalRef = useRef<number | null>(null);

  // Monitor WebSocket status
  useEffect(() => {
    const unsubStatus = wsService.onStatusChange((newStatus) => {
      setStatus(newStatus);
      if (newStatus === "CONNECTED") {
        setIsStale(false);
      }
    });

    const unsubFrame = wsService.onFrame((packet: WebSocketFramePacket) => {
      if (!isDemoMode) {
        setFrame(packet.frame);
        setTelemetry(packet.telemetry);
        lastFrameTimeRef.current = Date.now();
        setIsStale(false);
      }
    });

    const unsubVlm = wsService.onIncidentVerified((id, exp) => {
      setLatestVlmAlert({ incidentId: id, explanation: exp });
    });

    wsService.connect();

    return () => {
      unsubStatus();
      unsubFrame();
      unsubVlm();
    };
  }, [isDemoMode]);

  // Check for stale stream
  useEffect(() => {
    staleTimerRef.current = window.setInterval(() => {
      if (status === "CONNECTED" && !isDemoMode) {
        const diff = Date.now() - lastFrameTimeRef.current;
        if (diff > 3500) {
          setIsStale(true);
        }
      }
    }, 1000);

    return () => {
      if (staleTimerRef.current) clearInterval(staleTimerRef.current);
    };
  }, [status, isDemoMode]);

  // Demo simulation mode loop
  useEffect(() => {
    if (isDemoMode) {
      let frameCount = 0;
      demoIntervalRef.current = window.setInterval(() => {
        frameCount++;
        const now = new Date();

        // Simulated dynamic worker positions
        const t = frameCount * 0.05;
        const worker1X = 220 + Math.sin(t) * 35;
        const worker1Y = 240 + Math.cos(t) * 15;

        const simulatedTelemetry: StreamTelemetry = {
          timestamp: now.toISOString(),
          frame_idx: frameCount,
          fps: 14.8,
          scene_risk: {
            overall_score: 72.5,
            overall_level: "HIGH",
            summary: "ACTIVE HAZARD: 1 worker without safety helmet near restricted zone boundary",
            workers_at_risk: 1,
            active_violations_count: 1,
          },
          workers_count: 2,
          tracks: [
            {
              track_id: 1,
              bbox: [worker1X, worker1Y, worker1X + 110, worker1Y + 220],
              activity: "walking",
              ppe: { has_helmet: false, has_vest: true },
              risk: {
                score: 72.5,
                level: "HIGH",
                factors: ["Violation [MISSING_HELMET]: +25 pts", "Restricted zone boundary proximity: +15 pts"],
              },
            },
            {
              track_id: 2,
              bbox: [460, 200, 570, 430],
              activity: "standing",
              ppe: { has_helmet: true, has_vest: true },
              risk: {
                score: 0.0,
                level: "LOW",
                factors: ["Compliant"],
              },
            },
          ],
          violations: [
            {
              track_id: 1,
              event_type: "MISSING_HELMET",
              severity: "HIGH",
              confidence: 0.92,
              description: "Worker #1 detected missing safety helmet in active zone",
            },
          ],
        };

        setTelemetry(simulatedTelemetry);
      }, 100);
    } else {
      if (demoIntervalRef.current) {
        clearInterval(demoIntervalRef.current);
        demoIntervalRef.current = null;
      }
    }

    return () => {
      if (demoIntervalRef.current) clearInterval(demoIntervalRef.current);
    };
  }, [isDemoMode]);

  const reconnect = useCallback(() => {
    wsService.disconnect();
    wsService.connect();
  }, []);

  return {
    status,
    isConnected: status === "CONNECTED",
    isStale,
    isDemoMode,
    setIsDemoMode,
    frame,
    telemetry,
    latestVlmAlert,
    reconnect,
  };
}


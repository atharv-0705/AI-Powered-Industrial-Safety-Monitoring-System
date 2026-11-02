/**
 * Resilient WebSocket service for low-latency streaming.
 * Handles auto-reconnect, heartbeats, message decoding, and callback dispatching.
 */

import { VLMExplanation, WebSocketFramePacket } from "@/types/safety";

export type WebSocketStatus = "CONNECTING" | "CONNECTED" | "DISCONNECTED" | "ERROR";

type FrameCallback = (packet: WebSocketFramePacket) => void;
type IncidentCallback = (incidentId: number, explanation: VLMExplanation) => void;
type StatusCallback = (status: WebSocketStatus) => void;

class SafetyWebSocketService {
  private socket: WebSocket | null = null;
  private url: string = "";
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 20;
  private reconnectTimer: number | null = null;
  private pingIntervalTimer: number | null = null;
  private isExplicitlyClosed = false;

  private frameListeners: Set<FrameCallback> = new Set();
  private incidentListeners: Set<IncidentCallback> = new Set();
  private statusListeners: Set<StatusCallback> = new Set();

  private _status: WebSocketStatus = "DISCONNECTED";

  get status(): WebSocketStatus {
    return this._status;
  }

  private setStatus(status: WebSocketStatus) {
    this._status = status;
    this.statusListeners.forEach((cb) => cb(status));
  }

  public connect(customUrl?: string) {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isExplicitlyClosed = false;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const defaultUrl = `${protocol}//${host}/ws/stream`;

    this.url = customUrl || import.meta.env.VITE_WS_URL || defaultUrl;

    this.setStatus("CONNECTING");

    try {
      this.socket = new WebSocket(this.url);

      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.setStatus("CONNECTED");
        this.startHeartbeat();
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "FRAME_UPDATE") {
            this.frameListeners.forEach((cb) => cb(data as WebSocketFramePacket));
          } else if (data.type === "INCIDENT_VERIFIED") {
            this.incidentListeners.forEach((cb) =>
              cb(data.incident_id, data.vlm_explanation as VLMExplanation)
            );
          } else if (data.type === "PONG") {
            // Heartbeat acknowledged
          }
        } catch {
          // Non-JSON or binary frames
        }
      };

      this.socket.onclose = () => {
        this.stopHeartbeat();
        this.setStatus("DISCONNECTED");
        if (!this.isExplicitlyClosed) {
          this.scheduleReconnect();
        }
      };

      this.socket.onerror = () => {
        this.setStatus("ERROR");
      };
    } catch {
      this.setStatus("ERROR");
      this.scheduleReconnect();
    }
  }

  public disconnect() {
    this.isExplicitlyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.setStatus("DISCONNECTED");
  }

  public send(data: any) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(typeof data === "string" ? data : JSON.stringify(data));
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.pingIntervalTimer = window.setInterval(() => {
      this.send({ type: "ping", timestamp: Date.now() });
    }, 5000);
  }

  private stopHeartbeat() {
    if (this.pingIntervalTimer) {
      clearInterval(this.pingIntervalTimer);
      this.pingIntervalTimer = null;
    }
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    const delay = Math.min(10000, 1000 * Math.pow(1.5, this.reconnectAttempts));
    this.reconnectAttempts++;

    this.reconnectTimer = window.setTimeout(() => {
      this.connect(this.url);
    }, delay);
  }

  public onFrame(callback: FrameCallback): () => void {
    this.frameListeners.add(callback);
    return () => this.frameListeners.delete(callback);
  }

  public onIncidentVerified(callback: IncidentCallback): () => void {
    this.incidentListeners.add(callback);
    return () => this.incidentListeners.delete(callback);
  }

  public onStatusChange(callback: StatusCallback): () => void {
    this.statusListeners.add(callback);
    callback(this._status);
    return () => this.statusListeners.delete(callback);
  }
}

export const wsService = new SafetyWebSocketService();


// WebSocket hook for live dashboard updates
import { useEffect, useRef } from "react";
import type { WebSocketMessage } from "../lib/types";

type MessageHandler = (msg: WebSocketMessage) => void;

export function useVitalBandWS(onMessage: MessageHandler, hospitalId = "DEFAULT_HOSP") {
  // Keep the latest handler without making it an effect dependency, so a new
  // inline callback on every App render never tears down the socket.
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    // Guards against the old bug: onclose used to schedule a reconnect even
    // when the effect was tearing down, so React StrictMode's double-mount
    // (and every hot reload) leaked an extra socket that kept reconnecting.
    // Each leaked socket re-delivered every alert, double-firing the chime.
    let disposed = false;

    const connect = () => {
      if (disposed) return;

      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      ws = new WebSocket(`${proto}//${window.location.host}/ws?hospital_id=${hospitalId}`);

      ws.onopen = () => console.log("[VitalBand WS] Connected");

      ws.onmessage = (evt) => {
        if (disposed) return;
        try {
          handlerRef.current(JSON.parse(evt.data) as WebSocketMessage);
        } catch {
          // ignore malformed frames
        }
      };

      ws.onclose = () => {
        if (disposed) return;
        console.warn("[VitalBand WS] Disconnected. Reconnecting in 3s...");
        retryTimer = setTimeout(connect, 3000);
      };

      // Let onclose own reconnection; errors are always followed by a close.
      ws.onerror = () => {
        if (!disposed) console.error("[VitalBand WS] Socket error");
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (ws) {
        ws.onclose = null; // prevent the teardown close from reconnecting
        ws.onerror = null;
        ws.onmessage = null;
        ws.close();
      }
    };
  }, [hospitalId]);
}

export const useWebSocket = useVitalBandWS;

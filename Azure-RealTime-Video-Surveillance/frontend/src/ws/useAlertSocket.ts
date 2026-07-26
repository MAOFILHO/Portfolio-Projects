import { useEffect, useRef, useState } from "react";
import type { AlertMessage } from "../types";

const WS_URL: string = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws/alerts";
const RECONNECT_DELAY_MS = 3000;

export interface AlertSocketState {
  connected: boolean;
  alerts: AlertMessage[];
}

/** Connects to the backend's /ws/alerts feed and reconnects automatically on drop. */
export function useAlertSocket(maxAlerts = 50): AlertSocketState {
  const [connected, setConnected] = useState(false);
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    function connect() {
      if (cancelled) return;
      const socket = new WebSocket(WS_URL);
      socketRef.current = socket;

      socket.onopen = () => setConnected(true);

      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          const alert = JSON.parse(event.data) as AlertMessage;
          setAlerts((prev) => [alert, ...prev].slice(0, maxAlerts));
        } catch {
          // Ignore malformed messages rather than crashing the feed.
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      socket.onerror = () => socket.close();
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socketRef.current?.close();
    };
  }, [maxAlerts]);

  return { connected, alerts };
}

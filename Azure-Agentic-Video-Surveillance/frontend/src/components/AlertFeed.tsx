import type { AlertMessage } from "../types";
import { SeverityBadge } from "./SeverityBadge";

interface AlertFeedProps {
  connected: boolean;
  alerts: AlertMessage[];
}

// A compact, real-time "just happened" ticker -- deliberately capped and
// stripped of thumbnails/captions, which is the full historical record
// Event History already owns. Live Alerts exists for the "watch it happen"
// use case (WebSocket push, no polling delay), not for browsing.
export function AlertFeed({ connected, alerts }: AlertFeedProps) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h3>Live Alerts</h3>
        <span className={`status-dot ${connected ? "status-ok" : "status-down"}`} title={connected ? "Connected" : "Disconnected"} />
      </div>
      {alerts.length === 0 ? (
        <p className="empty-state">No alerts yet.</p>
      ) : (
        <ul className="alert-ticker">
          {alerts.map((alert) => (
            <li key={`${alert.event_id}-${alert.triggered_at}`} className="alert-ticker-row">
              <SeverityBadge severity={alert.severity} />
              <span className="alert-ticker-text">
                <strong>{alert.matched_tags.join(", ")}</strong> · {alert.camera_id} ·{" "}
                {new Date(alert.triggered_at).toLocaleTimeString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { fetchAuditEvents, type AuditEvent } from "../api/client";

const REFRESH_INTERVAL_MS = 15_000;

export function AuditTrailPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchAuditEvents(50);
        if (!cancelled) {
          setEvents(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load audit trail");
      }
    }

    load();
    const id = setInterval(load, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="panel">
      <h3>Audit Trail</h3>
      <p className="capture-hint">
        User-facing actions (sign-ins, on-demand CV analysis) reported by the browser. Not
        cryptographically verified server-side -- see docs.
      </p>
      {error && <p className="error-text">{error}</p>}
      {events.length === 0 ? (
        <p className="empty-state">No audit events recorded yet.</p>
      ) : (
        <table className="event-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.RowKey}>
                <td>{new Date(event.LoggedAt).toLocaleString()}</td>
                <td>{event.Actor}</td>
                <td>{event.Action}</td>
                <td>{event.Details || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

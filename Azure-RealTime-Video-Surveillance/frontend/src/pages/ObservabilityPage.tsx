import { useEffect, useState } from "react";
import {
  fetchHealth,
  fetchRecentExceptions,
  fetchRequestsSummary,
  type ExceptionEvent,
  type RequestBucket,
} from "../api/client";

const APPINSIGHTS_PORTAL_URL: string = import.meta.env.VITE_APPINSIGHTS_PORTAL_URL ?? "";
const REFRESH_INTERVAL_MS = 30_000;

function RequestsChart({ buckets }: { buckets: RequestBucket[] }) {
  if (buckets.length === 0) {
    return <p className="empty-state">No request telemetry in the last 24 hours.</p>;
  }
  const maxTotal = Math.max(...buckets.map((b) => b.total), 1);
  return (
    <div className="bar-chart">
      {buckets.map((b) => {
        const hour = new Date(b.timestamp).getHours();
        const okHeight = ((b.total - b.failed) / maxTotal) * 100;
        const failedHeight = (b.failed / maxTotal) * 100;
        return (
          <div key={b.timestamp} className="bar-chart-col" title={`${hour}:00 — ${b.total} requests, ${b.failed} failed`}>
            <div className="bar-chart-bar">
              <div className="bar-chart-segment bar-chart-failed" style={{ height: `${failedHeight}%` }} />
              <div className="bar-chart-segment bar-chart-ok" style={{ height: `${okHeight}%` }} />
            </div>
            <span className="bar-chart-label">{hour}</span>
          </div>
        );
      })}
    </div>
  );
}

export function ObservabilityPage() {
  const [health, setHealth] = useState<{ status: string } | "error" | null>(null);
  const [buckets, setBuckets] = useState<RequestBucket[]>([]);
  const [exceptions, setExceptions] = useState<ExceptionEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      fetchHealth()
        .then((h) => !cancelled && setHealth(h))
        .catch(() => !cancelled && setHealth("error"));
      try {
        const [summary, recentExceptions] = await Promise.all([
          fetchRequestsSummary(24),
          fetchRecentExceptions(20),
        ]);
        if (!cancelled) {
          setBuckets(summary);
          setExceptions(recentExceptions);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load telemetry");
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
    <div className="observability-grid">
      <div className="panel">
        <h3>Backend Health</h3>
        <dl className="profile-fields">
          <dt>Status</dt>
          <dd>
            {health === null && "Checking…"}
            {health === "error" && (
              <>
                <span className="status-dot status-down" /> unreachable
              </>
            )}
            {health && health !== "error" && (
              <>
                <span className="status-dot status-ok" /> {health.status}
              </>
            )}
          </dd>
        </dl>
      </div>

      <div className="panel">
        <h3>Requests (last 24h)</h3>
        {error && <p className="error-text">{error}</p>}
        <RequestsChart buckets={buckets} />
        <div className="chart-legend">
          <span>
            <span className="legend-swatch legend-ok" /> Succeeded
          </span>
          <span>
            <span className="legend-swatch legend-failed" /> Failed
          </span>
        </div>
      </div>

      <div className="panel observability-exceptions">
        <h3>Recent Exceptions</h3>
        {exceptions.length === 0 ? (
          <p className="empty-state">No exceptions in the last 24 hours.</p>
        ) : (
          <table className="event-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Severity</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {exceptions.map((e, i) => (
                <tr key={i} className="row-alert">
                  <td>{new Date(e.timestamp).toLocaleString()}</td>
                  <td>{e.severity}</td>
                  <td>{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {APPINSIGHTS_PORTAL_URL && (
          <p className="capture-hint">
            <a href={APPINSIGHTS_PORTAL_URL} target="_blank" rel="noreferrer">
              View full details in Application Insights ↗
            </a>
          </p>
        )}
      </div>
    </div>
  );
}

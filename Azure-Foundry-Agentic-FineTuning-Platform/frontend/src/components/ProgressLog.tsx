import type { ProgressEvent } from "../api/useAgentRun";

interface ProgressLogProps {
  events: ProgressEvent[];
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
}

/** Live-updating progress log for a still-running background job. */
export default function ProgressLog({ events }: ProgressLogProps) {
  if (events.length === 0) return null;
  const lines = events.map((e) => `[${formatTime(e.ts)}] ${e.message}`).join("\n");
  return (
    <div className="card">
      <h2>Progress</h2>
      <p className="card-sub">
        Live from the backend — updates as the run makes real progress. Safe to leave this
        page and come back; the run keeps going server-side either way.
      </p>
      <div className="trace-log" style={{ maxHeight: 260 }}>
        {lines}
      </div>
    </div>
  );
}

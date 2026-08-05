import type { ModelStatus } from "../types";

const LABELS: Record<ModelStatus, string> = {
  idle: "Not run",
  queued: "Queued",
  running: "Running…",
  completed: "Completed",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: ModelStatus }) {
  return <span className={`status-badge status-${status}`}>{LABELS[status]}</span>;
}

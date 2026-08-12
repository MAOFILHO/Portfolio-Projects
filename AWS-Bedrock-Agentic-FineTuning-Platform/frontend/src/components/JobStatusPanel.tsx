import { useEffect, useRef, useState } from "react";

import type { FinetuneStatusEvent } from "../api/types";

interface JobStatusPanelProps {
  jobArn: string | null;
  statusLog: FinetuneStatusEvent[];
}

const STATUS_MESSAGES: Record<string, string> = {
  InProgress: "Training started — Bedrock is processing your fine-tuning job.",
  Completed: "Training completed.",
  Failed: "Training failed.",
  Stopped: "Training was stopped.",
  Stopping: "Training is stopping.",
};

function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function eventMessage(event: FinetuneStatusEvent, prev: FinetuneStatusEvent | null): string {
  if (event.status === "Failed" && event.failure_message) {
    return event.failure_message;
  }
  if (event.status === "Completed" && event.output_model_arn) {
    return `${STATUS_MESSAGES.Completed} Output model: ${event.output_model_arn}`;
  }
  if (!event.is_status_change) {
    return `Still ${event.status} — data validation: ${event.validation_status ?? "unknown"}, training: ${event.training_status ?? "unknown"}`;
  }
  if (prev) {
    if (event.training_status !== prev.training_status) {
      return `Training phase: ${prev.training_status ?? "—"} → ${event.training_status ?? "unknown"}`;
    }
    if (event.validation_status !== prev.validation_status) {
      return `Data validation phase: ${prev.validation_status ?? "—"} → ${event.validation_status ?? "unknown"}`;
    }
  }
  return STATUS_MESSAGES[event.status] ?? event.status;
}

export function JobStatusPanel({ jobArn, statusLog }: JobStatusPanelProps) {
  const [now, setNow] = useState(() => Date.now());

  const latest = statusLog[statusLog.length - 1] ?? null;
  const creationTimeIso = statusLog.find((e) => e.creation_time)?.creation_time ?? null;
  const creationTimeMs = creationTimeIso ? new Date(creationTimeIso).getTime() : null;
  const isRunning = latest?.status === "InProgress" || latest?.status === "Stopping";
  const jobName = statusLog.find((e) => e.job_name)?.job_name ?? null;
  const resolvedJobArn = jobArn ?? statusLog.find((e) => e.job_arn)?.job_arn ?? null;

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [isRunning]);

  const logEndRef = useRef<HTMLLIElement>(null);
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [statusLog.length]);

  return (
    <div>
      {jobName && (
        <p>
          <strong>Job ID:</strong> <code>{jobName}</code>
        </p>
      )}
      {resolvedJobArn && (
        <p>
          Job ARN: <code>{resolvedJobArn}</code>
        </p>
      )}

      {latest && (
        <p>
          <strong>Status:</strong> {latest.status}
          {creationTimeMs && (
            <span className="job-elapsed"> · running for {formatElapsed(now - creationTimeMs)}</span>
          )}
        </p>
      )}

      {latest && (latest.validation_status || latest.training_status) && (
        <p className="job-subphases">
          Data validation: <strong>{latest.validation_status ?? "—"}</strong> · Training:{" "}
          <strong>{latest.training_status ?? "—"}</strong>
        </p>
      )}

      {isRunning && (
        <div className="progress-indeterminate" role="progressbar" aria-label="Fine-tuning in progress">
          <div className="progress-indeterminate-bar" />
        </div>
      )}

      <h4>Event log ({statusLog.length}) — persisted since job start, survives refresh</h4>
      <ul className="event-log">
        {statusLog.map((event, i) => {
          const prev = i > 0 ? statusLog[i - 1] : null;
          const message = eventMessage(event, prev);
          return (
            <li
              key={i}
              className={`event-log-item${event.is_status_change ? "" : " event-log-item-heartbeat"}`}
            >
              <span className="event-log-time">
                {event.logged_at ? new Date(event.logged_at).toLocaleString() : ""}
              </span>
              <span className="event-log-status">{event.status}</span>
              <span className="event-log-message">{message}</span>
            </li>
          );
        })}
        {statusLog.length === 0 && (
          <li className="event-log-item">
            <span className="event-log-message">Connecting to job status stream…</span>
          </li>
        )}
        <li ref={logEndRef} aria-hidden="true" style={{ height: 0, padding: 0, border: "none" }} />
      </ul>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type AgentJobPayload } from "./client";

export type Demo = "discovery" | "finetune" | "comparison";

export interface ProgressEvent {
  ts: number;
  message: string;
}

interface AgentRunState<T> {
  loading: boolean;
  elapsedSeconds: number;
  events: ProgressEvent[];
  error: string | null;
  result: T | null;
  trace: string[];
  blockedError: string | null;
  run: () => Promise<void>;
}

const POLL_MS = 2000;
const storageKey = (demo: Demo) => `foundry.activeJob.${demo}`;

/**
 * Drives one demo via the background-job endpoints (POST /agent/invoke/start
 * + GET /agent/jobs/{id}) instead of one blocking POST /agent/invoke.
 *
 * Two things this buys over the blocking call, both load-bearing in live
 * mode where a run can take 30-60 minutes:
 *
 * 1. Progress: the job registry (see src/app/jobs.py) accumulates
 *    timestamped events server-side as the run executes: this polls for
 *    them, so the UI has something better than a static "Running…" label.
 * 2. Refresh survival: the job id is stashed in localStorage the moment the
 *    run starts. On mount, if a job id is already there, this resumes
 *    polling it — a page refresh (or reopening the tab later) reattaches to
 *    the still-running (or since-finished) job instead of losing it, because
 *    the run itself lives in the backend process, not in this component's
 *    state.
 */
export function useAgentRun<T = Record<string, unknown>>(demo: Demo): AgentRunState<T> {
  const [loading, setLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<T | null>(null);
  const [trace, setTrace] = useState<string[]>([]);
  const [blockedError, setBlockedError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyPayload = useCallback(
    (payload: AgentJobPayload) => {
      setElapsedSeconds(payload.elapsed_seconds);
      setEvents(payload.events);
      if (payload.status === "running") return;

      // Terminal — stop polling and settle final state.
      stopPolling();
      setLoading(false);
      localStorage.removeItem(storageKey(demo));
      setTrace(payload.trace ?? []);
      setResult((payload.result as T) ?? null);
      if (payload.status === "failed" || payload.error) {
        setBlockedError(payload.error ?? "run failed");
      }
    },
    [demo, stopPolling],
  );

  const pollJob = useCallback(
    (jobId: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const payload = await api.agentJobStatus(jobId);
          applyPayload(payload);
        } catch (err) {
          stopPolling();
          setLoading(false);
          localStorage.removeItem(storageKey(demo));
          setError(err instanceof ApiError ? err.message : "Lost contact with the job.");
        }
      }, POLL_MS);
    },
    [applyPayload, demo, stopPolling],
  );

  // Resume an in-flight (or just-finished) job after a refresh: the job id
  // survives in localStorage even though this component's state doesn't.
  useEffect(() => {
    const savedId = localStorage.getItem(storageKey(demo));
    if (!savedId) return;
    setLoading(true);
    api
      .agentJobStatus(savedId)
      .then((payload) => {
        applyPayload(payload);
        if (payload.status === "running") pollJob(savedId);
      })
      .catch(() => {
        localStorage.removeItem(storageKey(demo));
        setLoading(false);
      });
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demo]);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    setBlockedError(null);
    setEvents([]);
    setElapsedSeconds(0);
    try {
      const started = await api.startAgent(demo);
      localStorage.setItem(storageKey(demo), started.job_id);
      applyPayload(started);
      pollJob(started.job_id);
    } catch (err) {
      setLoading(false);
      setError(err instanceof ApiError ? err.message : "Request failed. Is the API running?");
    }
  }, [applyPayload, demo, pollJob]);

  return { loading, elapsedSeconds, events, error, result, trace, blockedError, run };
}

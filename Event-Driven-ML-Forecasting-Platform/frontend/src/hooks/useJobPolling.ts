import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ModelResult, ModelStatus } from "../types";

const POLL_INTERVAL_MS = 1500;

interface UseJobPollingResult {
  status: ModelStatus;
  result: ModelResult | null;
  error: string | null;
  run: () => Promise<void>;
}

/** POSTs a model run, then polls GET /api/jobs/:id until it settles, exposing
 * live status/result/error to the component. */
export function useJobPolling(modelKey: string): UseJobPollingResult {
  const [status, setStatus] = useState<ModelStatus>("idle");
  const [result, setResult] = useState<ModelResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    // Reset local state when switching between models.
    setStatus("idle");
    setResult(null);
    setError(null);
    clearTimer();

    api
      .getModelResult(modelKey)
      .then((existing) => {
        setResult(existing);
        setStatus("completed");
      })
      .catch(() => {
        // No prior result yet -- that's fine, stay idle.
      });

    return clearTimer;
  }, [modelKey, clearTimer]);

  const poll = useCallback(
    (jobId: string) => {
      api
        .getJob(jobId)
        .then((job) => {
          setStatus(job.status);
          if (job.status === "completed") {
            setResult(job.result);
          } else if (job.status === "failed") {
            setError(job.error ?? "Model run failed.");
          } else {
            timerRef.current = setTimeout(() => poll(jobId), POLL_INTERVAL_MS);
          }
        })
        .catch((err) => {
          setStatus("failed");
          setError(err instanceof Error ? err.message : "Failed to poll job status.");
        });
    },
    [],
  );

  const run = useCallback(async () => {
    setError(null);
    setStatus("queued");
    try {
      const job = await api.runModel(modelKey);
      setStatus(job.status);
      poll(job.job_id);
    } catch (err) {
      setStatus("failed");
      setError(err instanceof Error ? err.message : "Failed to start model run.");
    }
  }, [modelKey, poll]);

  useEffect(() => clearTimer, [clearTimer]);

  return { status, result, error, run };
}

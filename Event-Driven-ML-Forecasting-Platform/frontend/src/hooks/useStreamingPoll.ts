import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { WindowedFeatureEntry } from "../types";

const POLL_INTERVAL_MS = 3000;

interface UseStreamingPollResult {
  active: boolean;
  features: WindowedFeatureEntry[];
  error: string | null;
  loading: boolean;
}

/** Polls GET /api/streaming/windowed-features on an interval. Unlike
 * useJobPolling, there's nothing to "run" here -- the producer/consumer are
 * standalone processes started outside the dashboard, so this hook is purely
 * read-only, same shape as Sidebar's own model-list poll. */
export function useStreamingPoll(): UseStreamingPollResult {
  const [active, setActive] = useState(false);
  const [features, setFeatures] = useState<WindowedFeatureEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await api.streamingWindowedFeatures();
        if (cancelled) return;
        setActive(data.streaming_active);
        setFeatures(data.features);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to reach the streaming endpoint.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return { active, features, error, loading };
}

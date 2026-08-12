import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { CostSummaryResponse } from "../api/types";

const REFRESH_INTERVAL_MS = 60_000;

export function CostBanner() {
  const [summary, setSummary] = useState<CostSummaryResponse | null>(null);

  useEffect(() => {
    function load() {
      api.getCostSummary().then(setSummary).catch(console.error);
    }
    load();
    const interval = setInterval(load, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  if (!summary || summary.price_source_unavailable) {
    return null;
  }

  return (
    <div className="cost-banner">
      <span>
        Live estimated cost: <strong>${summary.total_one_time_usd.toFixed(4)}</strong> one-time ·{" "}
        <strong>${summary.total_recurring_usd_per_month.toFixed(2)}</strong>/month while models
        exist
      </span>
      <span>Run `make teardown` when done to stop recurring charges.</span>
    </div>
  );
}

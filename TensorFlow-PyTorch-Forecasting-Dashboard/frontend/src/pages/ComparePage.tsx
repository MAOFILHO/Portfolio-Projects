import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ForecastChart } from "../components/ForecastChart";
import type { ComparisonModelEntry, Point } from "../types";

const COLORS = ["#2e6fd9", "#ff8c00", "#1c8a4b", "#c62828", "#7b3fe4"];

export function ComparePage() {
  const [models, setModels] = useState<ComparisonModelEntry[]>([]);
  const [observed, setObserved] = useState<Point[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    Promise.all([api.getComparison(), api.observedTemperature()])
      .then(([comparison, obs]) => {
        setModels(comparison.models);
        setObserved(obs);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Compare All Models</h1>
        <button className="run-button secondary" onClick={load}>
          Refresh
        </button>
      </div>

      {loading && <div className="state-message">Loading comparison…</div>}

      {!loading && models.length === 0 && (
        <div className="state-message">
          No models have been run yet. Run at least one model from the sidebar
          to see it here.
        </div>
      )}

      {!loading && models.length > 0 && (
        <>
          <ForecastChart
            title="Observed vs. All Run Models"
            observedSince="2000-01-01"
            series={[
              { name: "Observed", data: observed, color: "#1b2430" },
              ...models.map((m, i) => ({
                name: m.display_name,
                data: m.forecast,
                color: COLORS[i % COLORS.length],
                dashed: true,
              })),
            ]}
          />

          <div className="section-title">Accuracy (RMSE on 2010-2012 test set)</div>
          <div className="card metrics-table-card">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Framework</th>
                  <th>MSE</th>
                  <th>RMSE</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.key}>
                    <td>{m.display_name}</td>
                    <td>{m.framework}</td>
                    <td>{m.metrics ? m.metrics.mse.toFixed(3) : "—"}</td>
                    <td>{m.metrics ? m.metrics.rmse.toFixed(3) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

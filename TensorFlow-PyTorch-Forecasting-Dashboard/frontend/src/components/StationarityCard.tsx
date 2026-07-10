import type { StationarityResponse, StationarityTestResult } from "../types";

function TestResult({ name, result }: { name: string; result: StationarityTestResult }) {
  return (
    <div className="card metric-card">
      <span className="label">{name}</span>
      <span
        className={`stationarity-badge ${result.is_stationary ? "stationary" : "non-stationary"}`}
      >
        {result.is_stationary ? "Stationary" : "Non-stationary"}
      </span>
      <span className="sub">
        p-value {result.p_value.toFixed(4)} &middot; statistic {result.test_statistic.toFixed(3)}
      </span>
    </div>
  );
}

export function StationarityCard({ stationarity }: { stationarity: StationarityResponse }) {
  return (
    <div className="card-grid">
      <TestResult name="Augmented Dickey-Fuller Test" result={stationarity.adf} />
      <TestResult name="KPSS Test" result={stationarity.kpss} />
    </div>
  );
}

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { ForecastChart } from "../components/ForecastChart";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import { useJobPolling } from "../hooks/useJobPolling";
import type { ModelInfo, Point } from "../types";

function HyperparamsTable({ hyperparams }: { hyperparams: Record<string, unknown> }) {
  return (
    <div className="card hyperparams-card">
      <div className="chart-title">Configuration</div>
      <dl className="hyperparams-list">
        {Object.entries(hyperparams).map(([key, value]) => (
          <div key={key} className="hyperparams-row">
            <dt>{key.replace(/_/g, " ")}</dt>
            <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function TrainingLossChart({ loss }: { loss: number[] }) {
  const data = loss.map((value, epoch) => ({ epoch: epoch + 1, loss: value }));
  return (
    <div className="card chart-card">
      <div className="chart-title">Training Loss</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--contoso-border)" />
          <XAxis dataKey="epoch" tick={{ fontSize: 11 }} label={{ value: "Epoch", position: "insideBottom", offset: -3, fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Line type="monotone" dataKey="loss" stroke="#2e6fd9" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ModelPage() {
  const { modelKey = "" } = useParams<{ modelKey: string }>();
  const { status, result, error, run } = useJobPolling(modelKey);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [observed, setObserved] = useState<Point[]>([]);

  useEffect(() => {
    api
      .listModels()
      .then((models) => setModelInfo(models.find((m) => m.key === modelKey) ?? null))
      .catch(() => setModelInfo(null));
    api.observedTemperature().then(setObserved).catch(() => setObserved([]));
  }, [modelKey]);

  const isBusy = status === "queued" || status === "running";

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{modelInfo?.display_name ?? modelKey}</h1>
          {modelInfo && <span className="framework-tag">{modelInfo.framework}</span>}
        </div>
        <div className="page-header-actions">
          <StatusBadge status={status} />
          <button className="run-button" onClick={run} disabled={isBusy}>
            {isBusy ? "Running…" : "Run Model"}
          </button>
        </div>
      </div>

      {modelInfo && <HyperparamsTable hyperparams={modelInfo.hyperparams} />}

      {error && <div className="state-message error">{error}</div>}

      {isBusy && !result && (
        <div className="state-message">
          Training / fitting in progress — this can take anywhere from a few
          seconds (SARIMAX) to a couple of minutes (ARIMA's full grid search,
          or an LSTM's training epochs).
        </div>
      )}

      {!result && !isBusy && !error && (
        <div className="state-message">
          This model hasn't been run yet in this session. Click "Run Model" to
          fit it live and see results below.
        </div>
      )}

      {result && (
        <>
          {result.metrics && (
            <div className="card-grid" style={{ marginTop: "1rem" }}>
              <MetricCard label="RMSE" rmse={result.metrics.rmse} mse={result.metrics.mse} />
            </div>
          )}

          <ForecastChart
            title={`Observed vs. ${modelInfo?.display_name ?? modelKey} Forecast`}
            observedSince="2000-01-01"
            series={[
              { name: "Observed", data: observed, color: "#1b2430" },
              { name: "Forecast", data: result.forecast, color: "#2e6fd9", dashed: true },
            ]}
          />

          {result.training_loss && result.training_loss.length > 0 && (
            <TrainingLossChart loss={result.training_loss} />
          )}
        </>
      )}
    </div>
  );
}

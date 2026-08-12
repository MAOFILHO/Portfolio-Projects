import { useEffect, useState } from "react";
import { useAgentRun } from "../api/useAgentRun";
import { api, type DatasetInfo } from "../api/client";
import ProgressLog from "../components/ProgressLog";
import TraceLog from "../components/TraceLog";

interface FineTuneResult {
  validation: {
    file_name: string;
    total_lines: number;
    valid_rows: number;
    errors: { line: number; message: string }[];
    is_valid: boolean;
    has_consistent_system_prompt: boolean;
  };
  blocked: boolean;
  cost_estimate?: { billed_tokens: number; estimated_usd: number; training_type: string; note: string };
  job?: { job_id: string; config: { base_model: string; suffix: string; hyperparameters: Record<string, number> } };
  status?: {
    status: string;
    progress_pct: number;
    is_terminal: boolean;
    // All null until the job has actually run enough steps to report them —
    // true for any freshly-submitted live job, not just a hypothetical edge
    // case (mock mode's fixture is always a completed run, which is why this
    // wasn't declared honestly before).
    metrics: {
      final_train_loss: number | null;
      final_train_mean_token_accuracy: number | null;
      trained_tokens: number | null;
      total_steps: number | null;
    };
  };
  deployment?: { deployment_name: string; deployment_type: string; hourly_cost_usd: number; auto_removed_after_hours: number };
}

export default function Demo2FineTune() {
  const { loading, elapsedSeconds, events, error, result, trace, blockedError, run } =
    useAgentRun<FineTuneResult>("finetune");
  const [uploadResult, setUploadResult] = useState<Record<string, unknown> | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);

  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState("");
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogValidation, setCatalogValidation] = useState<Record<string, unknown> | null>(null);
  const [catalogCost, setCatalogCost] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api
      .listDatasets()
      .then((res) => setDatasets(res.datasets))
      .catch(() => setDatasets([]));
  }, []);

  async function handleCatalogCheck() {
    if (!selectedDataset) return;
    setCatalogBusy(true);
    setCatalogValidation(null);
    setCatalogCost(null);
    try {
      const [validation, cost] = await Promise.all([
        api.validateDatasetById(selectedDataset),
        api.estimateCostForDataset(selectedDataset),
      ]);
      setCatalogValidation(validation);
      setCatalogCost(cost);
    } finally {
      setCatalogBusy(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadBusy(true);
    try {
      const res = await api.uploadDataset(file);
      setUploadResult(res);
    } catch {
      setUploadResult({ is_valid: false, errors: [{ line_number: 0, error: "upload failed" }] });
    } finally {
      setUploadBusy(false);
    }
  }

  return (
    <div>
      <div className="canvas-header">
        <h1>Workflow 2 — Supervised Fine-Tuning</h1>
        <p>
          Validates <code>travel-finetune-hotel.jsonl</code>, estimates cost before spending
          anything, submits the SFT job on gpt-4.1, monitors it to completion, and deploys on
          the $0/hr Developer tier.
        </p>
      </div>

      <div className="card">
        <h2>Try your own dataset</h2>
        <p className="card-sub">
          Schema violations are shown as a demonstrated feature, not an error — every row
          is validated with Pydantic v2.
        </p>
        <input type="file" accept=".jsonl" onChange={handleUpload} disabled={uploadBusy} />
        {uploadResult && (
          <div style={{ marginTop: 14 }}>
            <span className={`pill ${uploadResult.is_valid ? "pill-pass" : "pill-fail"}`}>
              {uploadResult.is_valid ? "Valid" : "Invalid"}
            </span>{" "}
            {String(uploadResult.valid_rows ?? "?")}/{String(uploadResult.total_lines ?? "?")} rows valid
            {Array.isArray(uploadResult.errors) && uploadResult.errors.length > 0 && (
              <ul>
                {(uploadResult.errors as { line_number: number; error: string }[]).map((err, i) => (
                  <li key={i}>
                    line {err.line_number}: {err.error}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Dataset catalog</h2>
        <p className="card-sub">
          {datasets.length} selectable datasets — the lab's own travel assistant, plus 7
          more converted from AWS Bedrock's Converse format into Azure's fine-tuning
          format (see <code>data/convert_bedrock_datasets.py</code>). Only the travel
          dataset has a real recorded Azure training run behind it; cost for the others
          is a ~4-chars/token heuristic estimate, shown as such below.
        </p>
        <div className="field">
          <label htmlFor="dataset-select">Dataset</label>
          <select
            id="dataset-select"
            value={selectedDataset}
            onChange={(e) => setSelectedDataset(e.target.value)}
          >
            <option value="">Select a dataset…</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label} — {d.domain}
              </option>
            ))}
          </select>
        </div>
        {selectedDataset && (
          <p className="card-sub">
            {datasets.find((d) => d.id === selectedDataset)?.description}
          </p>
        )}
        <button
          className="btn btn-secondary"
          onClick={handleCatalogCheck}
          disabled={!selectedDataset || catalogBusy}
        >
          {catalogBusy ? "Checking…" : "Validate & estimate cost"}
        </button>

        {catalogValidation && (
          <div style={{ marginTop: 14 }}>
            <span
              className={`pill ${catalogValidation.is_valid ? "pill-pass" : "pill-fail"}`}
            >
              {catalogValidation.is_valid ? "Valid" : "Invalid"}
            </span>{" "}
            {String(catalogValidation.valid_rows ?? "?")}/
            {String(catalogValidation.total_lines ?? "?")} rows ·{" "}
            {String(catalogValidation.size_bytes ?? "?")} bytes
            {catalogCost && (
              <p className="card-sub" style={{ marginTop: 8 }}>
                Estimated cost: <strong>${String(catalogCost.estimated_usd)}</strong> (
                {String(catalogCost.training_type)} tier) — {String(catalogCost.note)}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <button className="btn" onClick={run} disabled={loading}>
          {loading ? `Running orchestrator… ${elapsedSeconds}s` : "▶ Run Workflow 2"}
        </button>
        {error && <div className="error-box" style={{ marginTop: 14 }}>{error}</div>}
        {blockedError && (
          <div className="error-box" style={{ marginTop: 14 }}>
            Blocked: {blockedError}
          </div>
        )}
      </div>

      {loading && <ProgressLog events={events} />}

      {/* A job that failed before producing a full result (e.g. a raised
          exception mid-run, rather than a graceful {error: ...} return) can
          leave `result` as a truthy-but-partial object with no `validation`
          key — guard on that explicitly rather than assuming any truthy
          result has the full expected shape. */}
      {result && result.validation && (
        <>
          <div className="card">
            <h2>1. Validation</h2>
            <p className="card-sub">
              <span className={`pill ${result.validation.is_valid ? "pill-pass" : "pill-fail"}`}>
                {result.validation.is_valid ? "Valid" : "Invalid"}
              </span>{" "}
              {result.validation.valid_rows}/{result.validation.total_lines} rows ·{" "}
              {result.validation.file_name} ·{" "}
              {result.validation.has_consistent_system_prompt
                ? "consistent system prompt across all rows"
                : "system prompt varies across rows"}
            </p>
          </div>

          {result.cost_estimate && (
            <div className="card">
              <h2>2. Cost estimate (before spending anything)</h2>
              <p className="card-sub">
                <strong>${result.cost_estimate.estimated_usd}</strong> for{" "}
                {result.cost_estimate.billed_tokens.toLocaleString()} billed tokens on{" "}
                {result.cost_estimate.training_type} tier.
              </p>
              <p className="card-sub">{result.cost_estimate.note}</p>
            </div>
          )}

          {result.job && (
            <div className="card">
              <h2>3. Job configuration</h2>
              <table>
                <tbody>
                  <tr>
                    <td>Base model</td>
                    <td>{result.job.config.base_model}</td>
                  </tr>
                  <tr>
                    <td>Suffix</td>
                    <td>{result.job.config.suffix}</td>
                  </tr>
                  {Object.entries(result.job.config.hyperparameters).map(([k, v]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td>{v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.status && (
            <div className="card">
              <h2>4. Job progress</h2>
              <p className="card-sub">
                <span className="pill pill-neutral">{result.status.status}</span>{" "}
                {result.status.progress_pct}% · step {result.status.metrics.total_steps ?? "—"} ·
                final train loss {result.status.metrics.final_train_loss ?? "—"} · token
                accuracy {result.status.metrics.final_train_mean_token_accuracy ?? "—"} ·{" "}
                {result.status.metrics.trained_tokens?.toLocaleString() ?? "0"} tokens trained
                {!result.status.is_terminal && " (still running — metrics fill in as training progresses)"}
              </p>
            </div>
          )}

          {result.deployment && (
            <div className="card">
              <h2>5. Deployment</h2>
              <p className="card-sub">
                <strong>{result.deployment.deployment_name}</strong>
              </p>
              <p className="card-sub">
                {result.deployment.deployment_type} tier · ${result.deployment.hourly_cost_usd}/hr
                · auto-removed after {result.deployment.auto_removed_after_hours}h
              </p>
            </div>
          )}

          <TraceLog trace={trace} />
        </>
      )}
    </div>
  );
}

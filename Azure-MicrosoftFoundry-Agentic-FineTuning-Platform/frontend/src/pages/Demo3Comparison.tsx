import { useAgentRun } from "../api/useAgentRun";
import ProgressLog from "../components/ProgressLog";
import TraceLog from "../components/TraceLog";

interface Check {
  name: string;
  description: string;
  verdict: "pass" | "fail";
  evidence: string;
}

interface Side {
  model_name: string;
  response: string;
  checks: Check[];
  passed: number;
  total: number;
  score_display: string;
}

interface PromptComparison {
  prompt: string;
  baseline: Side;
  fine_tuned: Side;
}

interface ComparisonResult {
  report: {
    baseline_model: string;
    fine_tuned_model: string;
    comparisons: PromptComparison[];
    baseline_total: number;
    fine_tuned_total: number;
    max_total: number;
    summary?: string;
  };
}

function SideCard({ label, side }: { label: string; side: Side }) {
  return (
    <div>
      <h3>
        {label} — {side.model_name}
      </h3>
      <p style={{ fontSize: "0.9rem" }}>{side.response}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {side.checks.map((check) => (
          <div key={check.name}>
            <span className={`pill ${check.verdict === "pass" ? "pill-pass" : "pill-fail"}`}>
              {check.verdict === "pass" ? "✓" : "✗"} {check.name.replace(/_/g, " ")}
            </span>
          </div>
        ))}
      </div>
      <p className="card-sub" style={{ marginTop: 8 }}>
        {side.score_display} behavioural checks passed
      </p>
    </div>
  );
}

export default function Demo3Comparison() {
  const { loading, elapsedSeconds, events, error, result, trace, blockedError, run } =
    useAgentRun<ComparisonResult>("comparison");

  return (
    <div>
      <div className="canvas-header">
        <h1>Workflow 3 — Agentic Inference &amp; Comparison</h1>
        <p>
          Compares baseline gpt-4.1 against the fine-tuned travel assistant under an
          identical system prompt across five canonical travel prompts. Scored on
          behaviour — tone, no restricted recommendations, ends with a question — not
          string equality, since outputs are non-deterministic.
        </p>
      </div>

      <div className="card">
        <button className="btn" onClick={run} disabled={loading}>
          {loading ? `Running orchestrator… ${elapsedSeconds}s` : "▶ Run Workflow 3"}
        </button>
        {error && <div className="error-box" style={{ marginTop: 14 }}>{error}</div>}
        {blockedError && (
          <div className="error-box" style={{ marginTop: 14 }}>
            Run failed: {blockedError}
          </div>
        )}
      </div>

      {loading && <ProgressLog events={events} />}

      {/* Same guard as Demo1/Demo2: a mid-run exception can leave `result`
          truthy but empty, so check for a field that only exists on a
          genuinely completed run. */}
      {result && result.report && (
        <>
          <div className="card">
            <h2>Result</h2>
            <p className="card-sub">
              Fine-tuned <strong>{result.report.fine_tuned_total}</strong>/
              {result.report.max_total} vs baseline{" "}
              <strong>{result.report.baseline_total}</strong>/{result.report.max_total} on
              behavioural checks.
            </p>
          </div>

          {result.report.comparisons.map((c, i) => (
            <div className="card" key={i}>
              <h2>“{c.prompt}”</h2>
              <div className="grid-2">
                <SideCard label="Baseline" side={c.baseline} />
                <SideCard label="Fine-tuned" side={c.fine_tuned} />
              </div>
            </div>
          ))}

          <TraceLog trace={trace} />
        </>
      )}
    </div>
  );
}

import { useAgentRun } from "../api/useAgentRun";
import ProgressLog from "../components/ProgressLog";
import TraceLog from "../components/TraceLog";

interface LeaderboardRow {
  model_name: string;
  quality_index: number;
  safety_attack_success_rate: number;
  throughput_tps: number;
  benchmark_cost_usd: number;
}

interface Leaderboard {
  label: string;
  sublabel: string;
  rows: LeaderboardRow[];
  winner: string;
}

interface DiscoveryResult {
  catalog: { count: number; models: { name: string; version: string; provider: string; supports_fine_tuning: boolean }[] };
  leaderboards: Record<string, Leaderboard>;
  comparison?: { model_a?: string; model_b?: string };
  evaluation: {
    overall_score?: string;
    row_count: number;
    evaluators: { name: string; group: string; passed: number; total: number; display: string }[];
  };
}

const METRIC_ORDER = [
  "quality_index",
  "safety_attack_success_rate",
  "throughput_tps",
  "benchmark_cost_usd",
];

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function Demo1Discovery() {
  const { loading, elapsedSeconds, events, error, result, trace, blockedError, run } =
    useAgentRun<DiscoveryResult>("discovery");

  return (
    <div>
      <div className="canvas-header">
        <h1>Workflow 1 — Model Discovery &amp; Evaluation</h1>
        <p>
          Compares gpt-5.4 against gpt-5.4-mini across a four-axis leaderboard — quality,
          safety, throughput, and cost — then runs a 45-row synthetic evaluation across all
          16 quality, safety, business, and agent evaluators.
        </p>
      </div>

      <div className="card">
        <button className="btn" onClick={run} disabled={loading}>
          {loading ? `Running orchestrator… ${formatElapsed(elapsedSeconds)}` : "▶ Run Workflow 1"}
        </button>
        {loading && (
          <p className="card-sub" style={{ marginTop: 10, marginBottom: 0 }}>
            In live mode this runs ~700 sequential model calls (45 rows × 16 evaluators).
            Typically 10–30 minutes depending on Azure rate limits. It's safe to refresh this
            page, close the tab, or come back later — the run keeps going on the server and
            you'll be reconnected to it automatically.
          </p>
        )}
        {error && <div className="error-box" style={{ marginTop: 14 }}>{error}</div>}
        {blockedError && (
          <div className="error-box" style={{ marginTop: 14 }}>
            Run failed: {blockedError}
          </div>
        )}
      </div>

      {loading && <ProgressLog events={events} />}

      {/* A job that failed mid-run (raised exception rather than a graceful
          {error: ...} return) can leave `result` truthy but empty — guard on
          a field that's only present when the run actually completed. */}
      {result && result.catalog && (
        <>
          <div className="card">
            <h2>Model catalog</h2>
            <p className="card-sub">{result.catalog.count} models available.</p>
            <table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Version</th>
                  <th>Provider</th>
                  <th>Fine-tunable</th>
                </tr>
              </thead>
              <tbody>
                {result.catalog.models.map((m) => (
                  <tr key={m.name}>
                    <td>{m.name}</td>
                    <td>{m.version}</td>
                    <td>{m.provider}</td>
                    <td>{m.supports_fine_tuning ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Leaderboard</h2>
            <p className="card-sub">
              No single model wins every axis — that trade-off is the point.
            </p>
            {METRIC_ORDER.map((metric) => {
              const board = result.leaderboards[metric];
              if (!board) return null;
              return (
                <div key={metric}>
                  <h3>{board.label}</h3>
                  <table>
                    <thead>
                      <tr>
                        <th>Model</th>
                        <th>Quality</th>
                        <th>Safety (ASR)</th>
                        <th>Throughput</th>
                        <th>Cost ($)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {board.rows.map((row) => (
                        <tr
                          key={row.model_name}
                          className={row.model_name === board.winner ? "winner-row" : ""}
                        >
                          <td>
                            {row.model_name === board.winner ? "🏆 " : ""}
                            {row.model_name}
                          </td>
                          <td>{row.quality_index}</td>
                          <td>{row.safety_attack_success_rate}%</td>
                          <td>{row.throughput_tps} tok/s</td>
                          <td>${row.benchmark_cost_usd}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })}
          </div>

          <div className="card">
            <h2>Synthetic evaluation</h2>
            <p className="card-sub">
              Overall score: <strong>{result.evaluation.overall_score}</strong> across{" "}
              {result.evaluation.row_count} synthetic rows.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Evaluator</th>
                  <th>Group</th>
                  <th>Pass rate</th>
                </tr>
              </thead>
              <tbody>
                {result.evaluation.evaluators.map((ev) => (
                  <tr key={ev.name}>
                    <td>{ev.name}</td>
                    <td>{ev.group}</td>
                    <td>{ev.display}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <TraceLog trace={trace} />
        </>
      )}
    </div>
  );
}

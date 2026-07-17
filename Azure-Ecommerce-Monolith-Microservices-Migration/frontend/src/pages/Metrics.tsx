import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BenchmarkResult, metricsApi } from "../api/bffClient";

export default function Metrics() {
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    metricsApi
      .latest()
      .then(setResult)
      .catch(() => setError("No benchmark results yet — click \"Run Benchmark\" below."));
  }, []);

  async function runBenchmark() {
    setRunning(true);
    setError(null);
    try {
      const data = await metricsApi.run();
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setRunning(false);
    }
  }

  const hasMonolith = result?.measured.includes("monolith") ?? false;
  const hasMicroservices = result?.measured.includes("microservices") ?? false;

  const chartData =
    (hasMonolith ? result!.monolith : result?.microservices ?? []).map((m, i) => ({
      operation: m.operation,
      monolith_p95: hasMonolith ? result!.monolith[i]?.p95_ms : undefined,
      microservices_p95: hasMicroservices ? result!.microservices[i]?.p95_ms : undefined,
      monolith_rps: hasMonolith ? result!.monolith[i]?.throughput_rps : undefined,
      microservices_rps: hasMicroservices ? result!.microservices[i]?.throughput_rps : undefined,
    })) ?? [];

  return (
    <div className="grid" style={{ gap: "1.5rem" }}>
      <section className="card">
        <h1>Metrics: Before vs. After</h1>
        <p className="muted">
          Real, reproducible measurements from <code>scripts/benchmark.py</code> hitting equivalent
          operations against the monolith and the microservices stack — not fabricated numbers.
          Only whichever backend(s) are actually running get measured — nothing is filled in or
          assumed for a backend that isn't up.
        </p>
        <button className="btn" onClick={runBenchmark} disabled={running}>
          {running ? "Running benchmark…" : "Run Benchmark"}
        </button>
        {error && (
          <div className="card" style={{ borderColor: "var(--contoso-danger)", marginTop: "0.75rem" }}>
            <strong style={{ color: "var(--contoso-danger)" }}>This run failed.</strong>
            <p className="muted">{error}</p>
            {result && (
              <p className="muted">
                The chart below is still showing your <strong>last successful</strong> run (see the
                timestamp at the bottom) — not new data from this failed attempt.
              </p>
            )}
          </div>
        )}
      </section>

      {result && (
        <>
          {hasMonolith && !hasMicroservices && (
            <p className="muted">
              Only <strong>monolith</strong> metrics shown — the microservices weren't running when
              this benchmark ran. Migrate first (Migrate page), then re-run the benchmark to add a
              comparison.
            </p>
          )}
          {hasMicroservices && !hasMonolith && (
            <p className="muted">
              Only <strong>microservices</strong> metrics shown — the monolith wasn't running when
              this benchmark ran (likely already decommissioned by a completed migration).
            </p>
          )}

          <section className="card">
            <h2>p95 Latency (ms) — lower is better</h2>
            <div style={{ width: "100%", height: 300 }}>
              <ResponsiveContainer>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="operation" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  {hasMonolith && <Bar dataKey="monolith_p95" name="Monolith" fill="#0078d4" />}
                  {hasMicroservices && <Bar dataKey="microservices_p95" name="Microservices" fill="#107c10" />}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="card">
            <h2>Throughput (req/s) — higher is better</h2>
            <div style={{ width: "100%", height: 300 }}>
              <ResponsiveContainer>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="operation" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  {hasMonolith && <Bar dataKey="monolith_rps" name="Monolith" fill="#0078d4" />}
                  {hasMicroservices && <Bar dataKey="microservices_rps" name="Microservices" fill="#107c10" />}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <p className="muted">
            Data above generated at <strong>{new Date(result.generated_at).toLocaleString()}</strong>
          </p>
        </>
      )}
    </div>
  );
}

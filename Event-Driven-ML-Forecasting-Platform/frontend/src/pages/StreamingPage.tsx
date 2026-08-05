import { CodeBlock } from "../components/CodeBlock";
import { useStreamingPoll } from "../hooks/useStreamingPoll";
import type { WindowedFeatureEntry } from "../types";

const START_COMMANDS = `# from the repo root
docker compose up -d

# from backend/, in two separate terminals
python src/kafka_consumer.py
python src/kafka_producer.py --limit 2000   # quick smoke run; drop --limit for the full replay`;

function formatWindow(entry: WindowedFeatureEntry): string {
  const start = new Date(entry.window_start);
  const end = new Date(entry.window_end);
  return `${start.toLocaleTimeString()} – ${end.toLocaleTimeString()}`;
}

export function StreamingPage() {
  const { active, features, error, loading } = useStreamingPoll();

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Live Telemetry</h1>
      </div>

      <p className="learn-intro">
        Windowed per-city temperature stats computed by the PySpark Structured Streaming consumer
        (<code>src/kafka_consumer.py</code>) from events replayed onto Kafka by{" "}
        <code>src/kafka_producer.py</code>. This is a manually-started pipeline, not something the
        dashboard runs for you — see below.
      </p>

      {error && <div className="state-message error">{error}</div>}

      {!error && loading && <div className="state-message">Loading…</div>}

      {!error && !loading && !active && (
        <div className="card">
          <div className="section-title">Nothing streaming yet</div>
          <p className="learn-intro">Start the local Kafka broker, then the consumer, then the producer:</p>
          <CodeBlock label="Terminal" code={START_COMMANDS} />
          <p className="learn-intro">This page starts updating automatically once windowed features land.</p>
        </div>
      )}

      {!error && active && features.length === 0 && (
        <div className="state-message">Streaming is active — waiting for the first window to complete…</div>
      )}

      {!error && active && features.length > 0 && (
        <div className="card metrics-table-card">
          <div className="section-title">Latest windows ({features.length})</div>
          <table className="metrics-table">
            <thead>
              <tr>
                <th>City</th>
                <th>Window</th>
                <th>Avg °C</th>
                <th>Min °C</th>
                <th>Max °C</th>
                <th>Events</th>
              </tr>
            </thead>
            <tbody>
              {features.map((entry) => (
                <tr key={`${entry.city}-${entry.window_start}`}>
                  <td>{entry.city}</td>
                  <td>{formatWindow(entry)}</td>
                  <td>{entry.avg_temperature.toFixed(2)}</td>
                  <td>{entry.min_temperature.toFixed(2)}</td>
                  <td>{entry.max_temperature.toFixed(2)}</td>
                  <td>{entry.event_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

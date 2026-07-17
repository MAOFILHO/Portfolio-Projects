import { useEffect, useRef, useState } from "react";
import { MigrationSnapshot, migrationApi } from "../api/bffClient";
import ArchitectureDiagram from "../components/ArchitectureDiagram";

export default function Migrate() {
  const [snapshot, setSnapshot] = useState<MigrationSnapshot | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [mode, setMode] = useState<"local" | "azure">("local");
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    migrationApi.status().then((data) => {
      setSnapshot(data);
      setMode(data.mode);
    }).catch(() => {});
    return () => eventSourceRef.current?.close();
  }, []);

  function appendLogFromSnapshot(data: MigrationSnapshot) {
    setLogs((prev) => {
      const next = [...prev];
      for (const step of data.steps) {
        const line = `[${step.status}] ${step.title}`;
        if (next[next.length - 1] !== line) next.push(line);
      }
      return next.slice(-30);
    });
  }

  function connectStream() {
    eventSourceRef.current?.close();
    const es = new EventSource(migrationApi.streamUrl());
    es.addEventListener("state", (event) => {
      const data: MigrationSnapshot = JSON.parse((event as MessageEvent).data);
      setSnapshot(data);
      appendLogFromSnapshot(data);
    });
    es.addEventListener("complete", (event) => {
      const data: MigrationSnapshot = JSON.parse((event as MessageEvent).data);
      setSnapshot(data);
      appendLogFromSnapshot(data);
      es.close();
    });
    eventSourceRef.current = es;
  }

  async function startMigration() {
    setLogs((prev) => [...prev, `> Starting migration in ${mode} mode…`]);
    connectStream();
    await migrationApi.start(mode);
  }

  const [resetBusy, setResetBusy] = useState(false);
  const monolithDecommissioned =
    snapshot?.steps.find((s) => s.id === "decommission")?.status === "done";

  async function resetMigration() {
    eventSourceRef.current?.close();
    setResetBusy(true);
    // Reset always brings the monolith back up first (if a prior run
    // decommissioned it) before clearing step state — otherwise the UI
    // would say "monolith" is the active backend again while the process
    // is actually still dead. Log that explicitly when it applies, since
    // it can take a few seconds (a real health-check wait, in Azure mode a
    // real scale-up), not an instant no-op.
    if (monolithDecommissioned) setLogs((prev) => [...prev, "> Restarting the monolith…"]);
    try {
      const data = await migrationApi.reset();
      setSnapshot(data);
      setLogs(data.last_error ? [`> ${data.last_error}`] : []);
    } finally {
      setResetBusy(false);
    }
  }

  return (
    <div className="grid" style={{ gap: "1.5rem" }}>
      <section className="card">
        <h1>Migrate: Monolith → Microservices</h1>
        {snapshot?.mode === "azure" ? (
          <p className="muted">
            This deployment is running on <strong>Azure Container Apps</strong>. Clicking Start
            Migration creates the user-service, product-service, and order-service Container Apps
            for real, one at a time — they don't exist yet — then scales the monolith down to zero
            replicas once all three are live and healthy.
          </p>
        ) : (
          <p className="muted">
            This runs a real strangler-fig cutover — in <strong>local</strong> mode it actually starts
            the user-/product-/order-service Python processes and stops the monolith process as each
            step completes, polling real <code>/health</code> endpoints. In <strong>azure</strong> mode
            (after <code>make provision</code>) it creates real Azure Container Apps for each service.
          </p>
        )}
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
          {snapshot?.mode !== "azure" && (
            <select value={mode} onChange={(e) => setMode(e.target.value as "local" | "azure")} className="btn secondary">
              <option value="local">Local processes</option>
              <option value="azure">Azure Container Apps</option>
            </select>
          )}
          <button className="btn" disabled={snapshot?.running} onClick={startMigration}>
            Start Migration
          </button>
          <button className="btn secondary" disabled={snapshot?.running || resetBusy} onClick={resetMigration}>
            {resetBusy ? "Resetting…" : "Reset"}
          </button>
        </div>
        {monolithDecommissioned && (
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            The monolith process was stopped by the decommission step. Shop's "Monolith" option is
            disabled until you restart it here.
          </p>
        )}
      </section>

      {snapshot && (
        <section className="card" style={{ overflowX: "auto" }}>
          <h2>Architecture — live</h2>
          <p className="muted" style={{ fontSize: "0.85rem", marginBottom: "0.5rem" }}>
            Reflects real state, not a canned animation — each box lights up the moment that
            service actually comes online (or, in Azure mode, the moment its Container App is
            created and healthy).
          </p>
          <ArchitectureDiagram snapshot={snapshot} />
        </section>
      )}

      {snapshot && (
        <section className="card">
          <h2>Timeline</h2>
          <ul className="timeline">
            {snapshot.steps.map((step) => (
              <li key={step.id}>
                <div>
                  <strong>{step.title}</strong>
                  <div className="muted" style={{ fontSize: "0.85rem" }}>
                    {step.description}
                  </div>
                </div>
                <span className={`pill ${step.status}`}>{step.status}</span>
              </li>
            ))}
          </ul>
          <p className="muted" style={{ marginTop: "1rem" }}>
            Active backend: <strong>{snapshot.active_backend}</strong>
          </p>
          {snapshot.last_error && (
            <p style={{ color: "var(--contoso-danger)" }}>{snapshot.last_error}</p>
          )}
        </section>
      )}

      {logs.length > 0 && (
        <section className="card">
          <h2>Live Log</h2>
          <div className="log-box">{logs.join("\n")}</div>
        </section>
      )}
    </div>
  );
}

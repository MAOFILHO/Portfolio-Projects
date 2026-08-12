import type { View } from "../components/Sidebar";
import type { HealthResponse } from "../api/client";

interface HomeProps {
  health: HealthResponse | null;
  onNavigate: (view: View) => void;
}

export default function Home({ health, onNavigate }: HomeProps) {
  return (
    <div>
      <div className="canvas-header">
        <h1>Azure Foundry Agentic Fine-Tuning Platform</h1>
        <p>
          A LangGraph orchestrator over Model Context Protocol tools that automates two
          Microsoft Foundry hands-on labs — model discovery/evaluation and supervised
          fine-tuning — end to end, with zero portal clicks.
        </p>
      </div>

      {health && (
        <div className="card">
          <h2>System status</h2>
          <p className="card-sub">
            <span className={`badge ${health.demo_mode === "mock" ? "badge-mock" : "badge-live"}`}>
              {health.demo_mode === "mock" ? "MOCK · $0 cost" : "LIVE · billing active"}
            </span>{" "}
            region {health.region} · v{health.version} · {health.billing}
          </p>
        </div>
      )}

      <div className="card">
        <h2>Three workflows</h2>
        <p className="card-sub">Each workflow runs the full LangGraph orchestrator → MCP tools → Azure Foundry pipeline.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <button className="btn btn-secondary" onClick={() => onNavigate("discovery")}>
            🔎 Workflow 1 — Model Discovery &amp; Evaluation
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate("finetune")}>
            🛠️ Workflow 2 — Supervised Fine-Tuning
          </button>
          <button className="btn btn-secondary" onClick={() => onNavigate("comparison")}>
            ⚖️ Workflow 3 — Agentic Inference &amp; Comparison
          </button>
        </div>
      </div>
    </div>
  );
}

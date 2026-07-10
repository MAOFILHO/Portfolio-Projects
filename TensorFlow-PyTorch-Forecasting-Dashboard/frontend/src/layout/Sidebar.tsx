import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api/client";
import type { ModelInfo, ModelStatus } from "../types";

const STATUS_DOT: Record<ModelStatus, string> = {
  idle: "dot-idle",
  queued: "dot-running",
  running: "dot-running",
  completed: "dot-completed",
  failed: "dot-failed",
};

export function Sidebar() {
  const [models, setModels] = useState<ModelInfo[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await api.listModels();
        if (!cancelled) setModels(data);
      } catch {
        // Backend not reachable yet -- the pages themselves surface the error.
      }
    }

    load();
    const hasActiveJob = models.some((m) => m.status === "queued" || m.status === "running");
    const interval = setInterval(load, hasActiveJob ? 2000 : 8000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [models.map((m) => m.status).join(",")]);

  return (
    <nav className="sidebar">
      <div className="sidebar-section-label">Models</div>
      <ul className="sidebar-list">
        {models.map((model) => (
          <li key={model.key}>
            <NavLink
              to={`/models/${model.key}`}
              className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}
            >
              <span className={`status-dot ${STATUS_DOT[model.status]}`} />
              <span className="sidebar-link-text">{model.display_name}</span>
            </NavLink>
          </li>
        ))}
        {models.length === 0 && <li className="sidebar-empty">Loading models…</li>}
      </ul>

      <div className="sidebar-section-label">Analysis</div>
      <ul className="sidebar-list">
        <li>
          <NavLink to="/compare" className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}>
            Compare All
          </NavLink>
        </li>
        <li>
          <NavLink to="/eda" className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}>
            Data &amp; EDA
          </NavLink>
        </li>
      </ul>

      <div className="sidebar-section-label">Learn</div>
      <ul className="sidebar-list">
        <li>
          <NavLink to="/learn" className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}>
            PyTorch vs TensorFlow
          </NavLink>
        </li>
      </ul>
    </nav>
  );
}

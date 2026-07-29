import { useEffect, useState } from "react";
import { fetchAgentActivity, type AgentActivityEntry } from "../api/client";

const REFRESH_INTERVAL_MS = 15_000;

// Parses "[AGENT] AgentName | phase | key=val key=val" lines emitted by
// shared/surveil_core/agents/activity_log.py -- falls back to showing the
// raw message if a line doesn't match (defensive, not expected in practice).
const LINE_PATTERN = /^\[AGENT\]\s+(\S+)\s+\|\s+(\S+)\s+\|\s+(.*)$/;

function parseLine(message: string): { agent: string; phase: string; detail: string } | null {
  const match = LINE_PATTERN.exec(message);
  if (!match) return null;
  return { agent: match[1], phase: match[2], detail: match[3] };
}

function phaseClass(phase: string): string {
  if (phase === "error") return "agent-phase-error";
  if (phase === "invoke" || phase === "tool_call") return "agent-phase-invoke";
  if (phase === "result" || phase === "tool_result") return "agent-phase-result";
  return "agent-phase-decision";
}

export function AgentActivityPage() {
  const [entries, setEntries] = useState<AgentActivityEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await fetchAgentActivity(24, 200);
        if (!cancelled) {
          setEntries(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load agent activity");
      }
    }

    load();
    const id = setInterval(load, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="panel">
      <h3>AI Agents Activity</h3>
      <p className="capture-hint">
        Live log of every agent invocation, tool call, and orchestration decision -- the Triage and
        Notification Policy agents (Azure Function, during frame analysis) and the NL Event Query and
        Observability Monitoring agents (this backend), all built on the Semantic Kernel SDK against Azure
        OpenAI. Sourced from the same Application Insights instance as the Observability page.
      </p>
      {error && <p className="error-text">{error}</p>}
      {entries.length === 0 ? (
        <p className="empty-state">No agent activity in the last 24 hours.</p>
      ) : (
        <div className="agent-log">
          {entries.map((entry, i) => {
            const parsed = parseLine(entry.message);
            return (
              <div key={i} className="agent-log-line">
                <span className="agent-log-time">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                {parsed ? (
                  <>
                    <span className="agent-log-name">{parsed.agent}</span>
                    <span className={`agent-log-phase ${phaseClass(parsed.phase)}`}>{parsed.phase}</span>
                    <span className="agent-log-detail">{parsed.detail}</span>
                  </>
                ) : (
                  <span className="agent-log-detail">{entry.message}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

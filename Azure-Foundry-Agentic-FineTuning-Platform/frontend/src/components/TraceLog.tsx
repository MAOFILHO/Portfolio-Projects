interface TraceLogProps {
  trace: string[];
}

export default function TraceLog({ trace }: TraceLogProps) {
  if (trace.length === 0) return null;
  return (
    <div className="card">
      <h2>Agent trace</h2>
      <p className="card-sub">MCP tool calls made by the LangGraph sub-agent, in order.</p>
      <div className="trace-log">{trace.map((line) => `· ${line}`).join("\n")}</div>
    </div>
  );
}

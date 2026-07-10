export function CodeBlock({ code, label }: { code: string; label: string }) {
  return (
    <div className="code-panel">
      <div className="code-panel-label">{label}</div>
      <pre className="code-block">
        <code>{code.trim()}</code>
      </pre>
    </div>
  );
}

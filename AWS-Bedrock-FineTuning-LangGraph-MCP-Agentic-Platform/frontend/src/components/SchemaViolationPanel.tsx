import type { SchemaViolation } from "../api/types";

interface SchemaViolationPanelProps {
  violation: SchemaViolation;
}

export function SchemaViolationPanel({ violation }: SchemaViolationPanelProps) {
  return (
    <div className="schema-violation-panel">
      <h4>Schema violation caught</h4>
      <p>
        The model's raw output didn't match the scenario's expected schema — the platform caught
        it and surfaced it here instead of silently accepting bad data.
      </p>
      <p>
        <strong>Raw text:</strong> <code>{violation.raw_text}</code>
      </p>
      <p>
        <strong>Error:</strong> <code>{violation.error_path}</code>
      </p>
      <details>
        <summary>Expected schema</summary>
        <pre>{violation.expected_schema}</pre>
      </details>
    </div>
  );
}

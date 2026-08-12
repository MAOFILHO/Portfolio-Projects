import type { InferCompareResponse } from "../api/types";
import { SchemaViolationPanel } from "./SchemaViolationPanel";

interface ComparePaneProps {
  result: InferCompareResponse;
}

export function ComparePane({ result }: ComparePaneProps) {
  return (
    <div>
      <div className="compare-pane">
        <div className="compare-card">
          <h4>Base foundation model</h4>
          <p>{result.base.text}</p>
          <div className="compare-meta">
            {result.base.latency_ms}ms · {result.base.input_tokens} in /{" "}
            {result.base.output_tokens} out
          </div>
        </div>

        <div className="compare-card">
          <h4>
            Fine-tuned model{" "}
            {result.schema_valid !== null && (
              <span className="schema-valid-badge">
                {result.schema_valid ? "Schema valid" : "Schema violation"}
              </span>
            )}
          </h4>
          <p>{result.tuned.text}</p>
          <div className="compare-meta">
            {result.tuned.latency_ms}ms · {result.tuned.input_tokens} in /{" "}
            {result.tuned.output_tokens} out
          </div>
        </div>
      </div>

      {result.violation && <SchemaViolationPanel violation={result.violation} />}
    </div>
  );
}

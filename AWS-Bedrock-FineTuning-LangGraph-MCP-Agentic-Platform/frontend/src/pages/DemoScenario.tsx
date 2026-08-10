import { useEffect, useState } from "react";

import { api } from "../api/client";
import type {
  DatasetInfo,
  FinetuneStatusEvent,
  InferCompareResponse,
  ScenarioDetail,
} from "../api/types";
import { ComparePane } from "../components/ComparePane";
import { JobStatusPanel } from "../components/JobStatusPanel";
import { PhaseRail } from "../components/PhaseRail";

interface DemoScenarioProps {
  scenarioId: string;
}

export function DemoScenario({ scenarioId }: DemoScenarioProps) {
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [scenario, setScenario] = useState<ScenarioDetail | null>(null);
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);

  const [approvalToken, setApprovalToken] = useState("");
  const [jobArn, setJobArn] = useState<string | null>(null);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const [statusLog, setStatusLog] = useState<FinetuneStatusEvent[]>([]);
  const [outputModelArn, setOutputModelArn] = useState<string | null>(null);

  const [customModelArn, setCustomModelArn] = useState("");
  const [deploymentArn, setDeploymentArn] = useState<string | null>(null);
  const [deployError, setDeployError] = useState<string | null>(null);

  const [prompt, setPrompt] = useState("");
  const [inferResult, setInferResult] = useState<InferCompareResponse | null>(null);
  const [inferError, setInferError] = useState<string | null>(null);

  useEffect(() => {
    setPhaseIndex(0);
    setScenario(null);
    setDataset(null);
    setJobArn(null);
    setStatusLog([]);
    setOutputModelArn(null);
    setDeploymentArn(null);
    setInferResult(null);

    api.getScenario(scenarioId).then((s) => {
      setScenario(s);
      setPrompt(s.sample_prompts[0] ?? "");
    });
  }, [scenarioId]);

  function loadDataset() {
    api
      .getDataset(scenarioId)
      .then(setDataset)
      .then(() => setPhaseIndex(1));
  }

  function launchFinetune() {
    setLaunchError(null);
    api
      .launchFinetune(scenarioId, {
        approval_token: approvalToken,
        force_retrain: false,
        training_data_s3_key: `training-data/${scenarioId}/train.jsonl`,
        validation_data_s3_key: `validation-data/${scenarioId}/validation.jsonl`,
      })
      .then((res) => {
        setJobArn(res.job_arn);
        setPhaseIndex(3);
        startStatusStream();
      })
      .catch((err: Error) => setLaunchError(err.message));
  }

  function startStatusStream() {
    const source = api.streamFinetuneStatus(scenarioId);
    source.onmessage = (event) => {
      const parsed: FinetuneStatusEvent = JSON.parse(event.data);
      setStatusLog((log) => [...log, parsed]);
      if (parsed.status === "Completed" && parsed.output_model_arn) {
        setOutputModelArn(parsed.output_model_arn);
        setCustomModelArn(parsed.output_model_arn);
        source.close();
      }
      if (parsed.status === "Failed" || parsed.status === "Stopped") {
        source.close();
      }
    };
  }

  function createDeployment() {
    setDeployError(null);
    api
      .deploy(scenarioId, { custom_model_arn: customModelArn })
      .then((res) => {
        setDeploymentArn(res.deployment_arn);
        setPhaseIndex(4);
      })
      .catch((err: Error) => setDeployError(err.message));
  }

  function runInference() {
    if (!deploymentArn) return;
    setInferError(null);
    api
      .infer(scenarioId, { prompt, deployment_arn: deploymentArn })
      .then((res) => {
        setInferResult(res);
        setPhaseIndex(5);
      })
      .catch((err: Error) => setInferError(err.message));
  }

  if (!scenario) {
    return <p>Loading scenario…</p>;
  }

  return (
    <div>
      <h2>{scenario.display_name}</h2>
      <p>{scenario.tagline}</p>

      <PhaseRail currentIndex={phaseIndex} />

      {phaseIndex === 0 && (
        <section>
          <h3>Foundation model</h3>
          <p>
            <strong>Model:</strong> <code>{scenario.base_model_id}</code>
          </p>
          <p>
            <strong>Epochs:</strong> {scenario.epochs}
          </p>
          <p>
            <strong>System prompt:</strong> {scenario.system_prompt}
          </p>
          <button onClick={loadDataset}>Continue to dataset →</button>
        </section>
      )}

      {phaseIndex === 1 && dataset && (
        <section>
          <h3>Dataset</h3>
          <p>
            {dataset.record_count} records in <code>{dataset.dataset_path}</code>
          </p>
          <pre>{JSON.stringify(dataset.preview_records, null, 2)}</pre>
          <button onClick={() => setPhaseIndex(2)}>Continue to fine-tune →</button>
        </section>
      )}

      {phaseIndex === 2 && (
        <section>
          <h3>Launch fine-tune</h3>
          <p>This calls the real Bedrock CreateModelCustomizationJob API. Type APPROVE to enable the button.</p>
          <input
            value={approvalToken}
            onChange={(e) => setApprovalToken(e.target.value)}
            placeholder="Type APPROVE"
          />
          <button onClick={launchFinetune} disabled={approvalToken !== "APPROVE"}>
            Launch fine-tune job
          </button>
          {launchError && <p className="field-error">{launchError}</p>}
          <p>
            Already launched this job from the CLI?{" "}
            <a
              className="link-action"
              onClick={() => { setPhaseIndex(3); startStatusStream(); }}
            >
              Skip to Job Status →
            </a>
          </p>
        </section>
      )}

      {phaseIndex === 3 && (
        <section>
          <h3>Job status</h3>
          <JobStatusPanel jobArn={jobArn} statusLog={statusLog} />
          {outputModelArn && (
            <>
              <p>
                Output model ARN: <code>{outputModelArn}</code>
              </p>
              <button onClick={() => setPhaseIndex(4)}>Continue to deployment →</button>
            </>
          )}
        </section>
      )}

      {phaseIndex === 4 && (
        <section>
          <h3>Deploy for inference</h3>
          <label>
            Custom model ARN
            <input
              value={customModelArn}
              onChange={(e) => setCustomModelArn(e.target.value)}
              style={{ width: "100%" }}
            />
          </label>
          <button onClick={createDeployment} disabled={!customModelArn}>
            Create deployment
          </button>
          {deployError && <p className="field-error">{deployError}</p>}
          {deploymentArn && (
            <p>
              Deployment ARN: <code>{deploymentArn}</code>
            </p>
          )}
        </section>
      )}

      {phaseIndex >= 5 || (phaseIndex === 4 && deploymentArn) ? (
        <section>
          <h3>Run inference</h3>
          <input value={prompt} onChange={(e) => setPrompt(e.target.value)} style={{ width: "100%" }} />
          <button onClick={runInference} disabled={!deploymentArn}>
            Compare base vs tuned
          </button>
          {inferError && <p className="field-error">{inferError}</p>}
          {inferResult && <ComparePane result={inferResult} />}
        </section>
      ) : null}
    </div>
  );
}

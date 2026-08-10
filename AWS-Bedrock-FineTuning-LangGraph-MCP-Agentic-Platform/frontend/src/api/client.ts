import type {
  CostSummaryResponse,
  DatasetInfo,
  DeployRequest,
  DeployResponse,
  DeploymentStatusResponse,
  FinetuneLaunchRequest,
  FinetuneLaunchResponse,
  InferCompareResponse,
  InferRequest,
  ScenarioDetail,
  ScenarioSummary,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === "string" ? body.detail : response.statusText;
    throw new Error(detail || `${init?.method ?? "GET"} ${path} failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listScenarios: () => request<ScenarioSummary[]>("/scenarios"),
  getScenario: (id: string) => request<ScenarioDetail>(`/scenarios/${id}`),
  getDataset: (id: string) => request<DatasetInfo>(`/dataset/${id}`),
  launchFinetune: (id: string, body: FinetuneLaunchRequest) =>
    request<FinetuneLaunchResponse>(`/finetune/${id}/launch`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  streamFinetuneStatus: (id: string) => new EventSource(`/finetune/${id}/status`),
  deploy: (id: string, body: DeployRequest) =>
    request<DeployResponse>(`/deploy/${id}`, { method: "POST", body: JSON.stringify(body) }),
  getDeploymentStatus: (scenarioId: string, deploymentArn: string) =>
    request<DeploymentStatusResponse>(
      `/deploy/${scenarioId}/status?deployment_arn=${encodeURIComponent(deploymentArn)}`,
    ),
  infer: (id: string, body: InferRequest) =>
    request<InferCompareResponse>(`/infer/${id}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getCostSummary: () => request<CostSummaryResponse>("/cost/summary"),
};

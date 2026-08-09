// Typed fetch wrapper for the FastAPI backend. In dev, Vite proxies /api -> :8000
// (see vite.config.ts); set VITE_API_BASE_URL to point elsewhere in prod.

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// Set by App.tsx once MSAL has a signed-in account (see auth/msalConfig.ts) —
// null in local/mock dev, where the backend has no Easy Auth in front of it
// and this is simply never called. A plain module-level hook rather than a
// React context because this module has no component tree of its own to sit
// in — it's imported directly by pages, not rendered.
let getAuthToken: (() => Promise<string | null>) | null = null;

export function setAuthTokenProvider(fn: (() => Promise<string | null>) | null): void {
  getAuthToken = fn;
}

async function authHeaders(): Promise<Record<string, string>> {
  if (!getAuthToken) return {};
  const token = await getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    ...init,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    const detail =
      typeof data?.detail === "string" ? data.detail : JSON.stringify(data);
    throw new ApiError(res.status, detail || res.statusText);
  }
  return data as T;
}

function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
}

// ---------------------------------------------------------------------------
// Health / auth
// ---------------------------------------------------------------------------
export interface HealthResponse {
  status: string;
  version: string;
  demo_mode: "mock" | "live";
  region: string;
  billing: string;
}

export interface DatasetInfo {
  id: string;
  label: string;
  domain: string;
  description: string;
  file_name: string;
  subdir: string;
  source: string;
}

export interface LoginResponse {
  authenticated: boolean;
  username: string;
  token: string;
  notice: string;
}

export const api = {
  health: () => get<HealthResponse>("/health"),
  mcpTools: () => get<{ count: number; servers: Record<string, unknown[]> }>("/mcp/tools"),

  login: (username: string, password: string) =>
    post<LoginResponse>("/auth/login", { username, password }),

  // ---- Workflow 1: catalog ----
  leaderboard: (metric: string) =>
    get<Record<string, unknown>>(`/catalog/leaderboard?metric=${metric}`),
  leaderboardAll: () => get<Record<string, unknown>>("/catalog/leaderboard/all"),
  modelCards: () => get<Record<string, unknown>[]>("/catalog/models"),
  compareModels: () => get<Record<string, unknown>>("/catalog/compare"),
  evaluate: () => post<Record<string, unknown>>("/catalog/evaluate", {}),
  evaluationResults: () => get<Record<string, unknown>>("/catalog/evaluate/results"),

  // ---- Workflow 2: fine-tune ----
  listDatasets: () => get<{ count: number; datasets: DatasetInfo[] }>("/finetune/datasets"),
  validateDataset: () => get<Record<string, unknown>>("/finetune/validate"),
  validateDatasetById: (datasetId: string) =>
    get<Record<string, unknown>>(`/finetune/validate?dataset_id=${encodeURIComponent(datasetId)}`),
  estimateCostForDataset: (datasetId: string) =>
    post<Record<string, unknown>>(`/finetune/estimate?dataset_id=${encodeURIComponent(datasetId)}`, {}),
  uploadDataset: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    // No Content-Type header here deliberately — the browser sets the
    // multipart boundary itself when the body is a FormData instance.
    const res = await fetch(`${BASE_URL}/finetune/validate/upload`, {
      method: "POST",
      headers: await authHeaders(),
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new ApiError(res.status, data?.detail ?? res.statusText);
    return data as Record<string, unknown>;
  },
  estimateCost: (billedTokens: number, epochs: number, trainingType: string) =>
    post<Record<string, unknown>>("/finetune/estimate", {
      billed_tokens: billedTokens,
      epochs,
      training_type: trainingType,
    }),
  createJob: () => post<Record<string, unknown>>("/finetune/jobs", {}),
  jobStatus: (jobId: string) => get<Record<string, unknown>>(`/finetune/jobs/${jobId}`),
  jobLogs: (jobId: string) => get<Record<string, unknown>>(`/finetune/jobs/${jobId}/logs`),
  deploy: () => post<Record<string, unknown>>("/finetune/deploy", {}),

  // ---- Workflow 3: inference ----
  canonicalPrompts: () => get<Record<string, unknown>>("/inference/prompts"),
  compareCompletions: () => post<Record<string, unknown>>("/inference/compare", {}),
  chat: (prompt: string, fineTuned: boolean) =>
    post<Record<string, unknown>>("/inference/chat", { prompt, fine_tuned: fineTuned }),

  // ---- Orchestrator ----
  invokeAgent: (demo: "discovery" | "finetune" | "comparison") =>
    post<{
      demo: string;
      route_reason?: string;
      error?: string;
      result: Record<string, unknown>;
      trace: string[];
    }>("/agent/invoke", { demo }),

  // Background-job variant: returns a job_id immediately, poll agentJobStatus.
  // Survives a page refresh (see src/app/jobs.py) — the run keeps going and
  // stays queryable server-side even if nobody is listening.
  startAgent: (demo: "discovery" | "finetune" | "comparison") =>
    post<AgentJobPayload>("/agent/invoke/start", { demo }),
  agentJobStatus: (jobId: string) => get<AgentJobPayload>(`/agent/jobs/${jobId}`),
};

export interface AgentJobPayload {
  job_id: string;
  demo: string;
  status: "running" | "succeeded" | "failed";
  elapsed_seconds: number;
  events: { ts: number; message: string }[];
  trace: string[];
  result: Record<string, unknown>;
  error: string | null;
}

import type {
  ComparisonResponse,
  HealthResponse,
  JobStatusResponse,
  ModelInfo,
  ModelResult,
  MovingAveragesResponse,
  Point,
  RunJobResponse,
  SeasonalDecompositionResponse,
  StationarityResponse,
  StreamingFeaturesResponse,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`Request to ${path} failed (${response.status}): ${detail}`);
  }
  return response.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string) => request<T>(path, { method: "POST" });

export const api = {
  health: () => get<HealthResponse>("/api/health"),
  listModels: () => get<ModelInfo[]>("/api/models"),
  runModel: (modelKey: string) => post<RunJobResponse>(`/api/models/${modelKey}/run`),
  getJob: (jobId: string) => get<JobStatusResponse>(`/api/jobs/${jobId}`),
  getModelResult: (modelKey: string) => get<ModelResult>(`/api/models/${modelKey}/result`),
  getComparison: () => get<ComparisonResponse>("/api/comparison"),
  observedTemperature: () => get<Point[]>("/api/temperature/observed"),
  movingAverages: () => get<MovingAveragesResponse>("/api/eda/moving-averages"),
  seasonalDecomposition: () => get<SeasonalDecompositionResponse>("/api/eda/seasonal-decomposition"),
  stationarity: () => get<StationarityResponse>("/api/eda/stationarity"),
  streamingWindowedFeatures: () => get<StreamingFeaturesResponse>("/api/streaming/windowed-features"),
};

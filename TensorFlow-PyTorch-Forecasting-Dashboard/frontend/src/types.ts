export interface Point {
  date: string;
  value: number;
}

export type ModelStatus = "idle" | "queued" | "running" | "completed" | "failed";

export interface ModelInfo {
  key: string;
  display_name: string;
  framework: string;
  hyperparams: Record<string, unknown>;
  has_result: boolean;
  metrics?: Record<string, number> | null;
  status: ModelStatus;
}

export interface ModelResult {
  forecast: Point[];
  confidence_interval_lower?: Point[] | null;
  confidence_interval_upper?: Point[] | null;
  order?: number[] | string | null;
  seasonal_order?: number[] | null;
  metrics?: Record<string, number> | null;
  training_loss?: number[] | null;
  auto_arima?: { order: number[]; seasonal_order: number[] };
}

export interface RunJobResponse {
  job_id: string;
  status: ModelStatus;
}

export interface JobStatusResponse {
  id: string;
  model_key: string;
  status: ModelStatus;
  result: ModelResult | null;
  error: string | null;
}

export interface ComparisonModelEntry {
  key: string;
  display_name: string;
  framework: string;
  forecast: Point[];
  metrics?: Record<string, number> | null;
}

export interface ComparisonResponse {
  models: ComparisonModelEntry[];
}

export interface MovingAveragesResponse {
  twelve_month: Point[];
  five_year: Point[];
}

export interface SeasonalDecompositionResponse {
  observed: Point[];
  trend: Point[];
  seasonal: Point[];
  residual: Point[];
}

export interface StationarityTestResult {
  test_statistic: number;
  p_value: number;
  lags_used: number;
  is_stationary: boolean;
  num_observations?: number | null;
  critical_values?: Record<string, number> | null;
}

export interface StationarityResponse {
  adf: StationarityTestResult;
  kpss: StationarityTestResult;
}

export interface HealthResponse {
  status: string;
}

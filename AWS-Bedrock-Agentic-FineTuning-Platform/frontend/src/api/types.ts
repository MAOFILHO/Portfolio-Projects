// Mirrors the Pydantic models in src/bedrock_platform/api — keep field names identical.

export interface HealthResponse {
  status: string;
}

export interface ScenarioSummary {
  id: string;
  display_name: string;
  tagline: string;
  industry: string;
}

export interface ScenarioDetail extends ScenarioSummary {
  system_prompt: string;
  output_mode: "prose" | "strict_json" | "numbered_steps" | "short_copy";
  sample_prompts: string[];
  epochs: number;
  base_model_id: string;
}

export interface TextBlock {
  text: string;
}

export interface ConversationMessage {
  role: string;
  content: TextBlock[];
}

export interface ConversationRecord {
  schemaVersion: string;
  system: TextBlock[];
  messages: ConversationMessage[];
}

export interface DatasetInfo {
  scenario_id: string;
  dataset_path: string;
  record_count: number;
  system_prompt: string;
  preview_records: ConversationRecord[];
}

export interface FinetuneLaunchRequest {
  approval_token: string;
  force_retrain: boolean;
  training_data_s3_key: string;
  validation_data_s3_key: string;
}

export interface FinetuneLaunchResponse {
  job_arn: string;
}

export interface FinetuneStatusEvent {
  status: string;
  output_model_arn: string | null;
  failure_message: string | null;
  creation_time: string | null;
  last_modified_time: string | null;
  job_name: string | null;
  job_arn: string | null;
  is_status_change: boolean;
  logged_at: string;
  validation_status: string | null;
  training_status: string | null;
}

export interface DeployRequest {
  custom_model_arn: string;
}

export interface DeployResponse {
  deployment_arn: string;
}

export interface DeploymentStatusResponse {
  status: string;
  failure_message: string | null;
}

export interface InferRequest {
  prompt: string;
  deployment_arn: string;
}

export interface InferenceResult {
  text: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
}

export interface SchemaViolation {
  raw_text: string;
  error_path: string;
  expected_schema: string;
}

export interface InferCompareResponse {
  base: InferenceResult;
  tuned: InferenceResult;
  schema_valid: boolean | null;
  violation: SchemaViolation | null;
}

export interface ScenarioCost {
  scenario_id: string;
  one_time_cost_usd: number;
  recurring_cost_usd_per_month: number;
}

export interface CostSummaryResponse {
  scenarios: ScenarioCost[];
  total_one_time_usd: number;
  total_recurring_usd_per_month: number;
  price_source_unavailable: boolean;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  authenticated: boolean;
  note: string;
}

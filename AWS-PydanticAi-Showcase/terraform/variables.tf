variable "aws_region" {
  description = "AWS region to deploy into. us-east-1 is typically the cheapest for Fargate on-demand pricing."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Used to name/tag every resource."
  type        = string
  default     = "pydantic-ai-showcase"
}

variable "container_port" {
  type    = number
  default = 8000
}

# Smallest Fargate task size available (0.25 vCPU / 0.5 GB) — the cheapest
# SKU that can run the app; bump this only if you see it OOM/throttle. Four
# demos share this one task, so watch memory first if anything needs to grow.
variable "fargate_cpu" {
  type    = number
  default = 256
}

variable "fargate_memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  description = "Number of running tasks. Set to 0 to stop billing for compute without destroying the stack."
  type        = number
  default     = 1
}

variable "openai_api_key" {
  description = "Stored in Secrets Manager, never in the task definition or state-visible plaintext output."
  type        = string
  sensitive   = true
}

variable "research_model" {
  description = "Used only by Research Analyst's web-research and report-writing steps, which benefit from a frontier model. Every other demo (and Research Analyst's own planning/evaluation) uses fast_model."
  type        = string
  default     = "openai:gpt-5.2"
}

variable "fast_model" {
  description = "The default model for every demo: short, structured tasks where a smaller/faster model is both sufficient and noticeably snappier for someone watching a live demo."
  type        = string
  default     = "openai:gpt-5-mini"
}

variable "max_revisions" {
  description = "Caps Research Analyst's evaluate/revise loop; each retry is a full synth+evaluate round trip and dominates worst-case latency."
  type        = number
  default     = 1
}

variable "log_retention_days" {
  description = "Short retention keeps CloudWatch Logs cost near zero for a demo deployment."
  type        = number
  default     = 7
}

variable "github_repository" {
  description = "\"owner/repo\", used to scope the GitHub Actions OIDC trust policy. Leave blank to skip creating the OIDC role."
  type        = string
  default     = ""
}

variable "demo_username" {
  description = "The single demo sign-in account's username. Not real authentication — see app/auth.py."
  type        = string
  default     = "demo@contoso.com"
}

variable "demo_password" {
  description = "The single demo sign-in account's password. Not real authentication — see app/auth.py."
  type        = string
  sensitive   = true
  default     = "contoso"
}

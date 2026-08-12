# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Public hosting**: Azure Container Apps (backend) + Azure Static Web Apps
  (frontend), gated by real Microsoft Entra ID sign-in with bearer-token
  validation done in-app (`src/app/auth_entra.py`) — not Container Apps'
  built-in Easy Auth, which has a confirmed platform bug blocking CORS
  preflight for this SPA + separate-origin-API shape. See
  [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) #12–15.
- **GitHub Actions CI/CD**: four workflows at the monorepo root
  (`ci`, `deploy`, `hosting-deploy`, `teardown`), OIDC auth (no stored Azure
  secret), a least-privilege custom role scoped to just this project's
  resources (`infra/foundry-deployer-role.json`).
- **Selectable fine-tuning dataset catalog** (`GET /finetune/datasets`): 7 new
  datasets (support ticket triage, pharma adverse-event triage, patient
  message triage, e-commerce product copy, IT helpdesk L1, banking assistant,
  gardening tutor) converted from AWS Bedrock's Converse JSONL format to
  Azure's flat fine-tuning `messages` format by
  `data/convert_bedrock_datasets.py`. All 7 pass `TrainingRecord` schema
  validation (1918 total rows, 0 skipped). The lab's own
  `travel-finetune-hotel.jsonl` remains the default and is unaffected —
  Demo 2's "Run Demo 2" orchestrated flow, Demo 3's canonical prompts, and all
  cost figures elsewhere in this project still key off it exclusively.
- New MCP tool `list_datasets` on `mcp-foundry-finetune` (19 tools total, up
  from 18); `validate_jsonl`, `upload_training_file`, and
  `estimate_training_cost` now accept an optional `dataset_id`.
- `estimate_training_cost` uses a ~4-chars/token heuristic for any dataset
  other than the travel one (clearly labelled as a heuristic in the
  response `note`), since only the travel dataset has a real recorded Azure
  training run to quote an exact billed-token count from.
- Demo 2 UI: a "Dataset catalog" card with a dropdown over all 8 datasets and
  a "Validate & estimate cost" action, separate from the orchestrated
  "Run Demo 2" button (which still runs the lab's own dataset end to end).

### Fixed
- `ci.yml`'s Terraform job ran `pytest` without ever installing dependencies
  first — added the missing `pip install -r requirements.txt`.
- Three real `ruff` line-length violations and one `ruff format` violation
  from the public-hosting work, never caught locally until CI's first
  actually-green run.
- Bumped `actions/checkout`, `actions/setup-node`, `actions/setup-python` to
  v7 and `hashicorp/setup-terraform` to v4 — resolves the Node.js 20
  deprecation warnings (GitHub forces Node 24 by June 2026, removes Node 20
  entirely in September 2026).

## [0.1.0] — 2026-08-05

### Added
- Initial release: automates two K21Academy Microsoft Foundry labs end to end.
- **Demo 1 — Model Discovery & Evaluation**: catalog browse, four-axis leaderboard
  (quality / safety / throughput / benchmark cost), trade-off scatter, and a
  45-row synthetic-dataset evaluation across 16 evaluators.
- **Demo 2 — Supervised Fine-Tuning**: JSONL validation, SFT job submission on
  `gpt-4.1-2025-04-14`, and live job monitoring with per-step train loss.
- **Demo 3 — Agentic Inference & Comparison**: baseline vs fine-tuned
  side-by-side over five canonical travel prompts, scored on behavioural
  assertions rather than string equality.
- LangGraph orchestrator supervising three sub-agents (Discovery, FineTune,
  Comparison) over three MCP servers.
- Terraform IaC for `eastus2` with budget alert provisioned before any billable
  resource, and auto-incrementing name suffixes.
- Dual-mode execution: `DEMO_MODE=mock` (default, $0, no Azure account) and
  `DEMO_MODE=live`.
- Five test suites: unit, pre-provision, post-provision, post-run, post-teardown.
- Contoso-themed React + TypeScript frontend.

### Notes
- Fine-tuned models deploy to **Developer Tier** ($0/hour, auto-removed after
  24 h) rather than Standard ($1.70/hour ≈ $1,224/month).

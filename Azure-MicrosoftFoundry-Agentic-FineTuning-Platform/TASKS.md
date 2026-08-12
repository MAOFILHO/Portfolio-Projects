# TASKS.md — executable build plan

**This file is written to be resumable by someone (or some model) who has never
seen the planning conversation.** Every task is self-contained. Every phase ends
in a gate: a literal command plus its expected output. Do not add scope beyond
what is written here.

Repo root = the directory containing this file.
Python entry points assume the venv at `.venv/`.

---

## Phase 0 — Environment  ✅

- [x] 0.1 Create folder tree.
- [x] 0.2 `python3 -m venv .venv`.
- [x] 0.3 Write `requirements.txt` with versions verified against PyPI.
- [x] 0.4 `pip install -r requirements.txt`.
- [x] 0.5 Download `data/travel-finetune-hotel.jsonl` from
      `https://microsoftlearning.github.io/mslearn-ai-studio/data/travel-finetune-hotel.jsonl`.
- [x] 0.6 Write `pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`,
      `PLAN.md`, `COSTS.md`, `CHANGELOG.md`.

**Gate:** `./.venv/bin/python -c "import fastapi,pydantic,langgraph,mcp,openai; print('ok')"`
→ prints `ok`.
**Gate:** `wc -c data/travel-finetune-hotel.jsonl` → `8576` bytes, 10 records.

---

## Phase 1 — Schemas and fixtures

- [ ] 1.1 `src/app/config.py` — `Settings(BaseSettings)` reading `.env`.
      Must expose `demo_mode`, `azure_location`, model names/versions, `ft_suffix`,
      `budget_ceiling_usd`, demo credentials. `is_mock` property.
- [ ] 1.2 `src/app/schemas/training.py` — `ChatMessage` (role literal
      `system|user|assistant`), `TrainingRecord` (exactly 3 messages in order
      system→user→assistant), `ValidationReport`.
- [ ] 1.3 `src/app/schemas/catalog.py` — `ModelCard`, `Benchmarks`
      (quality_index, safety_attack_success_rate, throughput_tps, benchmark_cost_usd),
      `LeaderboardRow`, `ModelComparison`.
- [ ] 1.4 `src/app/schemas/finetune.py` — `FineTuneJobConfig`, `FineTuneJob`,
      `JobStatus` enum (`queued|running|succeeded|failed|cancelled`), `JobLogEntry`,
      `Checkpoint`.
- [ ] 1.5 `src/app/schemas/evaluation.py` — `SyntheticRow` (id, query,
      sample_output_text, test_case_description), `EvaluatorResult`,
      `EvaluationRun`, `ClusterAnalysis`.
- [ ] 1.6 `src/app/schemas/comparison.py` — `PromptComparison`,
      `BehaviouralScore`.
- [ ] 1.7 `data/fixtures/*.json` — recorded fixtures using the exact values in
      `PLAN.md`: leaderboard rows, gpt-5.4 vs gpt-5.4-mini comparison
      (0.81/1.02/21/164.92 vs 0.67/0.00/142/45.81), a 45-row synthetic dataset,
      16 evaluator results, and a 100-step job log ending at loss 0.02.

**Gate:** `.venv/bin/pytest tests/unit/test_schemas.py -q` → all pass.
**Gate:** every fixture loads and validates:
`.venv/bin/python -m app.cli validate-fixtures` → `all fixtures valid`.

---

## Phase 2 — MCP servers

Each server uses `mcp.server.MCPServer` (MCP 2.0 API — note: `FastMCP` no longer
exists at `mcp.server.fastmcp`, and `Tool.input_schema` is snake_case).
Each tool must work identically in mock and live mode.

- [ ] 2.1 `mcp_servers/foundry_catalog/server.py` — tools `list_models`,
      `get_model_card`, `get_benchmarks`, `get_leaderboard`, `compare_models`.
- [ ] 2.2 `mcp_servers/foundry_finetune/server.py` — tools `upload_training_file`,
      `validate_jsonl`, `create_sft_job`, `get_job_status`, `get_job_logs`,
      `list_checkpoints`, `deploy_finetuned_model`.
- [ ] 2.3 `mcp_servers/foundry_inference/server.py` — tools `chat_completion`,
      `compare_completions`, `generate_synthetic_dataset`, `create_evaluation`,
      `get_evaluation_results`.
- [ ] 2.4 `src/app/mcp_clients/registry.py` — in-process registry that calls
      `MCPServer.call_tool(name, args)` and parses `content[0].text` as JSON
      (prefer `structured_content` when populated).

**Gate:** `make mcp-list` → lists **18** tools across 3 servers
(the 17 above plus `estimate_training_cost` on the fine-tune server).
**Gate:** `.venv/bin/pytest tests/unit/test_mcp_servers.py -q` → all pass.

---

## Phase 3 — Backend and agents

- [x] 3.1 `src/app/telemetry.py` — OTel tracer; console span exporter always on
      when `OTEL_CONSOLE_EXPORT=true`; Azure Monitor exporter when a connection
      string is present. **Wire this before pipeline logic.**
- [x] 3.2 `src/app/services/fixtures.py` — loads `data/fixtures/`.
- [x] 3.3 `src/app/services/azure_foundry.py` — live Azure adapter behind the
      same interface as `fixtures.py`.
- [x] 3.4 `src/app/services/comparison.py` — behavioural scoring: friendly tone,
      no hotel/flight/car/restaurant recommendation, ends with a question.
      **Not string equality** — the guide warns outputs are non-deterministic.
- [x] 3.5 `src/app/agents/state.py` — `AgentState` TypedDict.
- [x] 3.6 `src/app/agents/{discovery,finetune,comparison}_agent.py`.
- [x] 3.7 `src/app/agents/orchestrator.py` — LangGraph `StateGraph` with a
      supervisor node routing to one of the three sub-agents, then `END`.
- [x] 3.8 `src/app/routers/` — `catalog`, `finetune`, `inference`, `agent`,
      `auth`, `health`.
- [x] 3.9 `src/app/main.py` — FastAPI app, CORS, telemetry init, router mounting.
- [x] 3.10 `src/app/cli.py` — `run-all`, `mcp-list`, `validate-fixtures`, `sync-env`.

**Gate:** `DEMO_MODE=mock make run` → all three demos complete, exit 0, spans
printed to terminal. ✅ Verified 2026-08-05 — all 3 demos completed, exit 0.
**Gate:** `make api` then `curl -s localhost:8000/health` → `{"status":"ok",...}`.
✅ Verified 2026-08-05 — `/health`, `/mcp/tools` (19 tools as of the dataset-catalog
addition below; 18 at the time this gate first passed), `/catalog/leaderboard`,
`/finetune/validate` (10/10 valid), `/auth/login`, `/agent/invoke` all confirmed.

---

## Phase 4 — Terraform (eastus2)

Order matters: **the budget alert must be created before any billable resource.**

- [x] 4.1 `infra/terraform/versions.tf` — azurerm ~> 4.0, required_version >= 1.9.
- [x] 4.2 `infra/terraform/scripts/next_suffix.py` — `external` data source.
      Reads `.suffix.lock`; probes Azure; returns the **same** suffix if the
      existing resource carries `managed_by = foundry-agentic-platform`;
      otherwise advances `-v1 → -v2 → …`. Emits `{"suffix": "vN"}` on stdout.
- [x] 4.3 `infra/terraform/modules/budget/` — `azurerm_consumption_budget_resource_group`
      at `var.budget_ceiling_usd`, alerts at 50/80/100 %.
- [x] 4.4 `infra/terraform/modules/foundry/` — `azurerm_cognitive_account` (kind
      `AIServices`, S0) + `azurerm_ai_foundry_project`. (Switched from
      `azurerm_ai_services`, which validate flagged as deprecated in favor of
      `azurerm_cognitive_account`; the latter is what's actually used.)
- [x] 4.5 `infra/terraform/modules/model_deployment/` — reusable deployment module;
      SKU set **explicitly**, never left to a provider default.
- [x] 4.6 `infra/terraform/{main,variables,outputs,observability}.tf`.
- [x] 4.7 `infra/terraform/scripts/sweep_orphans.py` — finds and deletes every
      resource group tagged `managed_by = foundry-agentic-platform` at any suffix.

**Gate:** `terraform -chdir=infra/terraform init && terraform -chdir=infra/terraform validate`
→ `Success! The configuration is valid.` ✅ Verified 2026-08-05.
**Gate:** `terraform -chdir=infra/terraform fmt -check` → no diff. ✅ Verified 2026-08-05.
**Extra gate run:** `terraform plan` against the real subscription (read-only,
no `apply`) succeeded end-to-end — `Plan: 9 to add, 0 to change, 0 to destroy` —
which caught and fixed a real bug (`azurerm_cognitive_account.project_management_enabled`
requires a `SystemAssigned` identity block). No resources were created.

---

## Phase 5 — Frontend (built last, once the pipeline is stable)

- [x] 5.1 Vite + React 18 + TS scaffold; `package.json` pinned (React 18.3.1,
      Vite 5.4.21, TS 5.9.3 — verified live against npm on 2026-08-05).
- [x] 5.2 Contoso theme in `src/styles/theme.css` — light **and** dark
      (`prefers-color-scheme`).
- [x] 5.3 `Sidebar.tsx` — **fixed, 18 % width**, Contoso logo (inline SVG),
      Home, and 3 demo triggers that populate the main canvas.
- [x] 5.4 `Login.tsx` — static gate, `demo` / `demo123`.
      Label it clearly as a demo gate, not real authentication.
- [x] 5.5 `Demo1Discovery.tsx` — model catalog + 4-axis leaderboard tables
      (winner highlighted) + evaluation results. (Trade-off *scatter* was
      simplified to per-axis ranked tables with a 🏆 winner marker — same
      information, no charting dependency to keep the bundle CSP-clean.)
- [x] 5.6 `Demo2FineTune.tsx` — JSONL upload/validate (schema violations shown as
      a feature), job config, live progress, deployment summary.
- [x] 5.7 `Demo3Comparison.tsx` — side-by-side baseline vs fine-tuned, 5 preset
      prompts, behavioural check pills + score badges.
- [x] 5.8 `api/client.ts` — typed fetch wrapper + `useAgentRun` hook driving
      `POST /agent/invoke`.

**Gate:** `cd frontend && npm run build` → succeeds, no TS errors.
✅ Verified 2026-08-05 — `tsc -b && vite build` clean, 159 KB JS / 5.7 KB CSS bundle.
**Gate:** `npm run dev`, log in with demo/demo123, all three demos render.
✅ Verified 2026-08-05 via Playwright against a live `make api` backend — logged
in, ran all 3 demos end to end through the UI, confirmed rendered values match
the lab guides exactly (leaderboard winners, 98% (704/720) eval score, $0.016
cost estimate, 14/15 vs 4/15 behavioural comparison), zero console
errors/warnings.

---

## Phase 6 — Tests and CI/CD

- [x] 6.1 `tests/unit/` — schemas, comparison scoring, MCP tools, suffix logic,
      orchestrator, all API routers, and the dataset catalog added later. 78
      tests, 77% overall coverage (schemas/comparison ≥91–100%).
- [x] 6.2 `tests/smoke_pre/` — Python ≥3.12; `terraform`/`az` present;
      `terraform validate` (always runs); `az login`/region/live model+region
      availability/quota (gated behind `RUN_LIVE_SMOKE=1`, since those need a
      real Azure session).
- [x] 6.3 `tests/smoke_post_provision/` — every resource live **and asserted to be
      the approved SKU** (Developer for the FT deployment, GlobalStandard for base).
      Reads `terraform output -json` rather than hardcoding names (the
      auto-increment suffix makes names unpredictable). Gated behind
      `RUN_LIVE_SMOKE=1`.
- [x] 6.4 `tests/smoke_post_run/` — expected outputs (`outputs/{discovery,finetune,
      comparison}.json`) exist, are non-empty, valid JSON, and structurally sane.
      Runs in both mock and live mode (no Azure calls of its own).
- [x] 6.5 `tests/smoke_post_teardown/` — **zero** surviving tagged resources at any
      suffix. Failing this blocks release. Gated behind `RUN_LIVE_SMOKE=1`.
- [x] 6.6 `.github/workflows/ci.yml` — ruff lint + format check, fixture
      validation, unit tests w/ coverage, mock end-to-end (`app.cli run-all`),
      `/health` boot check, frontend build, Terraform validate/fmt (no
      credentials needed). Runs on every push/PR. **Never provisions.**
- [x] 6.7 `.github/workflows/deploy.yml` — `workflow_dispatch` with a typed
      confirmation guard; Azure OIDC login; smoke-pre → `terraform apply`
      (budget alert enforced before billable resources via `depends_on` in
      main.tf) → smoke-post-provision → live run → smoke-post-run → uploads
      outputs as a build artifact.
- [x] 6.8 `.github/workflows/teardown.yml` — `workflow_dispatch` + nightly
      cron (03:17 UTC); pre-sweep → `terraform destroy` → post-destroy sweep
      → smoke-post-teardown (release blocker).

**Gate:** `make test` → all unit tests pass. ✅ Verified 2026-08-05 — 78 passed.
**Gate:** `act -n` or a pushed branch → CI green on mock path. Workflow YAML
validated with `yaml.safe_load` (all 3 files parse); `ci.yml`'s steps were run
manually end-to-end locally (ruff check/format, fixture validation, unit
tests+coverage, `app.cli run-all`, `app.cli mcp-list`, API boot + `/health`,
frontend `npm run build`, `terraform init -backend=false && validate && fmt
-check`) and all passed — this is the same sequence CI runs.

---

## Phase 7 — Package and hand off

- [x] 7.1 `README.md` — business case, ASCII architecture diagram, prerequisites,
      quickstart, env-var table, cost table, teardown instructions, author block.
- [x] 7.2 `Dockerfile` + `frontend/Dockerfile` + `docker-compose.yml` — built and
      ran both containers, verified `/health` direct and via the nginx `/api`
      proxy, and the dataset-catalog endpoint, all through the running stack.
- [x] 7.3 Confirmed `.gitignore` covers `.env`, `.venv/`, `__pycache__/`, `*.py[cod]`
      (covers `*.pyc`), `.terraform/`, `*.tfstate*`, `.azure/`, `.suffix.lock`.
- [x] 7.4 `grep -rIn "sk-\|AZURE_FOUNDRY_API_KEY=." --exclude-dir=.venv .` → only
      false positives (the literal grep pattern in this file, and
      "it-**helpdesk-l1**" substring-matching "sk-"). No real secrets.
- [x] 7.5 Confirmed self-contained/renameable — the one path-like string found
      (`K21Academy`) is lab-name prose in a docstring, not a filesystem path.
- [x] 7.6 No resources are live — every verification in this build ran in
      `DEMO_MODE=mock` or as a read-only `terraform plan`/`validate`. Nothing
      to tear down.

**Gate:** `git init && git add . && git commit -m "..."` succeeds with no secrets.
✅ Verified 2026-08-05 — 138 files committed (`6f63e0e`), clean working tree,
no `.env`/`.venv`/`node_modules`/`.terraform`/`.tfstate`/`outputs` staged.

**Also found and fixed during this final pass:** `Makefile`'s `teardown` target
called `sweep_orphans.py --plan`/`--apply`, flags that don't exist on the
actual script (`--tag`/`--dry-run`) — fixed. `make run`/`make mcp-list`/`make api`
had no `PYTHONPATH=src`, so `python -m app.cli` failed with `ModuleNotFoundError`
outside of the manually-exported shell sessions used earlier in this build —
fixed by exporting `PYTHONPATH := src` once at the top of the Makefile.
`provision`/`smoke-pre`/`smoke-post-provision`/`smoke-post-teardown` targets
didn't set `RUN_LIVE_SMOKE=1`, so their live checks would have silently
skipped even when actually provisioning — fixed.

---

## Standing rules

1. **Never provision a resource not listed in `COSTS.md`.**
2. **Never overwrite `../CLAUDE.md`** — it is read-only project law.
3. Set every SKU explicitly; never accept a provider default.
4. Validate all structured data with Pydantic v2 at every boundary; surface
   caught schema violations in the UI as a demonstrated feature.
5. After any live provisioning, say aloud:
   *"Resources are live and billing. Run `make teardown` when done."*

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Automates two Microsoft Foundry portal workflows — model discovery/evaluation
and supervised fine-tuning — as three agentic pipelines: a FastAPI backend
runs a **LangGraph orchestrator** that routes each request to one of three
sub-agents (Discovery, Fine-Tune, Comparison), each of which talks to Azure
exclusively through typed **MCP tools** (3 stdio servers, 19 tools total,
also directly usable by Claude Desktop/Code standalone). A React/TypeScript
dashboard drives the three workflows; Terraform provisions the Azure
infrastructure.

Runs at **$0 by default** (`DEMO_MODE=mock`, fixture-backed, no Azure account
needed) and switches to real Azure Foundry calls with one env var
(`DEMO_MODE=live`).

## Commands

```bash
make setup              # venv + Python deps + frontend deps + .env from .env.example
make run                # run all 3 workflows end-to-end via app.cli (honours DEMO_MODE)
make api                # FastAPI backend, uvicorn --reload, localhost:8000
make frontend           # React dev server (Vite), localhost:5173
make mcp-list           # list every tool across the 3 MCP servers
make test               # alias for test-unit
make test-unit          # pytest tests/unit -q — no cloud, no network
make fmt                # ruff format src mcp_servers tests
make clean              # remove caches/build artefacts
```

Single test / single file (PYTHONPATH is `src`, set automatically by `make`,
or export manually when calling pytest directly):

```bash
.venv/bin/pytest tests/unit/test_orchestrator.py -q
.venv/bin/pytest tests/unit/test_orchestrator.py::test_specific_case -q
.venv/bin/ruff check src mcp_servers tests   # lint (format-only target is `make fmt`)
```

Cloud-touching commands (real Azure resources, real billing — confirm with
the user before running any of these):

```bash
make provision           # terraform apply; budget alert created FIRST, then sync-env + smoke-post-provision
make hosting-role        # one-time: create the least-privilege custom role for hosting OIDC (run before first provision that includes hosting.tf)
make teardown            # terraform destroy + orphan sweep at every suffix + smoke-post-teardown verification
make smoke-pre           # pre-provision checks: az auth, region, model availability, quota
make smoke-post-provision
make smoke-post-run
make smoke-post-teardown # release blocker: asserts zero surviving tagged resources
```

Pytest markers (`pyproject.toml`): `live`, `post_teardown`, `smoke_pre`,
`smoke_post_provision`, `smoke_post_run`, `smoke_post_teardown`. The
`tests/smoke_*` suites require `RUN_LIVE_SMOKE=1` and provisioned Azure
resources — don't run them against mock mode expecting them to pass.

## Architecture

```
React + TypeScript (frontend/)
        │ REST
FastAPI (src/app/main.py)  — /catalog /fine-tune /inference /agent /auth
        │
LangGraph Orchestrator (src/app/agents/orchestrator.py) — supervisor routes by intent
    ├─ discovery_agent   ├─ finetune_agent   └─ comparison_agent
        │ MCP (in-process call, real stdio JSON-RPC when run standalone)
mcp_servers/foundry_catalog  foundry_finetune  foundry_inference   (19 tools)
        │
services/fixtures.py  ⇄  services/azure_foundry.py   (mock vs. live, identical schema)
        │
Azure AI Foundry (eastus2)
```

**Mock vs. live is the central seam.** Every MCP tool has the identical
schema in both modes; `DEMO_MODE` only swaps the backing implementation
between `src/app/services/fixtures.py` (reads `data/fixtures/*.json`) and
`src/app/services/azure_foundry.py` (real Azure SDK calls). Nothing in the
agents, routers, or frontend branches on mode — if you're adding a feature,
keep it that way: implement both service functions with the same return
shape rather than special-casing `is_mock` in a router or agent.

**Orchestrator routing is keyword-based, not LLM-based** (`orchestrator.py`
`classify()`) — deliberately, so it's deterministic, free, and works with no
model deployed in mock mode. An explicit `demo` argument always wins over
classification. Swapping in an LLM classifier means replacing `classify()`
alone.

**MCP servers run in-process, not as subprocesses.** `src/app/mcp_clients/registry.py`
calls `MCPServer.call_tool` directly against the same `mcp_servers/foundry_*`
instances that would otherwise run standalone over stdio — same tool schemas
and handlers, no IPC overhead, deterministic tests. The servers under
`mcp_servers/` are still real, independently runnable MCP servers usable by
Claude Desktop/Code.

**Every workflow runs as a background job, not a blocking request**
(`src/app/jobs.py`). Live-mode runs can take 10–60 minutes, so
`POST /agent/invoke/start` returns a `job_id` immediately and the frontend
polls `GET /agent/jobs/{job_id}` every 2s, resuming from `localStorage` across
a page refresh. `current_job_id` is a `ContextVar` (not a threaded parameter)
so `report()` can be called from deep inside `services/azure_foundry.py`,
which has no job concept, without changing its signature — this works across
`asyncio.to_thread()` boundaries because contextvars propagate into worker
threads automatically.

**Pydantic v2 schemas (`src/app/schemas/`) are the single source of truth**
for every metric, cost formula, and evaluator direction — catalog,
comparison, dataset, evaluation, finetune, training. Fixtures and live Azure
responses are both validated against the same models.

**Config is centralized in `src/app/config.py`** — nothing reads
`os.environ` directly elsewhere. `Settings` (pydantic-settings) loads from
`.env`; `get_settings()` is an `lru_cache`d singleton. Notably: the
travel-assistant system prompt (`TRAVEL_SYSTEM_PROMPT`) and the five
canonical comparison prompts are defined once here and reused across the
training data, the fine-tune agent, and the comparison agent — that identity
is what makes the baseline-vs-fine-tuned comparison fair; don't fork it per
call site.

**Auth has two independent layers that must not be conflated.** `demo`/`demo123`
(`DEMO_USERNAME`/`DEMO_PASSWORD`) is a static UI gate only, unrelated to
security. Real access control for the hosted deployment is Microsoft Entra
ID — MSAL.js on the frontend, self-managed bearer-token validation in
`src/app/auth_entra.py` (not Container Apps' Easy Auth, which has a
confirmed CORS-preflight bug for this SPA + separate-origin-API shape — see
`docs/TROUBLESHOOTING.md` #12–15). `require_entra_auth` is a no-op when
`ENTRA_TENANT_ID`/`ENTRA_CLIENT_ID` are unset (local/mock dev); it's applied
as a router dependency to `catalog`, `finetune`, `inference`, `agent` in
`main.py` — `health` and `auth` stay open.

**Cost-guarded Terraform** (`infra/terraform/`): a budget alert is created
*before* any billable resource (`make provision` runs `smoke-pre` first),
resource names carry an auto-incrementing suffix, and `teardown` runs a
tag-based orphan sweep (`MANAGED_BY_TAG = "foundry-agentic-platform"`,
defined once in `config.py`) at every suffix, verified by
`smoke_post_teardown` as a release blocker.

## Fine-tuning dataset catalog

The lab's own `data/travel-finetune-hotel.jsonl` is the default and drives
Demo 2's orchestrated flow, Demo 3's canonical prompts, and all cost figures
elsewhere — don't repoint those at another dataset. Additional datasets in
`data/converted/` (support triage, healthcare, e-commerce, IT helpdesk,
banking, gardening) are selectable via `GET /finetune/datasets`, converted
from AWS Bedrock's Converse JSONL format by
`data/convert_bedrock_datasets.py`, and validated against the same
`TrainingRecord` schema as the default dataset.

## Notes for changes

- `DEMO_MODE=live` bills real Azure spend (a fine-tuning job kicked off by
  mistake, or a deployment on the wrong tier, is real, avoidable spend —
  Standard tier vs. Developer tier is $1,224/month vs. $0/hour for one
  deployment). Never flip `DEMO_MODE` to `live` or run `make provision` /
  `make teardown` without the user's explicit go-ahead.
- `docs/TROUBLESHOOTING.md` and `docs/LESSONS_LEARNED.md` document real bugs
  hit during live runs (async file-processing races, premature-deploy
  crashes, CORS/Easy Auth issues) — check there before re-diagnosing a
  symptom that looks familiar.

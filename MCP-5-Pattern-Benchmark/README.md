# mcp-pattern-benchmark

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/Protocol-MCP-6C3FC5)
![Postgres](https://img.shields.io/badge/Backend-Postgres-4169E1?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-Apache_2.0-green)

Measures what an MCP server's architecture costs an agent. Five server design
patterns, each compared against a weaker control server serving the identical
scenario, the identical tasks and the identical model — so the difference in
cost is attributable to the design, not the workload.

Status: **complete. All 6 phases done.**

- [`CONTEXT.md`](./CONTEXT.md) — the vocabulary
- [`docs/PLAN.md`](./docs/PLAN.md) — the build plan
- [`docs/adr/`](./docs/adr/) — why the design is shaped this way



## Why This Comparison Is Fair

This isn't five demos with a scoreboard — every number is produced by a
controlled A/B pair:

- **One control, reused four times.** Modules 1, 2, 4 and 5 are each measured
  against the same flat, vendor-named, 1:1 wrapper — the server a team ships
  first. Only module 3 needs its own baseline. See ADR
  [`0002`](./docs/adr/0002-baseline-pairing.md).
- **One synthetic backend, not a live third-party API.** Postgres behind one
  FastAPI service, seeded fresh per task — so a reader clones the repo and
  regenerates the same table, instead of chasing rate limits or drifting
  data. See ADR [`0005`](./docs/adr/0005-synthetic-backend.md).
- **Three metrics, never blended into one score.** Success rate, turn count
  and input tokens are reported side by side — a pattern module rarely
  changes whether a task is *possible*, it changes what the task *costs*.
  See ADR [`0004`](./docs/adr/0004-no-composite-score.md).
- **Task descriptions name no tool from either server** — `tests/test_task_neutrality.py`
  fails the build if one does, so a task can't tip the agent toward the
  server it's meant to be neutral about.
- **A gate, not a fixed model.** If the control passes every task 3 times
  running, the model is too strong to show a difference, and the same 8
  tasks rerun at a smaller model before anyone touches a task file.



## How Each Module Is Measured

```
task description (names no tool from either server)
      │
      ▼
agent ──► MCP server (pattern)  ──┐
      └─► MCP server (control)  ──┤
                                   ▼
                    same Postgres backend, reseeded per task
                                   │
                                   ▼
                    verify.py reads final state back
                                   │
                                   ▼
        aggregate: success rate · turns · input tokens, per server
```

Both servers front the identical backend and answer to the identical task, so
a difference in the aggregate can only come from the server's design — how
many round trips it takes, how much state the agent has to resend, whether
one call does what the control needs several for.



## The Problem

| Current Pain Point | Impact |
|---|---|
| No controlled data on what an MCP server's shape costs an agent | Architecture picked on intuition, not evidence |
| "Fewer round trips" and "less resent state" are claims, not measurements | Teams can't compare a wrapper against a purpose-built server before shipping either |
| Cost is reported as one blended score when it's asked for | The mechanism moving the number gets averaged away |
| Real third-party backends drift and rate-limit | A result can't be reproduced by someone else's clone |

## The Solution

Five pattern modules, each an A/B pair against a control, run at one fixed
model with the same 8 tasks 3 times over:

- **Tool Orchestrator** — one call does what the control's wrapper needs
  several for.
  **Use when** a business operation is always the same fixed sequence of
  dependent calls (create → attach → assign → notify) — collapsing a
  sequence that never varies has no downside. Confirmed: -47% turns, -67%
  tokens, same success.
- **Domain Adapter** — the server resolves domain lookups the control's flat
  API leaves to the agent.
  **Use when** the agent would otherwise have to resolve a business-domain
  reference (a customer, a ticket by title) that the backend already knows
  how to look up. Confirmed: -33% turns, -76% tokens, same success.
- **Stateful Session Server** — the server holds working state so the agent
  doesn't have to resend it every call.
  **Use when** a session accumulates enough state that resending it every
  turn would dominate cost. This benchmark's task (2-3 comments per review)
  was too small to clear that bar — it's a **negative finding at this
  scale**: +4% turns, +6% tokens for the same success. A longer-lived
  session is where the thesis should hold; see Limitations.
- **Proxy Aggregator** — one server fronts three backends' worth of tools
  behind scoped discovery.
  **Use when** unifying multiple backends behind one server actually cuts
  the agent's tool surface — but only if identifiers can be resolved
  directly. This benchmark's result is a **negative finding**: +148% turns,
  +92% tokens, -44% success, traced to an id-guessing gap shared by both
  servers, not to the aggregation pattern itself; see Limitations.
- **Resource Gateway** — `list_resources`/`read_resource` surface content the
  control's tools only return raw.
  **Use when** an agent needs to discover and browse read-only reference
  content (docs, runbooks) rather than fetch one already-known record.
  Confirmed: +50% success, -9% tokens.



## Results

`gpt-4.1-mini`, 3 runs x 8 tasks per server. Success rate, turns and input
tokens are reported side by side, never blended into one score. Each module
is its own A/B pair (see ADR 0002) — the 5 modules are not measured on one
shared dataset, so read each column down, never across modules.

![Control vs. pattern, per module, 3 metrics, with a confirms/negative verdict per module](./docs/phase6-chart.png)

The table below is the same numbers this chart draws from:

| Module | Control success | Pattern success | Control turns | Pattern turns | Control input tokens | Pattern input tokens |
|---|---|---|---|---|---|---|
| Tool Orchestrator | 24/24 (100%) | 24/24 (100%) | 3.79 | 2.00 | 2,427 | 809 |
| Domain Adapter | 24/24 (100%) | 24/24 (100%) | 3.00 | 2.00 | 2,925 | 700 |
| Stateful Session Server | 24/24 (100%) | 24/24 (100%) | 5.75 | 5.96 | 6,563 | 6,970 |
| Proxy Aggregator | 16/24 (66.7%) | 9/24 (37.5%) | 7.38 | 18.29 | 14,433 | 27,681 |
| Resource Gateway | 10/24 (41.7%) | 15/24 (62.5%) | 2.88 | 4.08 | 2,814 | 2,559 |

→ **3 of 5 modules confirm the thesis** — fewer turns, fewer input tokens, at
equal success: Tool Orchestrator (-47% turns, -67% tokens), Domain Adapter
(-33% turns, -76% tokens), Resource Gateway (+50% success, -9% tokens).

→ **2 of 5 do not** — Stateful Session Server costs slightly more (+4% turns,
+6% tokens) than its own control; Proxy Aggregator costs more *and* succeeds
less (+148% turns, +92% tokens, -44% success). Both are reported as negative
findings, not averaged in with the rest — see Limitations.

→ **0 re-run crashes** across all 5 modules' gate passes (120 agent runs at
`gpt-4.1-mini`).

→ **~$0.78** total LLM spend for that same 120-run gate suite, at
`gpt-4.1-mini`'s public per-token rate — see Cost Estimate.



## Architecture

```
pipeline.py --mcp <server> --models <model> --k 3 --exp-name <name>
      │
      ▼
src/factory.py  ──resolves──►  MCPServiceFactory  (src/services.py registry)
      │
      ▼
src/agents/mcpmark_agent.py  ──drives──►  agent turns against the MCP server
      │                                    (src/agents/mcp/stdio_server.py)
      ▼
   MCP server (pattern OR control, never both in one run)
      │
      ▼
   backend/app.py  (FastAPI)  ──►  Postgres, reseeded per task (backend/seed.py)
      │
      ▼
tasks/<module>/standard/<task_id>/verify.py  ──reads final state back──►  TaskResult
      │
      ▼
src/aggregators/aggregate_specific_results.py  ──►  success rate, turns, input tokens
```



## Six-Phase Build

| Phase | Module | New backend | New baseline | Harness change |
|---|---|---|---|---|
| 0 | Repo — fork MCPMark, strip to the harness | — | — | — |
| 1 | Tool Orchestrator | `/tickets` | none | none |
| 2 | Domain Adapter | customers in `/tickets` | none, reuses control | none |
| 3 | Stateful Session Server | change requests in `/repos` | stateless server | none |
| 4 | Proxy Aggregator | `/repos`, `/runbooks`, `/deploys` | none, reuses control | none |
| 5 | Resource Gateway | runbook documents | none, reuses control | `list_resources`, `read_resource` |
| 6 | README — this report | — | — | — |

Full detail per phase: [`docs/PLAN.md`](./docs/PLAN.md), the per-phase specs
in [`docs/specs/`](./docs/specs/), and the ticket-by-ticket build log under
[`.scratch/`](./.scratch/) (each module's `issues/` directory).



## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Agent-model access** | LiteLLM (`litellm`) — one interface across model providers |
| **Agent-tool protocol** | Model Context Protocol (`mcp`), stdio transport |
| **Pattern & control servers** | Python, `mcp` server SDK |
| **Backend API** | FastAPI + Uvicorn |
| **Backend store** | PostgreSQL 16 (`psycopg2-binary`), Docker Compose |
| **Chart** | Matplotlib |
| **Tests** | pytest |
| **Lint/format** | Ruff |
| **Env/config** | `python-dotenv`, `pydantic`, `pyyaml` |
| **Packaging** | `uv` / hatchling |



## Dependencies & Services Used

| Dependency | Purpose |
|---|---|
| PostgreSQL | Single synthetic backend store, reseeded per task |
| FastAPI service (`backend/app.py`) | The one HTTP API every pattern and control server fronts |
| Docker Compose (`compose.yaml`) | Runs Postgres + the API together for local dev and the harness |
| MCP stdio servers (`src/mcp_services/*`) | The pattern and control server implementations under test |
| LiteLLM | Routes agent calls to whichever model `--models` names |
| `pricing.py` (`src/aggregators/`) | Per-model $/M-token table used for the cost estimate below |



## Prerequisites

- **Python 3.12** (`requires-python = ">=3.12,<3.13"` in `pyproject.toml`)
- **Docker** — for Postgres + the backend API via `compose.yaml`
- **`uv`** (or `pip`) to install dependencies
- **An API key** for whichever model provider you run — see Setup



## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Add your model provider key and DATABASE_URL
#    pipeline.py loads .mcp_env at start (gitignored, never committed).
#    compose.yaml only sets DATABASE_URL inside the api container — the
#    pipeline process on your host needs its own, at the mapped host port,
#    or every task's setup step fails silently before the agent runs
#    (0 turns, 0 tokens, every task reported as failed).
cat >> .mcp_env <<'EOF'
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tickets
EOF

# 3. Start the backend
docker compose up -d
```

![docker compose down -v / up -d / docker ps, both containers Up](./docs/screenshots/docker-ps.png)



## Running the Project

```bash
# One server, one model, single run
uv run python -m pipeline --mcp resource_wrapper --models gpt-4.1-mini --k 1

# Full gate for one module: 3 runs, both servers, then aggregate
uv run python -m pipeline --mcp resource_wrapper  --models gpt-4.1-mini --k 3 --exp-name gate
uv run python -m pipeline --mcp resource_gateway  --models gpt-4.1-mini --k 3 --exp-name gate

# Aggregate, one result-dir at a time (not per --exp-name)
uv run python -m src.aggregators.aggregate_specific_results \
    --result-dir results/gate/gpt-4-1-mini__resource_wrapper --k 3
uv run python -m src.aggregators.aggregate_specific_results \
    --result-dir results/gate/gpt-4-1-mini__resource_gateway --k 3
```

`--mcp` accepts any registered server name (`wrapper`, `orchestrator`,
`domain_wrapper`, `domain_adapter`, `session_baseline`, `session_server`,
`proxy_wrapper`, `proxy_aggregator`, `resource_wrapper`, `resource_gateway`).
Results land under `results/<exp-name>/`, gitignored so the repo stays
reproducible-by-rerun rather than shipping stale data.

### Example run — Resource Gateway, live

One task's full setup → execute → verify → cleanup cycle, control then
pattern:

![resource_wrapper (control): Stage 1-4 for one task](./docs/screenshots/wrapper-run.png)
![resource_gateway (pattern): Stage 1-4 for one task](./docs/screenshots/gateway-run.png)

Each server's 3-run tail:

![resource_wrapper: 3 runs complete](./docs/screenshots/wrapper-results.png)
![resource_gateway: 3 runs complete](./docs/screenshots/gateway-results.png)

Then aggregated:

![aggregate_specific_results for both servers](./docs/screenshots/wrapper-gateway-summary.png)

This particular run landed at 45.8% vs. 50.0% pass@1 — different from the
README's headline 41.7%/62.5% table above. Expected: 3 runs × 8 tasks is
enough to see a direction, not to pin an exact number (see Limitations).
Same direction as the headline run either way: gateway succeeded more
(50.0% vs. 45.8%) and cost fewer tokens per run (16,877 vs. 23,466), at
the cost of more turns (3.54 vs. 2.92) — all three metrics reported
side by side, never blended (ADR 0004).



## Project Structure

```
mcp-pattern-benchmark/
├── pipeline.py                 # CLI entry point (argparse)
├── compose.yaml                # Postgres + backend API for local dev
├── pyproject.toml              # Dependencies, Python 3.12 pin
│
├── backend/                    # The one FastAPI service every server fronts
│   ├── app.py
│   ├── schema.sql
│   └── seed.py                 # Resets/reloads per task
│
├── src/
│   ├── agents/                 # Agent loop + MCP stdio/http client
│   ├── aggregators/            # Per-run → per-server metrics, pricing table
│   ├── base/                   # Task/state managers shared by all modules
│   ├── config/                 # Model config schema
│   ├── mcp_services/           # One dir per module: pattern + control servers
│   │   ├── tool_orchestrator/
│   │   ├── domain_adapter/
│   │   ├── stateful_session/
│   │   ├── proxy_aggregator/
│   │   └── resource_gateway/
│   ├── evaluator.py            # Runs one task, produces a TaskResult
│   ├── factory.py               # Resolves --mcp to a registered server
│   └── services.py             # The server registry
│
├── tasks/                      # meta.json + description.md + verify.py, per module
│   ├── tool_orchestrator/standard/
│   ├── domain_adapter/standard/
│   ├── stateful_session/standard/
│   ├── proxy_aggregator/standard/
│   └── resource_gateway/standard/
│
├── docs/
│   ├── PLAN.md                 # The build plan, phase by phase
│   ├── specs/                  # One spec per module
│   ├── adr/                    # Why the design is shaped this way
│   ├── phase6_chart.py         # Generates phase6-chart.png below
│   └── phase6-chart.png
│
├── .scratch/                   # Ticket-by-ticket build log per module
│
└── tests/                      # Unit + neutrality tests, per module
```



## Running Tests

```bash
uv run pytest
```

26 test files, including one neutrality test per module
(`test_task_neutrality*.py`) that fails the build if any `description.md`
names a tool from either server — the mechanism behind the "fair comparison"
claim above, not just an assertion of it.



## Cost Estimate

`pipeline.py` loads `.mcp_env` for provider credentials; per-run cost is
computed from `src/aggregators/pricing.py`'s $/M-token table when the model
is listed there (`gpt-4.1-mini` and `gpt-4.1-nano` both are).

| Run | Tasks | Tokens (in + out) | Est. cost |
|---|---|---|---|
| Full `gpt-4.1-mini` gate suite, all 5 modules (this report's headline data) | 120 agent runs (5 modules x 2 servers x 3 runs x 8 tasks) | 1,629,161 in + 80,028 out | **~$0.78** |

Cheap by design: ADR [`0005`](./docs/adr/0005-synthetic-backend.md)'s
synthetic backend and a small, fixed model keep a full re-run of this
report's data under a dollar.



## Key Engineering Decisions

| Challenge | Solution |
|-----------|---------|
| A pattern module needs a number to mean something, not just exist | A/B pair against one reused control, never an absolute score (ADR 0002) |
| Real third-party APIs make results irreproducible | One synthetic Postgres backend behind one API, seeded per task (ADR 0005) |
| A single score hides which mechanism moved it | Report success rate, turns, input tokens side by side, no blend (ADR 0004) |
| Code-First Hybrid Adapter needs a code-execution sandbox the harness lacks | Deferred; state the omission in this README rather than delay 5 shipped modules (ADR 0003) |
| Proxy Aggregator's scoped tool list could make the harness itself a variable | Server exposes a `discover_tools` tool instead of the harness re-listing tools every turn (ADR 0006) |
| "The client resends state" would make the *agent* a variable across modules | Stateful Session Server's control is a stateless *server*, not a modified client (ADR 0007) |
| Resource Gateway's leak-or-not is a content shape, not a database row | Verifier scans agent output text for withheld notes, not just state equality (ADR 0008) |
| `domain_adapter`'s first live run scored 1/8 — no way to resolve a ticket id | Tool takes `ticket_title`, resolved internally against the existing list endpoint |
| README's status line said "Phase 0 of 6" after all 6 were done | This report |



## Limitations

- **1 model.** All headline numbers are `gpt-4.1-mini`. A gate-recovery run at
  `gpt-4.1-nano` exists per module (see each module's ticket under
  `.scratch/`) but is not part of this report.
- **8 tasks per module**, 3 runs each — enough to gate a direction, not to
  bound noise tightly (e.g. Proxy Aggregator's control ranged 5/8 to 6/8
  across its 3 runs).
- **Synthetic backend**, not a real production system — see ADR
  [`0005`](./docs/adr/0005-synthetic-backend.md).
- **Code-First Hybrid Adapter not built** — see ADR
  [`0003`](./docs/adr/0003-defer-code-first-hybrid.md).
- **Re-run crashes: 0.** No run needed a retry across any module's gate pass.
- **Stateful Session Server is a negative finding, not a null result.** At
  this task's scale (2-3 comments per review), the baseline's per-call resend
  cost is smaller than the pattern's one mandatory extra tool call — ADR
  0007's thesis needs a task with more state to resend before it shows.
- **Proxy Aggregator and Resource Gateway share an unresolved gap**: neither
  surface lets the agent look up a repo id by name, so both servers pay a
  guessing cost. It depresses both sides of each comparison equally, but is
  not zero.



## Author

**Marcos Oliveira** — [LinkedIn](https://www.linkedin.com/in/mfilho1/) | [GitHub](https://github.com/MAOFILHO)



## Credit

The evaluation harness is forked from [MCPMark](https://github.com/eval-sys/mcpmark)
by eval-sys, used under its original license. See [`LICENSE`](./LICENSE).
The pattern modules, backend, tasks and results are this project's own.

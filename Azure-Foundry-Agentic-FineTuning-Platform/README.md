# Foundry Agentic FineTuning Platform

**Live:** [black-bay-02b703b0f.7.azurestaticapps.net](https://black-bay-02b703b0f.7.azurestaticapps.net) (Microsoft sign-in required — see [Live deployment](#live-deployment))

A production-grade, zero-console-click replacement for two Microsoft Foundry
hands-on lab guides ("Explore and compare models" and "Fine-tune a language
model") — both 100% portal click-throughs in their original form. This
project automates every step behind a LangGraph orchestrator over Model
Context Protocol (MCP) tools, a FastAPI backend, a Contoso-themed React UI,
and cost-guarded Terraform IaC.

## Business case

The two source labs teach the same underlying workflow — deploy a model,
evaluate it, fine-tune it, compare it — entirely through manual portal
clicks: browse the model catalog, read a leaderboard, click through a
fine-tuning wizard, babysit a 60-minute training job, eyeball two chat
responses side by side. None of that is reproducible, testable, or
automatable as written.

This project turns that into three one-click workflows backed by a real agentic
pipeline: an **Orchestrator Agent** routes each request to one of three
**Sub-Agents** (Discovery, Fine-Tune, Comparison), each of which talks to
Azure exclusively through typed **MCP tools** — the same tools Claude
Desktop/Code could call directly, since nothing here is UI-specific. The
whole thing runs at **$0** by default (`DEMO_MODE=mock`, fixture-backed, no
Azure account needed) and switches to real Azure Foundry calls with one
environment variable.

## Architecture

```
                        React + TypeScript (Contoso theme)
              fixed 18% sidebar · static auth demo/demo123 · 3 workflow triggers
                                      │ REST
                        ┌─────────────▼─────────────┐
                        │   FastAPI  (src/app)      │
                        │  /catalog /finetune       │
                        │  /inference /agent /auth  │
                        └─────────────┬─────────────┘
                                      │
                        ┌─────────────▼─────────────┐
                        │  LangGraph Orchestrator   │  ← supervisor, routes by intent
                        └──┬──────────┬──────────┬──┘
                           │          │          │
                  ┌────────▼──┐ ┌─────▼─────┐ ┌──▼──────────┐
                  │ Discovery │ │ FineTune  │ │ Comparison  │   sub-agents
                  │  Agent    │ │  Agent    │ │   Agent     │
                  └────────┬──┘ └─────┬─────┘ └──┬──────────┘
                           │  MCP (stdio/JSON-RPC)│
                  ┌────────▼──┐ ┌─────▼─────┐ ┌──▼──────────┐
                  │mcp-catalog│ │mcp-finetune│ │mcp-inference│  3 MCP servers, 19 tools
                  └────────┬──┘ └─────┬─────┘ └──┬──────────┘
                           └──────────┼──────────┘
                                      │ mock fixtures  ⇄  live Azure SDK
                        ┌─────────────▼─────────────┐
                        │  Azure AI Foundry (eastus2)│
                        └───────────────────────────┘
```

**Why MCP servers and not plain functions:** the same three servers
(`mcp_servers/foundry_{catalog,finetune,inference}`) are directly usable by
Claude Desktop/Code as standalone MCP servers — the Azure tooling built here
is reusable outside this app, not locked to its UI.

**Mock vs. live:** every MCP tool has the identical schema in both modes;
`DEMO_MODE` only swaps the backing implementation
(`src/app/services/fixtures.py` vs. `src/app/services/azure_foundry.py`).
Nothing in the agents, routers, or frontend branches on mode.

## The three workflows

| Workflow | Reproduces | What it does |
|---|---|---|
| **1 — Model Discovery & Evaluation** | *Explore and compare models* | Catalog browse, 4-axis leaderboard (quality / safety / throughput / cost — no single model wins all four), gpt-5.4 vs. gpt-5.4-mini comparison, 45-row synthetic evaluation across 16 evaluators (98% / 704/720, matching the lab exactly) |
| **2 — Supervised Fine-Tuning** | *Fine-tune a language model* | JSONL validation (schema violations shown as a feature, not an error), pre-spend cost estimate, SFT job submission on `gpt-4.1`, live progress (100 steps, final loss 0.02), $0/hr Developer-tier deployment. Also ships a **selectable dataset catalog** — 7 additional domains (support triage, healthcare, e-commerce, IT helpdesk, banking, gardening) converted from AWS Bedrock's format, validated and cost-estimated on demand, without touching the lab's own dataset or numbers. |
| **3 — Agentic Inference & Comparison** | Both labs' baseline-vs-fine-tuned pattern | Five canonical prompts, identical system message on both sides, scored on **behaviour** (friendly tone, no hotel/flight/car/restaurant recommendation, ends with a question) — not string equality, since the guide explicitly warns outputs are non-deterministic |

## Prerequisites

- Python 3.12+, Node.js 20+
- **Mock mode (default): nothing else.** Runs at $0 with no Azure account.
- **Live mode:** an Azure subscription with Owner/Contributor rights, `az
  login` completed, quota for the `gpt-5.4` family and `gpt-4.1` fine-tuning
  access in `eastus2`.

## Quickstart

```bash
make setup          # venv + Python deps + frontend deps + .env from .env.example
make run             # all 3 workflows end-to-end, mock mode, $0 — writes outputs/*.json
make api             # FastAPI on :8000  (try curl localhost:8000/health)
make frontend         # React dev server on :5173 — login demo / demo123
```

Or with Docker (no Python/Node install needed):

```bash
docker compose up    # backend :8000, frontend :8080 — both $0, mock mode
```

Going live:

```bash
make provision       # budget alert FIRST, then Terraform apply, then live smoke tests
DEMO_MODE=live make run
make teardown         # destroys every tagged resource, at every suffix, then verifies zero survive
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `mock` | `mock` = fixtures, $0. `live` = real Azure Foundry calls, real billing. |
| `AZURE_SUBSCRIPTION_ID` / `AZURE_TENANT_ID` | — | Only needed in live mode. |
| `AZURE_LOCATION` | `eastus2` | Locked — matches every screenshot in both source lab guides. |
| `AZURE_FOUNDRY_ENDPOINT` / `AZURE_FOUNDRY_API_KEY` | — | Populated automatically by `make provision` → `app.cli sync-env`. |
| `PROJECT_BASE_NAME` | `foundry-travel` | Base for Terraform's auto-increment naming (`-v1`, `-v2`, …). |
| `MODEL_BASELINE` / `MODEL_COMPARE_A` / `MODEL_COMPARE_B` | `gpt-4.1` / `gpt-5.4` / `gpt-5.4-mini` | The three catalog models the labs deploy. |
| `FT_DEPLOYMENT_TYPE` / `FT_TRAINING_TYPE` | `Developer` | $0/hr tier — see cost table below for why. |
| `BUDGET_CEILING_USD` | `25` | Consumption budget alert threshold (50/80/100%). |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | — | Populated by `make provision`; blank = console-only tracing. |
| `DEMO_USERNAME` / `DEMO_PASSWORD` | `demo` / `demo123` | **Static demo gate, not real authentication** — labelled as such in the UI and API. |

Full list in [`.env.example`](.env.example).

## Cost

**Nothing in this design bills by the hour.** Every model deployment is
Global Standard or Developer Tier — both pay-per-token at a **$0/hour** rate.

| Scenario | Cost |
|---|---|
| Mock mode (default), unlimited runs | **$0.00** |
| One full live session (all 3 workflows) | **≈ $3–6** (dominated by Workflow 1's 16-evaluator × 45-row evaluation) |
| Fine-tune training alone | **≈ $0.016** (Developer tier, 16,000 billed tokens) |
| Left running 48 h idle | **≈ $0.00** |
| Left running 30 d idle | **≈ $0.50** (App Insights + state storage only) |

If Standard tier were used instead of Developer for the fine-tuned
deployment, that single line item would be **$1,224/month** — which is
exactly why Developer is the default. Full breakdown, SKU-by-SKU, in
[`COSTS.md`](COSTS.md).

## Testing

```bash
make test                    # 78 unit tests, no cloud, no network
make smoke-pre                 # python/terraform/az checks; live checks need RUN_LIVE_SMOKE=1
RUN_LIVE_SMOKE=1 make smoke-post-provision   # after `make provision`: every resource live + approved SKU
RUN_LIVE_SMOKE=1 make smoke-post-teardown     # after `make teardown`: zero surviving resources — release blocker
```

Three GitHub Actions workflows in `.github/workflows/`:

- **`ci.yml`** — lint, unit tests, mock end-to-end, frontend build. Runs on
  every push/PR. **Never provisions anything.**
- **`deploy.yml`** — manual (`workflow_dispatch`, requires typed
  confirmation) — provisions Azure, runs live, tears nothing down.
- **`teardown.yml`** — manual + nightly cron safety-net sweep, catching any
  resource orphaned by the auto-increment naming scheme (see below).

## A deliberate risk, and how it's mitigated

Terraform names resources with an auto-incrementing suffix (`-v1`, `-v2`, …)
on a naming collision, via `infra/terraform/scripts/next_suffix.py`. This is
normally the wrong pattern for IaC — a lost `.suffix.lock` can orphan a
resource outside Terraform's state, invisible to a plain `terraform
destroy`. It was chosen deliberately here anyway (see `PLAN.md`), and is made
safe by three mitigations: every resource carries a `managed_by` tag;
`make teardown` sweeps and deletes **every** tagged resource group at **any**
suffix, not just the one in state; and `smoke_post_teardown` is a release
blocker that fails loudly if even one survives.

Since every resource in this design is $0/hour (see Cost, above), an orphan
costs nothing while idle — which is what makes the pattern acceptable here
rather than merely risky.

## Live deployment

The app itself (not just the AI infra) is hosted publicly:
**[black-bay-02b703b0f.7.azurestaticapps.net](https://black-bay-02b703b0f.7.azurestaticapps.net)**
— Azure Static Web Apps (Free tier) for the frontend, Azure Container Apps
(Consumption, `min_replicas = 0`) for the backend, both provisioned by
`infra/terraform/hosting.tf`.

**Sign-in is required and enforced server-side.** The demo/demo123 screen
used for local/mock dev was never checked by the backend — fine on
localhost, a real risk on a public URL, since anyone who found it could
submit real fine-tuning jobs on your Azure bill with no login at all. The
hosted build requires real Microsoft Entra ID sign-in instead
(`frontend/src/App.tsx` + `src/app/auth_entra.py`), gating every route
except `/health`.

**Deliberately not Container Apps' built-in "Easy Auth."** It authenticates
the browser's CORS preflight (`OPTIONS`) request too, and a preflight
structurally never carries credentials — so Easy Auth 401s every
cross-origin call from the SPA before it starts. Confirmed live and matches
a known, unresolved platform limitation
([microsoft/azure-container-apps#359](https://github.com/microsoft/azure-container-apps/issues/359)).
The backend validates Entra bearer tokens itself instead (`auth_entra.py`),
behind its own `CORSMiddleware`, which answers `OPTIONS` correctly since it
never depends on auth.

**Defaults to `DEMO_MODE=mock`** ($0, no real Azure calls) even though it's
publicly reachable — a public URL is not a reason to default to live
billing. Flip the Container App to `live` only when intentionally
demonstrating it, and watch the budget.

**Hosting cost:** ≈ $0–2/month on top of the AI infra's own cost (see
[Cost](#cost) above) — every new resource is free-tier or consumption-based
with a $0/hour idle rate. See `PLAN.md`'s public-hosting-phase section for
the full breakdown and the decisions behind it (Docker Hub over ACR to
avoid the one non-$0 line item, `min_replicas = 0` cold-start trade-off,
etc.).

**CI/CD:** this project lives in a monorepo
([`Portfolio-Projects`](https://github.com/MAOFILHO/Portfolio-Projects)) —
all four GitHub Actions workflows
(`azure-foundry-agentic-finetuning-platform-{ci,deploy,teardown,hosting-deploy}.yml`)
live at that repo's root `.github/workflows/`, not in this folder, matching
the monorepo's convention. CI is path-scoped to this folder only; deploy/
teardown/hosting-deploy are `workflow_dispatch`-only (never auto-triggered)
and authenticate via OIDC against a dedicated, least-privilege custom role
(`infra/foundry-deployer-role.json`) — not broad Owner/Contributor, and
unable to touch other projects' resources in that same repo/subscription.

## Troubleshooting & Lessons Learned

Fifteen real bugs were found and fixed by actually running this project
against live Azure — mock mode's fixtures are always well-formed, complete,
and fast, so none of these surfaced until real Azure responses hit real edge
cases (async processing races, `null` fields on in-progress jobs, a
confirmed platform bug in Container Apps' Easy Auth, JWT claims that
contradicted documentation). Full write-ups, each with Symptom / Root cause
/ Fix, live in their own pages:

- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** — the 15 bugs themselves
- **[docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md)** — the generalizable takeaways from each one

## Project layout

```
├── src/app/            FastAPI app: routers, LangGraph agents, Pydantic v2 schemas, config, telemetry
├── mcp_servers/         3 MCP servers (catalog, finetune, inference) — 19 tools total
├── frontend/            Vite + React 18 + TypeScript, Contoso theme
├── infra/terraform/      Budget-first IaC: budget → Foundry account/project → model deployments
├── data/                Lab dataset + 7 additional converted datasets + fixtures for mock mode
├── tests/               unit / smoke_pre / smoke_post_provision / smoke_post_run / smoke_post_teardown
├── (GitHub Actions workflows live at the monorepo root .github/workflows/,
│   prefixed azure-foundry-agentic-finetuning-platform-* — see Live deployment)
├── PLAN.md, TASKS.md, COSTS.md, CHANGELOG.md    build record — architecture decisions, cost approval, phase gates
```

---

Generated with [Claude Code](https://claude.com/claude-code) from two
K21Academy Microsoft Foundry lab guides. See `PLAN.md` for the full set of
architecture decisions and their rationale, and `CHANGELOG.md` for what
shipped when.

# Azure Foundry — Agentic Fine-Tuning & Model Evaluation Platform

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

## Troubleshooting — Known Issues & Workarounds

Everything below was found by actually running this project against live
Azure, not by inspection — mock mode's fixtures are always "nice" data
(completed runs, real numbers everywhere), so none of these surfaced until
real Azure responses hit real edge cases.

### 1. Terraform: Hub-based Foundry project resource is the wrong architecture
**Symptom:** `azurerm_ai_foundry_project.ai_services_hub_id` — "Expected a
Workspace ID that matched .../Microsoft.MachineLearningServices/workspaces/…"
**Root cause:** That resource expects a Machine Learning Workspace-based
"Hub" — the older Foundry architecture. This project's Foundry project sits
directly under an `azurerm_cognitive_account` (AIServices kind), a flatter,
modern layout the Hub resource doesn't support.
**Fix:** Switched to `azurerm_cognitive_account_project`, which also requires
its own `identity { type = "SystemAssigned" }` block (discovered via
`terraform providers schema -json`, since docs across API versions were
inconsistent).

### 2. Fine-tuning silently trains on the unsupported "Standard" tier
**Symptom:** `create_sft_job` fails with a generic `"The fineTuningJob field
is required"` error that has nothing to do with the actual problem.
**Root cause:** The GA API version (`2024-10-21`) has no `trainingType` field
at all — it silently defaults to `"Standard"`, which `gpt-4.1` doesn't
support for Supervised fine-tuning. The next API version
(`2025-04-01-preview`) does support it, but **only** with the exact string
`"developerTier"` (camelCase, "Tier" suffix) — any other casing or value
(`"Developer"`, `"GlobalStandard"`, nesting under `model_settings`, all
suggested by secondary docs during research) reproduces the same confusing
error.
**Fix:** Pin `api_version = "2025-04-01-preview"` and pass
`extra_body={"trainingType": "developerTier"}` explicitly. Root-caused by
testing raw REST payloads with `httpx` directly against Azure, bypassing the
`openai` SDK — the only way to isolate SDK behaviour from the actual API
contract. This accidentally created a real (harmless, $0-spend) test job
during that experimentation; cancelled after user confirmation via `az rest`.

### 3. `deploy_finetuned_model`'s live branch was a stub — it never called Azure
**Symptom:** A fine-tuning job reaches `succeeded`, but Workflow 3 keeps
reporting "no completed, deployed fine-tuned model available yet" forever.
**Root cause:** The live code path claimed `"note": "Auto-deployment is
enabled on the job, so Terraform/Foundry creates this deployment on
completion"` — but `create_sft_job` never actually sets auto-deploy. The
function returned a fabricated success payload without making any Azure
call.
**Fix:** Rewrote it to make a real ARM `PUT` against the Cognitive Services
deployments API (`azure_foundry.deploy_model`), gated on the job actually
having a `fine_tuned_model` (i.e. genuinely `succeeded`).

### 4. The whole backend freezes during any long-running workflow
**Symptom:** Clicking "Run Workflow 1" appears to hang — no response, no
error, page looks frozen for 30-60 minutes.
**Root cause:** The Azure OpenAI SDK calls inside the async MCP tool handlers
were **synchronous**, executed directly on the single asyncio event loop.
Workflow 1's evaluation makes ~700+ sequential calls; each one blocked the
*entire* backend process — not just that request, every request, including
unrelated health checks — for as long as it ran.
**Fix:** Wrapped every blocking Azure SDK call in `asyncio.to_thread(...)` at
the MCP server boundary, in both `foundry_inference/server.py` and
`foundry_finetune/server.py`. Verified by polling a live job's progress
endpoint *while* a chat-completion call was mid-flight — confirmed the
server stayed responsive.

### 5. A page refresh loses a run forever, even though it keeps billing
**Symptom:** A 45-minute live run completes successfully server-side, but if
the browser tab is refreshed (or the request otherwise dropped) before the
response arrives, the result is gone — unrecoverable, even though the run
already spent real tokens.
**Root cause:** `POST /agent/invoke` was a single blocking request/response —
the result only ever existed in that one HTTP round-trip. Nothing persisted
it server-side.
**Fix:** Added an in-process job registry (`src/app/jobs.py`, contextvar-based
so deeply-nested service code can report progress without threading a job
object through every function signature) plus `POST /agent/invoke/start` +
`GET /agent/jobs/{id}`. The frontend stores the job id in `localStorage` on
start and reconnects to it on mount — a refresh (or reopening the tab later)
resumes the same job instead of losing it.

### 6. `upload_training_file` races Azure's async file processing
**Symptom:** `create_sft_job` fails with `{'code': 'invalidPayload',
'message': 'The specified file reference must point to a completed file
import.'}` — reproduces on essentially every run.
**Root cause:** Azure's file upload API returns synchronously as soon as the
bytes are received, but validates the file *asynchronously* in the
background. Referencing the file id immediately (the natural thing to do
with a synchronous-looking API) races that background step.
**Fix:** `upload_training_file` now polls `client.files.retrieve(id).status`
until it reaches `processed` (bounded at 60s) before returning the id.

### 7. Deploying immediately after submitting a job always fails, and crashed the whole run
**Symptom:** `Blocked: 'deployment_type'` — the whole Workflow 2 run fails
right after a real fine-tuning job is successfully submitted.
**Root cause:** `run_finetune` chains `deploy_finetuned_model` immediately
after job submission in the same request. Since training takes ~60 minutes,
that deploy call is *always* too early and returns a graceful `{"error":
...}` dict (see #3's fix) — but the calling code indexed straight into
`deployment['deployment_type']` without checking for that key first, turning
an expected, recoverable state into an unhandled `KeyError` that crashed the
entire run (losing the job-submission results that *had* succeeded).
**Fix:** Check for `deployment.get("error")` and degrade gracefully — keep
every result that did succeed (validation, cost estimate, upload, job
status, logs) and simply note that deployment isn't ready yet.

### 8. Frontend crashes to a blank page on any partial/failed result
**Symptom:** Page goes fully blank (white screen) partway through a run, no
visible error, no console message shown to the user.
**Root cause:** Every workflow page rendered its results unconditionally on
`{result && (...)}`, assuming any truthy `result` has the full expected
shape. A run that fails mid-way (see #7) can leave `result` truthy but
missing fields the JSX indexes into unconditionally (e.g.
`result.validation.is_valid` on an object with no `validation` key) — React
has no error boundary configured, so one bad property access unmounts the
entire tree. Reproduced and root-caused with a real headless browser
(Playwright), not by reading code — the actual stack trace pointed at the
exact line.
**Fix:** Guard on a field that only exists once the run has genuinely reached
that stage (`result && result.validation`, `result && result.catalog`,
`result && result.report`), and surface `blockedError` visibly on every
workflow page instead of only one of them.

### 9. `null` metrics on a freshly-submitted job crash the render
**Symptom:** Same blank-page symptom as #8, on a *successful* run this time.
**Root cause:** `result.status.metrics.trained_tokens.toLocaleString()` — a
job that's a few seconds old legitimately has `trained_tokens: null` (no
training steps have run yet). Calling a method on `null` throws. This was
invisible in mock mode because its fixture is always a *completed* run with
real numbers — the TypeScript interface declared these fields as plain
`number`, which was simply inaccurate for live data, and `tsc` had no way to
catch a lie in a hand-written type.
**Fix:** Declared the metrics fields honestly as `number | null` and used
optional chaining / nullish coalescing at every call site.

### 10. A backend restart makes a real, working deployment invisible
**Symptom:** Workflow 3 fails with "no completed, deployed fine-tuned model
available yet" even though a fine-tuned deployment is live and serving
requests on Azure right now.
**Root cause:** The mapping from "which deployment is the fine-tuned one" was
kept only in an in-process module-level cache (`_last_live_job_id` /
`_last_live_deployment`) — correct within one process's lifetime, but wiped
by every backend restart (and this session needed several, chasing other
fixes).
**Fix:** Added `azure_foundry.list_finetuned_deployments()`, an ARM query
that finds real Cognitive Services deployments whose model name contains
`.ft-` (Azure's fine-tuned-model naming convention). `get_job_status` now
falls back to this when it has no cached job to work from, instead of
reporting nothing is available.

### 11. `tsc --noEmit -p .` was silently checking nothing
**Symptom:** Multiple frontend bugs (#8, #9) shipped despite "clean" `tsc`
output immediately beforehand.
**Root cause:** The project uses TypeScript's composite/project-references
setup (`tsconfig.json` → references `tsconfig.app.json` +
`tsconfig.node.json`). Running `tsc --noEmit -p .` against the root config
without `-b` (build mode) is a silent no-op — it doesn't check anything, and
exits 0 regardless of real errors.
**Fix:** Point directly at the leaf config: `tsc --noEmit -p
tsconfig.app.json`. Re-running this way immediately surfaced a real error
(`is_terminal` missing from a hand-written interface) that the broken command
had been hiding.

## Lessons Learned

1. **Mock-mode fixtures cannot substitute for live-mode testing, ever** —
   every bug in this section was invisible to 78 passing unit tests and
   extensive mock-mode use, because fixture data is always well-formed,
   complete, and fast. Only real Azure responses have `null` metrics,
   async processing races, and "not ready yet" states.
2. **A synchronous SDK call inside an `async def` handler blocks the entire
   process, not just that request** — always wrap blocking I/O (`openai`'s
   sync client, `httpx.get`/`.put`, anything without `await`) in
   `asyncio.to_thread(...)` when it lives inside an async server.
3. **A single blocking request/response is the wrong shape for anything that
   can take longer than a user will wait** — background job + poll (with a
   persisted/resumable job id) is the only pattern that survives a page
   refresh or a lost connection, and it should be the default for any run
   measured in minutes, not an afterthought.
4. **Never index into a dict that might be an `{"error": ...}` payload
   without checking first** — a function that can return either a success
   shape or a graceful error shape needs every caller to check
   `.get("error")` before assuming the success keys exist. One missed check
   turns an expected, documented condition into an unhandled crash.
5. **Don't trust a hand-written TypeScript interface to be honest about
   nullability** — it compiles either way; only real (live-mode) data
   exposes the lie. When a field is genuinely optional/nullable on the wire,
   declare it that way, don't assume the happy-path shape from whatever
   fixture you tested against.
6. **A composite/project-references `tsconfig.json` needs `-b` (build mode)
   to actually check anything** — `tsc --noEmit -p .` against the root
   config silently checks nothing and exits 0. Point directly at the leaf
   config (`tsc --noEmit -p tsconfig.app.json`) for a real check, or verify
   the command actually catches a deliberately-introduced error at least
   once.
7. **In-process caches are invisible across restarts — always add a
   query-Azure-directly fallback for anything load-bearing** — a
   module-level Python variable is fine as a fast path, but if losing it
   means a real, working, already-paid-for resource becomes unusable by the
   app, that's a bug, not an acceptable limitation.
8. **An API that returns synchronously can still be asynchronous underneath —
   verify, don't assume** — Azure's file upload returns immediately but
   validates in the background; referencing the result too early races it.
   When a "create X" call is suspiciously fast for what it claims to do,
   check whether there's a status field to poll before trusting the result
   is ready to use.
9. **A stub that fakes success is worse than one that raises** — the original
   `deploy_finetuned_model` returned a fabricated "Triggered" success payload
   without calling Azure at all, which hid the real gap (no deployment ever
   created) until it was root-caused independently, much later than an
   honest `NotImplementedError` would have surfaced it.
10. **Reproduce frontend bugs with a real browser, not just by reading
    code** — a headless-browser reproduction (Playwright) gave an exact
    stack trace and line number for each crash in this section; guessing
    from the component source alone would have been slower and less certain.
11. **Always confirm before cancelling/deleting anything real, and never
    work around a permission-classifier block** — an accidental test job
    created during raw-payload experimentation was disclosed immediately,
    left running until explicit user confirmation, and cancelled via a
    sanctioned tool (`az rest`) once approved — never by finding a way
    around a blocked action.

## Project layout

```
├── src/app/            FastAPI app: routers, LangGraph agents, Pydantic v2 schemas, config, telemetry
├── mcp_servers/         3 MCP servers (catalog, finetune, inference) — 19 tools total
├── frontend/            Vite + React 18 + TypeScript, Contoso theme
├── infra/terraform/      Budget-first IaC: budget → Foundry account/project → model deployments
├── data/                Lab dataset + 7 additional converted datasets + fixtures for mock mode
├── tests/               unit / smoke_pre / smoke_post_provision / smoke_post_run / smoke_post_teardown
├── .github/workflows/    ci / deploy / teardown
├── PLAN.md, TASKS.md, COSTS.md, CHANGELOG.md    build record — architecture decisions, cost approval, phase gates
```

---

Generated with [Claude Code](https://claude.com/claude-code) from two
K21Academy Microsoft Foundry lab guides. See `PLAN.md` for the full set of
architecture decisions and their rationale, and `CHANGELOG.md` for what
shipped when.

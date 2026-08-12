# PLAN.md — architecture and component inventory

## Source of truth

Two K21Academy hands-on lab guides (in `../assests/references/`), both of which
are 100 % Azure AI Foundry **portal click-throughs** containing no code, no IaC
and no CLI path. This project replaces every one of those manual clicks.

| Lab | Sections automated | Becomes |
|---|---|---|
| *Explore and compare models* (51 pp.) | §7 catalog · §8 leaderboard · §9 deploy · §10 playground compare · §11 synthetic evaluation | **Demo 1** |
| *Fine-tune a language model* (46 pp.) | §7 deploy baseline · §8 SFT job · §10 training file · monitoring | **Demo 2** |
| Both | §9 base prompts vs §11 fine-tuned prompts | **Demo 3** |

## Determinations

| Item | Value | How determined |
|---|---|---|
| Language | Python 3.12+ (3.13.13 local) | `python3 --version`; pinned `requires-python = ">=3.12"` |
| Cloud | Azure | Both guides are Azure AI Foundry end to end |
| Region | **eastus2** | Every portal screenshot in *both* PDFs shows East US 2; gpt-5.4 family is Global Standard there |
| Frontend | React 18 + TypeScript + Vite | Project default; explicitly not Streamlit |
| IaC | Terraform 1.15 | Project default |
| Scenario count | **3 demos from 2 guides** | Guides' own TOCs. Demo 3 is the cross-cutting baseline-vs-fine-tuned comparison both guides build toward |
| Repetition structure | One config-driven pipeline, not 3 copies | All three demos are `agent → MCP tool → Foundry`, differing only in tool set and config |

## Architecture

```
   React + TypeScript (Contoso theme) — fixed 18 % sidebar, static auth, 3 demo triggers
                                  │ REST
                    ┌─────────────▼─────────────┐
                    │      FastAPI (src/app)     │
                    └─────────────┬─────────────┘
                    ┌─────────────▼─────────────┐
                    │  LangGraph Orchestrator    │  supervisor; routes by intent
                    └──┬──────────┬──────────┬──┘
              ┌────────▼──┐ ┌─────▼─────┐ ┌──▼──────────┐
              │ Discovery │ │ FineTune  │ │ Comparison  │  sub-agents
              └────────┬──┘ └─────┬─────┘ └──┬──────────┘
                       │      MCP tool calls  │
              ┌────────▼──┐ ┌─────▼──────┐ ┌──▼──────────┐
              │mcp-catalog│ │mcp-finetune│ │mcp-inference│  3 MCP servers
              └────────┬──┘ └─────┬──────┘ └──┬──────────┘
                       └──────────┼───────────┘
                     mock fixtures ⇄ live Azure SDK   ← DEMO_MODE selects backend
                    ┌─────────────▼─────────────┐
                    │ Azure AI Foundry (eastus2) │
                    └───────────────────────────┘
```

**Design rule:** `DEMO_MODE` selects the *backing implementation*, never the tool
schema. Mock and live expose byte-identical MCP tool signatures, so the agent
graph is untouched by the switch and mock runs are a faithful rehearsal.

**Why MCP rather than plain function calls:** the three servers are standalone
stdio MCP servers, so the same Azure Foundry tooling is consumable by Claude
Desktop/Code or any MCP client — the automation outlives this particular UI.

## Data flow

1. UI triggers a demo → `POST /agent/invoke {demo, prompt}`.
2. Orchestrator classifies intent → routes to one sub-agent.
3. Sub-agent calls MCP tools; each result is validated by Pydantic v2 at the boundary.
4. OTel spans stream to the terminal **and** Application Insights.
5. Structured result returns to the UI; schema violations render as a visible
   feature, not a hidden error.

## Component inventory

| Component | Path | Responsibility |
|---|---|---|
| Config | `src/app/config.py` | Pydantic-settings; single source for env |
| Telemetry | `src/app/telemetry.py` | OTel tracer, console + Azure Monitor exporters |
| Schemas | `src/app/schemas/` | JSONL records, FT jobs, evals, leaderboard, comparison |
| MCP servers | `mcp_servers/*/server.py` | Catalog, fine-tune, inference tool surfaces |
| MCP client | `src/app/mcp_clients/` | In-process registry + stdio session manager |
| Agents | `src/app/agents/` | Orchestrator + 3 sub-agents, LangGraph `StateGraph` |
| Services | `src/app/services/` | `azure_foundry.py` (live), `fixtures.py` (mock), `comparison.py` (behavioural scoring) |
| Routers | `src/app/routers/` | `/catalog /finetune /inference /agent /auth /health` |
| IaC | `infra/terraform/` | RG, Foundry, deployments, budget, App Insights |
| Frontend | `frontend/` | Contoso UI |

## Deployments provisioned

| Deployment | Model | Version | SKU |
|---|---|---|---|
| `gpt-4.1` | gpt-4.1 | 2025-04-14 | GlobalStandard |
| `gpt-5.4` | gpt-5.4 | 2026-03-05 | GlobalStandard |
| `gpt-5.4-mini` | gpt-5.4-mini | 2026-03-17 | GlobalStandard |
| `…ft-travel` | fine-tuned gpt-4.1 | — | **Developer** |

## PDF contradictions and how they are resolved

The guides contain internal inconsistencies. Each is resolved deliberately:

| # | Contradiction | Resolution |
|---|---|---|
| 1 | §11.1 text says select `gpt-5.2`; screenshot shows `gpt-5.4` | Use **gpt-5.4** (typo in text) |
| 2 | §15 summary says `gpt-4o-mini`; body uses `gpt-5.4-mini` | Use **gpt-5.4-mini** |
| 3 | §11.4 says remove the Agents evaluators, but results show `TaskCompletion`/`IntentResolution` and `704/720` = 16×45 | Default to **all 16 evaluators**; `include_agent_evaluators` flag exposes the other behaviour |
| 4 | RG named `k21-aiproject` in text, `rg-k21-aiproject` in screenshots | Use `rg-{base}-{suffix}` convention |
| 5 | Region never stated in prose | **eastus2**, from screenshots |
| 6 | Hyperparameters never shown (left at API defaults) | **Pinned explicitly** for reproducibility; documented as a deliberate divergence |
| 7 | Cluster analysis shows 16 samples for a 45-row run | Cluster view covers failing samples only; modelled as such |

## Manual prerequisites (cannot be automated)

1. Azure subscription (Free-Tier or Paid) with **Owner or Contributor**.
2. `az login` — interactive.
3. Quota for the gpt-5.4 family in eastus2.
4. gpt-4.1 fine-tuning access enabled on the subscription.

These are checked, not assumed: `tests/smoke_pre` fails with a specific message
for each.

## Naming and the auto-increment override

Requirement: never halt on a name collision; append `-v1`, `-v2`, …
This overrides the standing rule against rename-on-collision, so it is
implemented defensively in `infra/terraform/scripts/next_suffix.py`:

- The suffix is resolved **once**, recorded in `.suffix.lock`, and reused
  thereafter — so `terraform apply` converges and does not drift.
- A name already taken **by this project** (matched on the `managed_by` tag)
  returns the *same* suffix rather than incrementing.
- Only a collision with a *foreign* resource advances the counter.
- `make teardown` sweeps **every** suffix bearing the project tag, so an orphan
  from a lost state file is still destroyed.
- `tests/smoke_post_teardown` fails the build if anything tagged survives.

Residual risk, stated plainly: losing both remote state and `.suffix.lock` will
mint a new suffix. Because every resource here is $0/hour, the blast radius is
$0 while idle — which is what makes the override tolerable.

## Estimated file count

~85 files.

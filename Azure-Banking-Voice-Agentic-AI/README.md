# Azure Banking Voice Agentic AI
### Azure Communication Services + Azure OpenAI Realtime · Canada Central · $25/mo Hard Ceiling
### Voice-First Banking IVR · Auth Gate Integrity by Construction · PIN Never Reaches the Model

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white&labelColor=1a1a2e)
![Azure](https://img.shields.io/badge/Azure-ACS_·_OpenAI_·_Container_Apps-0078D4?style=flat&logo=microsoftazure&logoColor=white&labelColor=1a1a2e)
![Region](https://img.shields.io/badge/Region-Canada_Central-D22128?style=flat&labelColor=1a1a2e)
![Phase](https://img.shields.io/badge/Phase-0_of_8_(in_progress)-f0a020?style=flat&labelColor=1a1a2e)
![Budget](https://img.shields.io/badge/Ceiling-$25%2Fmo_(spendingLimit%3A_Off)-2ea043?style=flat&labelColor=1a1a2e)

> **No build/CI badge, deliberately.** Phase 0 is provisioning and meter-measurement only — no agent
> code exists yet to lint, type-check, or test. `docs/PLAN.md`'s testing strategy (L0–L4) is designed
> but nothing runs against it before Phase 2. A badge here would be reporting a suite that doesn't
> exist.

## Project Description

A production-grade prototype IVR: **a real Canadian phone number that a caller dials to reach a
banking voice agent**, built on Azure Communication Services + Azure OpenAI's realtime API, under a
hard **$25/month** ceiling that Azure itself will not enforce (`spendingLimit: Off`, confirmed on the
subscription).

**This is the deliberate Azure counterpart to
[`AWS-Insurance-FNOL-Voice-Agentic-AI`](../AWS-Insurance-FNOL-Voice-Agentic-AI)** — same portfolio,
same rigor, different cloud, different domain. Symmetry is kept where a reviewer would expect to see
it (`docs/adr/`, phase docs, `PROJECT_STATE.md`, `COSTS.md`, commit convention) and dropped where the
clouds genuinely differ (Bicep instead of Terraform; a DTMF PIN path with no FNOL analog).

**Two reference repositories were scoped before any code was written**, and contributed far less than
the brief assumed: `AI-Powered-Call-Center-Intelligence` turned out to have zero telephony code (audio
never reaches its backend — the browser talks to Azure Speech directly), and `azure-openai-agents`
is a text-only demo with a fabricated-telemetry bug and a silent-fallback bug, both named as hard
exclusions below. Full inventory: `docs/PLAN.md`, "Reuse reality."

**The safety property this project is built around is structural, not prompted**, mirroring FNOL's own
design stance: whether a tool call reaches `mock-core-banking` is a deterministic function of
`(tool_name, session.auth_state)`, enforced server-side in `dispatch/gate.py` — not something the model
is asked nicely to respect. That gate does not exist yet; it ships in Phase 2, deny-all-by-default.

## Current status — Phase 0, in progress

**This is infrastructure-and-measurement work, not a working agent.** Nothing past a throwaway echo
WebSocket exists yet. Read this section literally: it says what's real today, not what's designed.

- **Purchased**: one Canadian phone number, `+17059100383` (705 — North Bay/Sault Ste Marie, ON),
  `$1.00 USD/mo`, purchased 2026-08-20. Per **R-09** (`docs/PLAN.md`), this number is never released by
  any script, at any phase, for any reason — a lost number in ACS's Canadian geographic inventory may
  not be replaceable (see "Known issues" below).
- **Created, consumption-billed, $0 so far**: an Azure OpenAI resource with `gpt-realtime-mini`
  (`2025-10-06`, GA, `NoAutoUpgrade`) deployed, and an Azure Communication Services resource.
- **Not yet deployed**: the Phase 0 echo app to Container Apps (Stage 12) — currently **blocked** on a
  container image architecture mismatch (an Apple Silicon build produced `arm64`; Container Apps
  requires `linux/amd64`), compounded by an unresolved question over which of two on-disk `echo-app`
  directories the wizard script actually builds from. Full detail: `docs/phase0/findings.md`.
- **Zero test calls made.** No transport RTT baseline, no DTMF-during-streaming evidence, no Container
  Apps idle-vs-active billing measurement exist yet — all of that is Phase 0's own exit gate, not met.
- **No agent code exists.** `voice-agent/`, `mock-core-banking/`, `dispatch/gate.py`, the realtime
  session client, and the IaC (Bicep + Typer CLI) described in "Project layout" below are Phase 1+ and
  have not been started.

**Phase 0's exit gate** (`docs/PLAN.md`): `COSTS.md` carries measured meters (not estimates) and a
measured transport RTT baseline with its sample size stated; ADR-001 and ADR-002 exist (they do —
`docs/adr/`); R-08's demo-runs/month figure is computed from measured meters. None of this is met yet —
Stage 12 hasn't produced a successful deploy.

## The problem this is built to solve

A banking IVR is safety-sensitive in a way a generic voice bot is not: the caller is authenticating
with money on the line, and a model that can be talked into skipping a check is a model that will be.

| Pain point | Impact |
|---|---|
| Auth as a model decision | Anything a prompt decides to allow, a prompt can be talked out of denying |
| PIN entry over voice/DTMF | A PIN that reaches a transcript, a log line, or an LLM context window is a PIN that has already leaked |
| Model pin drift | A realtime deployment silently redeployed onto an unvetted model version is an unreviewed change to what the bank is exposing to callers |
| No spend ceiling from the platform | `spendingLimit: Off` — Azure will not stop a runaway call or a cost bug; something in this codebase has to |
| Number irreplaceability | ACS's Canadian geographic phone-number inventory has been observed losing entire localities in ~20 minutes — a released number may not have an equivalent replacement |

The first two are why **B1** (Auth Gate Integrity) and **B2** (PIN Confidentiality) exist as named,
adversarially-tested, CI-blocking constraints rather than design guidance — see "Project invariants."

## 🛠️ Tech Stack

Reflects what Phase 0 has actually decided and verified live against Microsoft's own APIs — not
aspirational. Items not yet built are marked.

| Layer | Technology | Status |
|---|---|---|
| **Telephony** | Azure Communication Services, Call Automation + bidirectional media streaming | ACS resource created; PSTN number purchased |
| **AI platform** | Azure OpenAI realtime API, `gpt-realtime-mini` (`2025-10-06`, GlobalStandard, `NoAutoUpgrade`) | Deployment live; no realtime session has been opened yet |
| **Compute** | Azure Container Apps, `min-replicas=1`, 0.25 vCPU / 0.5 GiB | Environment not yet created — Stage 12 blocked |
| **Region** | Canada Central, no fallback chain | Confirmed live: realtime models exist in exactly 6 regions worldwide; Canada Central is one |
| **Container registry** | Docker Hub free tier (private repo), deliberately not ACR | Phase-0-only choice — avoids `az containerapp up`'s auto-provisioned ~$5/mo ACR Basic tier |
| **IaC** | Bicep, one module per resource | **Not started** — Phase 0 provisions via raw `az` CLI in bash; Bicep lands Phase 7 |
| **Deploy tooling** | Python Typer CLI wrapping `az` + Bicep, `deployment_state.json` checkpointing | **Not started** — Phase 0 uses `docs/phase0/wizard/*.sh` instead |
| **Orchestration (planned)** | Persistent realtime session per call; agent swap via `session.update`; explicit FSM + `AgentSpec` table | **Not started** — Phase 2 |
| **Auth (planned)** | Spoken card last-4 + DOB (KBA), then PIN via DTMF | **Not started** — Phase 4 |
| **Observability (planned)** | Azure Monitor / Application Insights via the **Azure Monitor OpenTelemetry Distro** — Azure-native, not a third-party SaaS. Per-call traces correlated on `x-ms-call-correlation-id`, PII redaction before export | **Not started** — Phase 6. Tooling pinned 2026-08-21 — see "Engineering decisions" below |
| **Testing (planned)** | L0 units → L4 live-model redteam, `FakeAcsTransport` + `FakeRealtimeServer` | **Not started** — Phase 2 builds the fakes |

## Architecture

The target architecture (`docs/PLAN.md`), reproduced here because it's the clearest single artifact
in the project — **only the top path (Caller → ACS → Container App) exists today**, and even that path
has not completed a successful deploy yet:

```
Caller (Ontario mobile)
    │  dials Canada local number (705, North Bay/Sault Ste Marie)
    ▼
Azure Communication Services ──Event Grid──► POST /api/incoming-call
    │                                              │ answer call
    │  bidirectional media streaming (WSS)         │
    │  audioFormat: Pcm24KMono                     │
    │  enableDtmfTones: true                       ▼
    └──────────────────────────────────►  Container App (Canada Central)   ◄── NOT YET DEPLOYED
                                            min-replicas=1, 0.25 vCPU / 0.5 GiB
         {"kind":"AudioData","audioData":{"data":"<b64 PCM>"}}
         {"kind":"DtmfData","dtmfData":{"data":"3"}}   ← PIN never reaches the LLM
                                                   │
                          wss://{res}.openai.azure.com/openai/v1/realtime
                                    ?model=gpt-realtime-mini
                          (Entra ID, scope https://ai.azure.com/.default)          ◄── NOT BUILT (Phase 2)
                                                   │
                                    ┌──────────────┴──────────────┐
                                    │  RealtimeSession            │
                                    │  session.update → agent swap│
                                    └──────────────┬──────────────┘
                                                   │ tool call
                                                   ▼
                                    ┌──────────────────────────────┐
                                    │  dispatch/gate.py   ◄── B1   │  ← THE control    ◄── NOT BUILT (Phase 2)
                                    └──────────────┬───────────────┘
                                                   ▼
                                    mock-core-banking (own Container App)              ◄── NOT BUILT (Phase 3)
                                    FastAPI + SQLite, real network hop
```

**Observability, not yet wired into the diagram above because it doesn't exist yet (Phase 6):** every
box above will emit OpenTelemetry via the Azure Monitor OpenTelemetry Distro (Container Apps has a
built-in OTel agent) into an Application Insights resource in the same Canada Central footprint —
Azure-native, not a third-party SaaS. Evaluated against LangFuse and rejected for that phase's use:
`docs/PLAN.md`, "Observability tooling."

**Region & residency, verified live, not assumed:** realtime models exist in exactly six regions
worldwide (`canadacentral`, `centralus`, `eastus2`, `francecentral`, `swedencentral`, `southindia`).
Canada Central was chosen over the original East US 2 assumption because it's physically Toronto — the
same metro as the caller — and because Global-type deployments **can still process outside the
resource's region** even when data-at-rest stays Canadian (`docs/adr/ADR-001-data-residency.md`
states this both ways deliberately). Full detail: `docs/PLAN.md`, "Region & data residency."

## Build status

**8 phases past Phase 0, none started.** Phase 0 itself is a single gated phase with 12 internal
stages, currently blocked at Stage 12.

| Phase | Status |
|---|---|
| **0 · Provisioning & Meter Spike** | 🟡 **in progress — Stage 12 fix applied 2026-08-21 (arch mismatch + `ECHO_DIR` misdirection), not yet re-run** |
| 1 · Duplex audio path (echo call, no agent) | ⬜ not started |
| 2 · Realtime session + agent core + `dispatch/gate.py` + test harness | ⬜ not started |
| 3 · `mock-core-banking` (FastAPI + SQLite) | ⬜ not started |
| 4 · Auth gate permissions (KBA + DTMF PIN) — B1/B2 threshold | ⬜ not started |
| 5 · Intents + cost controls — B5 frozen here | ⬜ not started |
| 6 · Observability (OTel, PII redaction) | ⬜ not started |
| 7 · IaC completion & CI/CD (Bicep, Typer CLI, GitHub OIDC) | ⬜ not started |
| 8 · Post-call analytics, evals & docs | ⬜ not started |

### Known issues — all open, all logged with evidence in `docs/phase0/findings.md`

1. **Container image architecture mismatch, blocking Stage 12 — fix applied 2026-08-21, not yet
   re-run.** A local `docker build` on Apple Silicon produces `arm64`; Container Apps rejects it,
   requiring `linux/amd64`. `01-provision.sh` now uses `docker buildx build --platform linux/amd64
   --push`, plus a `docker buildx imagetools inspect` gate that fails loudly, before any Azure spend,
   if `linux/amd64` isn't actually in the pushed manifest.
2. **`ECHO_DIR` misdirection — resolved 2026-08-21.** `01-provision.sh`'s `ECHO_DIR` used to resolve
   (correctly, by its own math) to `docs/phase0/echo-app/`, a second, untracked directory that a prior
   run of Stage 11 populated from the original broken template — no B2 gating at all, DTMF tone values
   logged unconditionally. The git-tracked, human-reviewed `docs/echo-app/` this session actually fixed
   was never what the script built. Had this shipped on `amd64` hardware instead of Apple Silicon, it
   would have deployed green and stayed unnoticed for the full 72h measurement window — the arch
   mismatch above is the only reason it was caught. Fixed by anchoring `ECHO_DIR` to the git repo root
   (`git rev-parse --show-toplevel`, not a relative `../..` chain) pointing at `docs/echo-app/`, with a
   hard assertion — the target must exist *and* be git-tracked, or the script refuses to proceed — and
   no template-regeneration fallback left in the script at all. `docs/phase0/echo-app/` deleted.
3. **ACS's Canadian geographic phone-number inventory is measurably volatile.** One locality (Guelph,
   ON) was live-purchasable at one check and gone ~20 minutes later; the nationwide locality count
   dropped 10→8 within a single session. This is why R-09 (number irreplaceability) exists as a hard
   rule, not a convenience.
4. **An auto-provisioned Log Analytics workspace survives teardown**, unaccounted for by name in
   `COSTS.md`/`docs/PLAN.md`. Verified against live Azure Retail Prices data: at this project's actual
   log volume it costs $0 in practice, but nothing in the cost tooling would notice if that changed.
5. **A stale machine-level `az` CLI default (`defaults.location=eastus`)** silently empties
   `az resource list` for this project's `canadacentral`/`global` resources on the machine this project
   is run from. No `create` call site is exposed; two `on_error` trap display bugs are.
6. **The Models API rate-limit field's meaning is not confirmed** — `10 requests/60s` on the pinned
   deployment doesn't reconcile against Microsoft's documented Quota Tier table, which doesn't name
   `gpt-realtime-mini` at all. Circumstantial evidence points to "request = new session," not
   independently confirmed.
7. **`gpt-realtime-1.5`, B3's documented successor model, has never actually been booted against
   anything** — it depends on `FakeRealtimeServer`, which doesn't exist until Phase 2.

## Project invariants

Named, measurable constraints — not aspirational, and not yet all enforceable, since the code paths
some of them govern don't exist yet. Full detail: `CLAUDE.md`, `docs/PLAN.md` "Named constraints."

| ID | Invariant | Target | Enforced at |
|---|---|---|---|
| **B1** | **Auth Gate Integrity** — zero authenticated-only tool calls reach the core-banking client while unauthenticated | 0 breaches / ≥120 adversarial cases | L1, blocking CI — **Phase 2** |
| **B2** | **PIN Confidentiality** — the DTMF PIN never appears in any transcript, log line, span, or record | 0 occurrences, artifact scan | L0+L1, blocking CI — **Phase 4** |
| **B3** | **Model Pinning** — no code path can instantiate a realtime deployment outside an allowlist keyed on (name, version) | 0 violations | startup guard reading the *live* deployed version + CI static check + Bicep — **Phase 2** |
| **B4** | **Cost Ceiling** — no call exceeds 5 min / 20 turns; daily aggregate cap fails **closed** | 0 overruns, 0 fail-open events | L1, blocking CI — **Phase 5** |
| **B5** | **Turn Latency**, p95 | Provisional after Phase 2 (N≥100 turns); frozen after Phase 5 | L3 + production OTel |
| **R-09** | **Number irreplaceability** — the phone number is never released, by any script, at any phase | 0 release calls in any teardown path | Verified in `04-teardown-and-r08.sh`; standing `CLAUDE.md` stop condition |

`spendingLimit: Off` is confirmed on the subscription. **Azure will not stop spend at any threshold —
B4 is the only brake that exists**, and it isn't built yet.

## Cost — estimated vs. actual

| Item | Estimated (`docs/PLAN.md`) | **Actual to date** |
|---|---:|---:|
| Canada local phone number | $1.00/mo | **$1.00/mo, purchased 2026-08-20** — first bill date not yet confirmed (no next-bill-date field in the API) |
| Azure OpenAI resource + deployment | $0 fixed, consumption-only | **$0** — zero tokens processed, no realtime session opened yet |
| ACS resource | $0 fixed, consumption-only | **$0** — zero PSTN/streaming minutes used yet |
| Container Apps, `min-replicas=1`, 0.25 vCPU/0.5 GiB | $4.29/mo idle – $14.31/mo active | not yet deployed |
| Auto-provisioned Log Analytics workspace | not in original budget | **$0 in practice** (verified against live Retail Prices data at this project's log volume) — see Known issues |
| Application Insights (Phase 6, not yet created) | not yet estimated | **$0 projected** — same Log Analytics meter, permanent 5 GB/month free ingestion allowance (verified live, Microsoft's own pricing page), this project's call volume nowhere close to it |
| **Monthly ceiling** | | **$25.00**, unenforced by the platform |

Full per-meter log with raw API evidence: [`COSTS.md`](COSTS.md). Free-tier-promotion suppression risk
(the subscription has an active `freetier` promotion through 2027-02-28, which can make Cost Analysis
figures read as $0 for reasons unrelated to actual usage) is tracked there and must be ruled out via the
Azure Portal's Free Services blade before any dollar figure from this project is trusted.

### Budget structure (planned, from `docs/PLAN.md` — not yet measured)

| Component | Rate |
|---|---:|
| PSTN inbound, Canada Geographic | $0.0085/min |
| ACS audio streaming | $0.0040/min |
| `gpt-realtime-mini` (floor estimate) | $0.0090/min |
| **Per-minute floor** | **$0.0215/min** |

At the estimated fixed + eval-ceiling cost, roughly **2–10.6 hours/month** of actual call time is left
under the $25 ceiling — the low end assumes the Container App bills at its active rate continuously;
Phase 0's own job is to measure which end of that range is real (R-04).

## Prerequisites

- **Azure CLI**, logged in against a subscription with `Microsoft.Communication` registered
- **Docker Desktop**, with `buildx` (needed to target `linux/amd64` from Apple Silicon — see Known
  issues)
- **A Docker Hub account** — Phase 0 pushes the throwaway echo image to Docker Hub's free tier rather
  than provisioning ACR
- **Python 3.12** — used by the echo app and the repo's own tooling scripts; no project-level
  `pyproject.toml` exists yet (Phase 1+ introduces the real `voice-agent/` package)
- **A phone** to dial the purchased number for Phase 0's manual test-call stage

There is currently no path that runs any part of this project without an Azure subscription — unlike
FNOL, Phase 0 here *is* the live-provisioning work.

## Setup

Nothing here is packaged yet. What exists today runs as a sequence of wizard scripts, not a Python
install:

```bash
cd docs/phase0/wizard
cat README.md   # read this first — what's automated vs. what only you can do, at each of the 4 scripts
```

## Quickstart

The four Phase 0 wizard scripts, run on separate days because Phase 0 has real-world waits (Cost
Analysis ingestion lag, a 72-hour idle-billing observation window) a single sitting can't absorb:

```bash
cd docs/phase0/wizard
./01-provision.sh          # provisioning, up to the hard `APPROVED: Phase 0` gate, then resource creation
# ...dial the number 3 times as instructed...
./02-test-calls.sh         # pulls Container App logs, extracts R-02/R-03/RTT evidence
# ...wait ~24h...
./03-cost-check-24h.sh     # Cost Analysis sanity check against the plan's estimate
# ...wait until ~72h total have passed since 01 ran...
./04-teardown-and-r08.sh   # R-04 verdict, R-08 computation, COSTS.md, teardown (keeps the number)
```

Each script is designed to be safe to re-run; three specific re-run gaps were found and fixed this
session (phone-number re-purchase risk, a duplicate findings.md append, and the echo-app template
regeneration risk described in Known issues). `Makefile` at the project root currently only exposes
`make install-hooks` and `make verify-project-root-scope` — the canonical targets (`install`, `test`,
`lint`, `fixtures`, `deploy`, `teardown`) are added in the phases that build what they need, matching
FNOL's own Makefile discipline: nothing is stubbed and labeled "would work."

## Testing

**Nothing exists to test yet.** `docs/PLAN.md`'s testing strategy is fully designed —
`FakeAcsTransport` + `FakeRealtimeServer` for deterministic L0/L1 CI, recorded-session L2 cassettes,
threshold-gated live-model L3 evals and L4 redteam under their own $6/mo budget ceiling — but none of
it has code behind it. It lands starting Phase 2, when `RealtimeSession` and `dispatch/gate.py` exist
to test in the first place.

## Engineering decisions

Findings from Phase 0 that changed the plan, each with live evidence rather than a prior assumption —
full write-ups in `docs/phase0/findings.md`:

| Challenge | Resolution |
|---|---|
| The original plan assumed a Toronto-area number (416/647/437/905/289) | Confirmed live: Toronto is entirely absent from ACS's Canadian geographic-locality inventory, not just filtered — a country-wide unfiltered query returned no Toronto entry at all. Revised to 705 (North Bay/Sault Ste Marie, ON), the caller's own first preference, live-confirmed purchasable |
| `gpt-realtime-mini`'s `isDefaultVersion` (`2025-12-15`) has only ~4 months of runway | Live Models API query found `2025-10-06` at identical pricing with ~7.5 months' runway and a better request-rate limit; pin revised. B3's startup guard restructured to carry a named successor, keyed on (name, version), reviewed at every phase gate |
| Purchasing a real number, blind, is a one-shot decision against a volatile inventory | A live `Search Available Phone Numbers` call is required immediately before purchase, never a locality/area-code lookup more than a few minutes old — a check that age was itself found empirically (a locality vanished ~20 minutes after appearing available) |
| A Docker Hub access token needs both push and pull scope, easy to under-grant | Corrected mid-session from a wrongly-recorded "Read-only" to "Read & Write" — the same token both `docker push`es and serves as the Container App's `--registry-password` |
| `az resource list` returned an empty result against a resource group with real resources in it | Root-caused via `--debug` REST inspection to a stale machine-level `az config` default (`defaults.location=eastus`) silently injecting a location filter — not an Azure-side discrepancy |
| Phase 6 needed a concrete observability tool, not just "OTel → App Insights" in shape; LangFuse was on the table with API keys offered | **Azure Monitor / Application Insights via the OTel Distro, not LangFuse** — LangFuse Cloud has no Canada hosting region (a real conflict with `ADR-001`'s residency posture), self-hosting would add an unbudgeted resource, and Azure Monitor already has a verified permanent 5 GB/month free ingestion allowance plus native OpenAI Agents SDK tracing support. Full comparison: `docs/PLAN.md`, "Observability tooling" |

## Documentation

| Document | Contents |
|---|---|
| [`PROJECT_STATE.md`](PROJECT_STATE.md) | **Start here.** Current phase, open items, active risks, next actions — fixed-size, current-state only |
| [`CLAUDE.md`](CLAUDE.md) | Stop conditions, named constraints, hard exclusions, skill discipline |
| [`docs/PLAN.md`](docs/PLAN.md) | Scope, architecture, budget, region, phase plan, tracked risks — the source of truth this README summarizes |
| [`COSTS.md`](COSTS.md) | Every measured meter, with raw API evidence, including the free-tier-suppression investigation |
| [`docs/adr/`](docs/adr/) | ADR-001 (data residency), ADR-002 (geography knobs) |
| [`docs/phase0/findings.md`](docs/phase0/findings.md) | Every raw finding this phase has produced, in the order it was found |
| [`docs/phase0/wizard/README.md`](docs/phase0/wizard/README.md) | What each of the 4 wizard scripts does, and what only a human can do |
| [`docs/handoffs/`](docs/handoffs/) | Session handoff documents, written at phase/context boundaries |

This project is one top-level folder in the
[`MAOFILHO/Portfolio-Projects`](https://github.com/MAOFILHO/Portfolio-Projects) monorepo, and the
deliberate Azure counterpart to
[`AWS-Insurance-FNOL-Voice-Agentic-AI`](../AWS-Insurance-FNOL-Voice-Agentic-AI) in the same repo.

## Author

**Marcos Oliveira** — [LinkedIn](https://www.linkedin.com/in/mfilho1/) | [GitHub](https://github.com/MAOFILHO)

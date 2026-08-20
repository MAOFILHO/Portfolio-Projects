# Azure-Banking-Voice-Agentic-AI — Scoping & Phase Plan

> Produced by four rounds of `/grill-with-docs` scoping (grilling + domain-modeling) against the
> `AI-Powered-Call-Center-Intelligence` and `azure-openai-agents` reference repos, plus verified
> live research against official Microsoft sources. Approved in substance by Marco on 2026-08-19.
> Operating rules that apply across every phase (stop conditions, model/context policy, skill
> discipline, hard exclusions) live in `CLAUDE.md`, not here — this file is scope, architecture,
> budget, and the phase plan.

## Context

`/Users/marco/K21/Real-world/Azure-Banking-Voice-Agentic-AI` is an **empty placeholder directory**
inside the `MAOFILHO/Portfolio-Projects` monorepo (`git@github.com:MAOFILHO/Portfolio-Projects.git`,
branch `setup-matt-pocock-skills`). Verified firsthand — the remote is the monorepo; the project is a
folder within it.

**Goal:** a production-grade prototype IVR — a real Canadian phone number that a caller dials to
reach a banking voice agent — built on Azure under a **hard $25/month** ceiling.

It is the deliberate Azure counterpart to `AWS-Insurance-FNOL-Voice-Agentic-AI`. The portfolio value
is the **contrast** between two clouds solving the same shape of problem. Symmetry is maintained
where a reviewer sees it (`evals/`, `redteam/`, `tests/`, `docs/`, phase docs, ADRs, `Makefile`,
commit convention) and deliberately diverges where the clouds genuinely differ (Bicep vs Terraform;
`transport/` has no FNOL analog).

Two reference repos were cloned to seed it. **A primary finding of this scoping exercise is that
they contribute far less than the brief assumed.**

---

## Reuse reality

The brief was "leverage the 2 repos so we don't reinvent the wheel." After full inventory, **roughly
10–15% of this build comes from the repos**, and it is design, not code.

### `AI-Powered-Call-Center-Intelligence` → ~0 lines of code

A transcribe-and-annotate dashboard, not an IVR. Zero matches tree-wide for `realtime`, `WebSocket`,
`Communication Services`, `Call Automation`, `MediaStreaming`, `sip`, `telephony`, `chat/completions`.

| Fact | Evidence |
|---|---|
| Audio never reaches the backend | `web-app-frontend/src/App.js:71` — `AudioConfig.fromDefaultMicrophoneInput()`; browser → Azure Speech directly |
| Deprecated legacy Completions API | `ai-app-backend/routes/openai-gpt.js:56` — `/completions?api-version=2022-12-01` |
| No TTS, barge-in, VAD, turn-taking, dialog state | absent throughout |
| Author states the limit | `call-intelligence-realtime/README.md:27` — "it does not use Azure Bot Service and Direct Line Speech channel" |
| No CI/CD | `.github/` has only two issue templates |
| `DEPLOY.md` is a stub | literally `## Step 5. text here` |
| Secrets in tracked files; leaked subscription ID | `ai-app-backend/config.json`; `web-app-frontend/.vscode/settings.json` |
| Illustrative latent bug | `data/data-logging.js:7` reads `consmosdb_connection_string` (typo); key absent, so Cosmos logging always throws, swallowed at `:33` |

Its one genuinely transferable artifact — the Speech STS token broker (`serverapp.js:37-58`) — exists
to hand a **browser** a short-lived token. **There is no browser in this architecture.** It is dead
to us. What survives: the externalised per-vertical prompt-config *pattern*
(`routes/openai-config.json` already has a `banking_prompt`), and its post-call analytics topology as
a **reference only** — not its ARM template, which hardcodes App Service Plan `EP1` (Elastic Premium)
and Azure SQL and would blow $25 several times over.

### `azure-openai-agents` → a design, not code

Text-only OpenAI Agents SDK demo. Zero matches for `voice|audio|speech|realtime|tts|stt`.

**Take:** the banking agent taxonomy and handoff shape — `customer_service_agent` triaging to
specialists via `handoff(...)` (`main.py:98-150`).

**Do not take — reasons, not preferences:**

| Problem | Evidence |
|---|---|
| **Fabricated telemetry** — user-mandated hard exclusion | `fixed_openai_agents.py:342-353` invents `to_agent` by string-matching demo agent names when the real value is missing. A Customer Service → Loan handoff can be reported as going to Investment Specialist. **Never vendor this file.** |
| Vendored fork of a private module | `fixed_openai_agents.py` copies logfire's `_internal/integrations/openai_agents.py` (~3.8.x); nothing imports it; meant to be hand-copied into site-packages. `logfire >= 3.8.1` unpinned has already drifted from installed 4.37+. |
| Broken dependency | `requirements.txt` lists `dotenv`; code needs `python-dotenv` (`main.py:5`). Clean install does not import. |
| Config that does nothing | `model="gpt-4o"` hardcoded ×4 (`main.py:102/115/128/142`); `AZURE_OPENAI_DEPLOYMENT` never reaches model selection. Entire APIM client (`main.py:27-32`) is dead. |
| **Silent-fallback bug** | `check_account_balance` (`main.py:59-65`) returns `$1,000.00` for **any** unknown account. Explicitly must not be reproduced — see T-UNKNOWN-ACCT. |
| No redaction on telemetry | `otel-collector-config.yaml` has **no `processors:`** while exporting raw prompts/completions to Azure Monitor. |
| No guardrails, tests, error handling, retry, or entry point | a linear 6-step scripted demo |

**Also unusable:** realtime handoffs do not support `input_filter`, so
`banking_handoff_message_filter` (`main.py:89-94`) cannot be ported.

---

## Settled decisions

| # | Decision | Choice |
|---|---|---|
| 1 | **Front door** | PSTN only — ACS Call Automation + bidirectional media streaming |
| 2 | **Pipeline** | Realtime speech-to-speech; native barge-in |
| 3 | **Deploy** | Numbered-step Python **Typer CLI** wrapping `az` + Bicep, checkpointed via `deployment_state.json`, driven by `make deploy`/`make teardown`. Not `azd`. |
| 4 | **Process depth** | Mirror FNOL: `docs/adr/`, `evals/`, `redteam/`, phase docs, `PROJECT_STATE.md`, `COSTS.md`, `CHANGELOG.md`, `TESTING-CONVENTIONS.md` |
| 5 | **Scope** | `authenticate_caller`, `get_balance`, `list_transactions`, `block_card`, `escalate_to_human` |
| 6 | **Handoff** | One persistent realtime session per call; agent swap via `session.update`. Triage → Accounts → Cards |
| 7 | **Caller auth** | Spoken card last-4 + DOB (KBA), then **PIN via DTMF** |
| 8 | **Post-call analytics** | Minimal, own phase. Transcript already available from realtime events — **no Speech STT needed** |
| 9 | **Layout** | Two deployables, shared-nothing |
| 10 | **Agent shape** | Explicit FSM + declarative `AgentSpec` table |
| 11 | **Fixtures** | TTS-synthesized from YAML text scripts + telephony degradation |
| 12 | **Region** | **Canada Central** (revised from East US 2 — Canada Central is physically Toronto, confirmed via the Azure regions page, same metro as the caller; East US 2 is Virginia, a cross-border hop. Also unifies the ACS/OpenAI footprint into one geography). **No fallback chain.** If Canada Central cannot serve a realtime deployment: **stop and report**, do not relocate |
| 13 | **Number** | **Canada local geographic**, Toronto area (416/647/437/905/289) |
| 14 | **Model pin** | `gpt-realtime-mini` **2025-12-15 (GA)**, GlobalStandard, `versionUpgradeOption: NoAutoUpgrade` |
| 15 | **WS lifecycle** | Close both WebSockets on call end; measure replica billing state empirically |
| 16 | **Non-functionals** | IaC, CI/CD, tests, OTel+redaction, managed identity, guardrails, docs/ADRs. API auth = shared-secret only |
| 17 | **`escalate_to_human`** | **Graceful apology + call termination**, with a logged escalation record (call correlation ID, reason code, timestamp) persisted to Table Storage. **No outbound transfer leg.** A real transfer needs a real second number and a real human on the other end — neither exists in this prototype, and simulating one (transferring to a personal number, a voicemail box) wouldn't demonstrate a real capability, only add ACS transfer-API complexity and an outbound $0.013/min cost for a feature that can't be meaningfully tested end-to-end. Named test case: `T-ESCALATION-LOGGED` |
| 18 | **`PROJECT_STATE.md` shape** | Fixed-size **current-state** document only — open items, current phase, active defects, next actions. **Size ceiling: ≤400 lines / ~20 KB.** Historical narrative goes in `docs/phaseN/`, never here. FNOL's `PROJECT_STATE.md` reached 557 KB and became its single biggest token cost — this is the standing rule that prevents the same failure here, recorded in `CLAUDE.md` |

---

## Named constraints

Modelled on FNOL's C1/C14 — named, measurable, adversarially tested, CI-gating.

| ID | Constraint | Target | Enforced at |
|---|---|---|---|
| **B1** | **Auth Gate Integrity** — zero authenticated-only tool invocations reach the core-banking client while `session.auth_state != Authenticated` | **0 breaches / ≥120 adversarial cases** | L1, blocking CI |
| **B2** | **PIN Confidentiality** — the DTMF PIN never appears in any transcript, log line, OTel span attribute, or persisted record | **0 occurrences**, artifact scan | L0+L1, blocking CI |
| **B3** | **Model Pinning** — no code path can instantiate a realtime deployment outside the frozen allowlist | **0 violations** | startup guard + CI static check + Bicep |
| **B4** | **Cost Ceiling** — no call exceeds 5 min / 20 turns; daily aggregate minute cap trips "we're closed"; **fails closed** | **0 overruns, 0 fail-open events** | L1, blocking CI |
| **B5** | **Turn Latency** — p95 turn round-trip | **PROVISIONAL after Phase 2 (N≥100 real turns); FROZEN after Phase 5 (tool calls in path)** | L3 + production OTel |

**B5 is measured, not asserted, in two stages — Phase 0 cannot produce it.** Phase 0 runs an echo
WebSocket with no realtime session, so it can only measure **transport RTT**, not turn latency; 3
calls is not a sample size a percentile can be drawn from. So:
- Phase 0 exit reports **transport RTT baseline** (ACS ingress/egress only), stated with its actual
  sample size — turns, not calls.
- After Phase 2 (first real turns through `RealtimeSession`, **N≥100 turns**), B5 gets a
  **provisional** p95 with the turn count that backs it.
- After Phase 5 (tool calls to `mock-core-banking` now in the hot path for authenticated intents),
  B5 is **frozen** — this is the realistic number, since tool calls are the slowest leg.
- Any p95 reported anywhere in this project **states the turn count behind it**. A percentile without
  a stated N is not a finding.

**B4 fail-closed is explicit:** if the cost-tracking store is unreachable or in an unknown state, the
IVR **refuses calls** and plays the closed path. It must never fail open. `spendingLimit: Off` is
confirmed on the subscription — **Azure will not stop spend at any threshold. B4 is the only brake
that exists.** Named test case: `T-B4-FAILCLOSED`.

**B3's startup guard** is one function, refusing to boot on either violation:
```python
ALLOWED_REALTIME_MODELS = frozenset({"gpt-realtime-mini"})  # 2025-12-15, GA

def assert_boot_safety() -> None:
    if "AZURE_OPENAI_API_KEY" in os.environ:
        raise SystemExit("keyless auth breaks when AZURE_OPENAI_API_KEY is set")
    if settings.realtime_deployment not in ALLOWED_REALTIME_MODELS:
        raise SystemExit(f"model {settings.realtime_deployment!r} not in B3 allowlist")
```

**B5 budget legs** (provisional after Phase 2, frozen after Phase 5):
ACS ingress → realtime round trip → tool call to `mock-core-banking` (when invoked) → ACS egress.
**No resampler legs** — pending Phase 0 empirical confirmation (see R-02).

---

## Architecture

```
Caller (Ontario mobile)
    │  dials Canada local number (416/647/437/905/289)
    ▼
Azure Communication Services ──Event Grid──► POST /api/incoming-call
    │                                              │ answer call
    │  bidirectional media streaming (WSS)         │
    │  audioFormat: Pcm24KMono                     │
    │  enableDtmfTones: true                       ▼
    └──────────────────────────────────►  Container App (Canada Central)
                                            min-replicas=1, 0.25 vCPU / 0.5 GiB
         {"kind":"AudioData","audioData":{"data":"<b64 PCM>"}}
         {"kind":"DtmfData","dtmfData":{"data":"3"}}   ← PIN never reaches the LLM
                                                   │
                          wss://{res}.openai.azure.com/openai/v1/realtime
                                    ?model=gpt-realtime-mini
                          (Entra ID, scope https://ai.azure.com/.default)
                                                   │
                                    ┌──────────────┴──────────────┐
                                    │  RealtimeSession            │
                                    │  session.update → agent swap│
                                    └──────────────┬──────────────┘
                                                   │ tool call
                                                   ▼
                                    ┌──────────────────────────────┐
                                    │  dispatch/gate.py   ◄── B1   │  ← THE control
                                    └──────────────┬───────────────┘
                                                   ▼
                                    mock-core-banking (own Container App)
                                    FastAPI + SQLite, real network hop
```

**Key protocol facts (verified):**
- ACS frames: 50/sec, 20 ms, **960 bytes at 24 kHz**. Inbound keys lowercase
  (`kind`/`audioData`/`data`); outbound keys **capitalized** (`Kind`/`AudioData`/`Data`), plus
  `{"Kind":"StopAudio",...}` for barge-in. Requires `EnableBidirectional = true`.
- ACS sends `x-ms-call-correlation-id` and `x-ms-call-connection-id` as handshake headers — use for
  call-state correlation and OTel trace linking.
- Realtime WS URL is the **GA path**: `/openai/v1/realtime?model={deployment}`. **No `api-version`**;
  deployment goes in `model=`, not `deployment=`. The `?api-version=…&deployment=…` form is the
  deprecated beta path.
- Realtime max session duration **60 min** (watch `expires_at` on `session.created`) — comfortably
  outside B4's 5-min cap.
- **`openai-agents` can target Azure.** Verified in source (`src/agents/realtime/openai_realtime.py`):
  `api.openai.com` is only the default for `options.get("url", …)`, and supplying `headers` via
  `model_config` bypasses the `OPENAI_API_KEY` requirement. Added in v0.2.11 (PR #1633).
  **Pin `openai-agents >= 0.3.0` as a floor in `pyproject.toml`**, not a comment.
- **The text seam exists inside the protocol**: `conversation.item.input_audio_transcription.completed`,
  `response.audio_transcript.delta`/`.done`, `response.function_call_arguments.done`,
  `input_audio_buffer.speech_started`/`speech_stopped`. This is what makes deterministic CI possible.

---

## Region & data residency

**Canada Central, no fallback.** Realtime models exist in exactly six regions: `canadacentral`,
`centralus`, `eastus2`, `francecentral`, `swedencentral`, `southindia`. East US, West US 2, and West
US 3 have **none**. Sweden Central is rejected (EU residency + transatlantic latency from Ontario).
If Canada Central cannot serve a realtime deployment, **stop and report** rather than relocate.

**ADR-001 — Data residency.** Quotable, from the Foundry data-privacy page:

> For any deployment type labeled 'Global,' prompts and responses **may be processed in any geography
> where the relevant model sold by Azure is deployed**. […] any data stored at rest […] is stored in
> the customer-designated geography. **Only the location of processing is affected.**

At rest stays in the resource geography — with Canada Central, that means every resource (ACS,
Azure OpenAI, Container Apps, Table Storage) sits in a single Canadian jurisdiction. But
**inference may still run in any of the six Global Standard regions**, spanning the US, Canada, the
EU, and India — Global deployment type does not pin processing to the resource's region even when
the resource itself is Canadian. The ADR must state this honestly, and it is a **better** finding
than the one under East US 2, not a neutral one: **resource geography and data-at-rest can be fully
Canadian, but no Global deployment — regardless of which of the six regions hosts the resource — can
guarantee Canadian-only *processing*.** A real Canadian bank under strict data-residency requirements
would need a Standard (single-region) or Data Zone deployment type instead of Global, trading away
Global's throughput/availability advantages — and per R-06, it isn't yet confirmed whether Data Zone
is even offered for realtime models. That's the honest, narrower gap worth documenting, in place of
the broader one the old region belief implied.

Two traps to avoid writing into it:
- **Do not cite "30 days"** for abuse-monitoring retention. It is no longer in current documentation
  (pages revised 2026-05). Cite the DPA, or omit the number.
- **Do not write "we can fall back to DataZone."** The pricing feed returns DataZone realtime meters
  at +10%, but the availability tables list realtime under **Global Standard only** — zero rows under
  Data Zone Standard. Phase 0 attempts a `DataZoneStandard` deployment to confirm or deny.

**ADR-002 — Geography knobs, now fully unified.** R-05 verified: ACS number purchase is gated
**only by Azure subscription billing address**, never by the ACS resource's `dataLocation` — so
there was never a technical requirement forcing any particular pairing. Confirmed across the Canada
page, US page, eligibility page, and a Microsoft support answer stating purchase works "regardless of
your ACS resource's region." `location` (ACS's ARM control-plane field) is always `'global'` — ACS is
not a regional resource — and is independent of `dataLocation` (data-at-rest geography, governing
only 24h call recordings + chat/resource data). With the region switch to Canada Central (see
above), the two knobs now land in the same place by choice, not by constraint: `dataLocation: 'Canada'`
(matches billing address, zero cost) with ACS `location: 'global'`, and Azure OpenAI in **Canada
Central**. The ADR documents both knobs, that no coupling forces them together, and that this
project chose to align them anyway — a single-jurisdiction resource footprint, with ADR-001 covering
the residual cross-border *processing* gap that Global deployment type still leaves open.

---

## Budget

All meters verified from official sources. ACS Audio Streaming was retrieved via the pricing
calculator API v3 (`https://azure.microsoft.com/api/v3/pricing/communication-services/calculator/?culture=en-us`)
— the Retail Prices API has **zero** ACS meters, and the pricing page renders client-side.

**Fixed monthly**

| Item | Cost |
|---|---|
| Canada local number | $1.00 |
| Container Apps, min-replicas=1, 0.25 vCPU / 0.5 GiB | **$4.29 idle** – **$14.31 active** |
| Table Storage, App Insights (<5 GB), Static Web Apps | ~$0 |
| **Subtotal** | **$5.29 – $15.31** |

**Per minute (inbound)**

| Component | Rate |
|---|---|
| PSTN inbound, Canada Geographic | $0.0085 |
| ACS audio streaming | $0.0040 |
| `gpt-realtime-mini` (floor, 10 tok/s/direction, 50/50 split) | $0.0090 |
| **Floor** | **$0.0215/min** |
| **Realistic (2× context growth)** | **~$0.031/min** |

**Eval budget — the naive figure above omits automated testing spend, which is real money against
this ceiling.** L3 (20 scenarios) and L4 (a sampled adversarial subset) both run live models through
`FakeTransport` — no ACS/PSTN meters, but real `gpt-realtime-mini` token cost:

| Suite | Cadence | Est. minutes/mo | Est. cost/mo |
|---|---|---|---|
| L3 evals (20 scenarios, ~2 min each) | weekly + on-demand | ~173 | $1.56 – $3.11 |
| L4 redteam (sampled subset, ~1 min each) | weekly + on-demand | ~130 | $1.17 – $2.34 |
| **Hard eval budget ceiling** | — | — | **$6.00/mo** |

The eval runner **refuses to start a new run once month-to-date eval spend reaches the ceiling** —
same fail-closed discipline as B4, tracked in the same cost store. The full 120-case B1 adversarial
suite stays **free**, because it runs deterministically against `FakeRealtimeServer` in L1 with no
live model involved — only the smaller L4 *live* sample costs money.

**Honest result including evals:**

| | Idle Container Apps ($4.29) | Active Container Apps ($14.31) |
|---|---|---|
| Fixed + eval ceiling | $11.29 | $21.31 |
| Left for manual/demo calls | $13.71 | $3.69 |
| **At floor rate ($0.0215/min)** | **~638 min (10.6 hr)** | **~172 min (2.9 hr)** |
| **At realistic rate ($0.031/min)** | **~442 min (7.4 hr)** | **~119 min (2.0 hr)** |

**So: roughly 2 to 10.6 hours/month of actual manual testing/demo calling** — down from the naive
5–15 hour figure once evals are accounted for. The Container Apps idle-vs-active question is still
the single biggest lever (worth ~7.5 hours), with the eval ceiling as the second. Both are Phase 0
measurements; the eval estimate itself gets replaced with a measured actual once the harness exists
in Phase 2, same as every other number in this budget.

Notes: Canada and US local are **identically priced** — no delta from choosing Canada. Outbound
$0.013/min never applies — see decision 17, `escalate_to_human` never places a real call. Container
Apps free grant is 180,000 vCPU-s / 360,000 GiB-s / 2M requests. During a call the replica is
unambiguously **active** (24 kHz PCM16 = 48,000 B/s vs a 1,000 B/s idle threshold); between calls is
undocumented, hence decision 15. `min-replicas=0` is **disqualifying** for inbound telephony (cold
start seconds→30s).

---

## Project layout

```
Azure-Banking-Voice-Agentic-AI/
├── voice-agent/                  pyproject.toml, Dockerfile
│   ├── transport/                acs.py, fake.py, protocol.py
│   ├── realtime/                 client.py, events.py, session.py
│   ├── agents/                   specs.py (AgentSpec table), prompts/
│   ├── dispatch/                 gate.py           ◄── B1 lives here
│   ├── audio/                    dtmf.py, degrade.py
│   ├── cost/                     caps.py           ◄── B4, fail-closed
│   └── boot.py                   ◄── B3 startup guard
├── mock-core-banking/            pyproject.toml, Dockerfile, SQLite
├── infra/                        main.bicep + modules/ (one file per resource)
├── src/azbank_deploy/            Typer CLI, deployment_state.json
├── tests/                        L0 units, L1 fakes, L2 cassettes
├── evals/                        L3 live semantic evals
├── redteam/                      L4 adversarial cases (YAML)
├── docs/
│   ├── adr/                      ADR-001 residency, ADR-002 geography knobs, … (written in Phase 0)
│   ├── phase0..phase8/           per-phase docs with exit criteria
│   ├── architecture.md  cost.md  deployment.md  troubleshooting.md
│   ├── RESULTS.md  REVIEW-CRITERIA.md  TESTING-CONVENTIONS.md
├── COSTS.md   PROJECT_STATE.md   CHANGELOG.md   CLAUDE.md   README.md
├── Makefile                      install test lint fixtures deploy teardown
└── pyproject.toml
```

CI at the **monorepo root**: `.github/workflows/azure-banking-voice-agentic-ai-{ci,deploy,teardown}.yml`,
scoped via `paths:`. Issues titled `[Azure-Banking-Voice-Agentic-AI] …`.
Commits: `type(project-phase): D<n>/OI<n> -- prose`.

---

## Testing strategy

```
L4  redteam/   live model via FakeTransport   weekly + on-demand, sampled subset, $-capped, non-blocking
L3  evals/     live model via FakeTransport   weekly + on-demand, threshold-gated, $-capped
L2  cassettes  recorded real sessions         every PR, deterministic — catches protocol drift
L1  fakes      FakeAcs + FakeRealtime         every PR, deterministic — BLOCKING (B1/B2/B4 live here)
L0  units      codec, DTMF, FSM, gate         every PR, deterministic, milliseconds
```

**Neither L3 nor L4 carries a real PSTN leg by default.** Both run the real Azure OpenAI model through
`FakeTransport` — no ACS, no phone number, no `$0.0125/min` ACS+PSTN cost, only model tokens. A run
that needs the real telephony path (occasional, deliberate) is explicitly flagged as **end-to-end**
and is not part of the weekly cadence. This is the mechanism behind the eval budget table above —
weekly, not nightly, is what keeps L3+L4 under the $6/mo ceiling; the eval runner enforces the ceiling
itself, refusing new runs once month-to-date eval spend is reached, same fail-closed discipline as B4.

**Why B1 is deterministically testable:** the gate is enforced server-side in the tool dispatcher,
so it is a pure function of `(tool_name, session.auth_state)` — no audio, no model, no network. This
splits adversarial testing cleanly:
- *Can an attacker make the model **try** a pre-auth balance call?* — probabilistic, L3/L4, reported.
- *Can that attempt **succeed**?* — deterministic, L1, **blocking**.

Only the second is a security property. `AgentSpec` tool scoping is **defense in depth, not the
control**.

**Fixture pipeline** (`make fixtures`) models the real signal chain — degrade **then restore**, since
ACS hands us PCM 24k and the μ-law/8k loss happens upstream on the PSTN leg:
```
TTS studio 24k → downsample 8k → μ-law encode → μ-law decode
              → band-limit 300–3400 Hz → optional noise floor → upsample 24k
```
YAML cases are tracked in git; WAVs are generated. Speech **F0** covers TTS (0.5M chars/mo free;
note F0 allows only **1 concurrent** request).

**Named test cases:** `T-UNKNOWN-ACCT` (unknown account must **raise**, never silent-fallback —
explicitly not repo 2's `$1,000.00` bug; caller-facing path handles it gracefully),
`T-B4-FAILCLOSED` (cost store unreachable → refuse calls), `T-ESCALATION-LOGGED` (escalation record
persisted with call correlation ID + reason code; call terminates gracefully; no outbound leg ever
attempted).

---

## Phase plan

Each phase gets `docs/phaseN/` with its own exit criteria. IaC is **incremental** — every phase adds
its Bicep module and grows the deploy CLI.

### Phase 0 — Provisioning & Meter Spike ⛔ *gated*
Everything that must be true before building. One trip, all unknowns folded in since we're dialing anyway.
1. Register `Microsoft.Communication` (currently **unregistered**).
2. Verify realtime SKU `deprecationDate` via the Models API — docs conflict (see R-01).
3. Attempt a `DataZoneStandard` realtime deployment → confirm/deny for ADR-001.
4. Create ACS resource (`location: 'global'`, `dataLocation: 'Canada'`). Run `List Area Codes`
   (`locality=Toronto`, `administrativeDivision=ON`) to determine live inventory — 416/647/437 vs the
   905/289 belt (different rate centre, likely a separate locality query) is genuinely undocumented
   and resolved only by this live call.
5. Purchase a Canada local geographic number from confirmed available area codes.
6. Minimal echo WebSocket; **3 test calls**.
7. Measure, in the same calls:
   - real ACS Audio Streaming meter vs $0.004 list
   - **empirical proof that `Pcm24KMono` delivers clean 24 kHz PCM16 both ways** (R-02)
   - `DtmfData` frames arriving during active bidirectional streaming (R-03)
   - per-leg latency baseline
8. Wait 24h; read Cost Analysis. Observe Container Apps billing state over **72h idle**.
9. Write **ADR-001** (data residency) and **ADR-002** (geography knobs) now, while the decisions are
   fresh — not deferred to Phase 8.
10. **R-08**: from the meters measured in steps 7–8 (not the plan's estimate), compute how many full
    Phase-8-style demo runs/month the remaining budget supports, using B4's 5-min cap as the ceiling
    on a single demo run's length. Record the number and its inputs in `COSTS.md`.
11. **Teardown compute only — keep the number leased.**

**Exit gate:** `COSTS.md` contains **measured** meters, not estimates, **and** a measured **transport
RTT baseline** with its stated sample size (turns, not calls — an echo WebSocket has no realtime
session, so it cannot produce a turn-latency percentile; that's Phase 2's job, see B5). ADR-001 and
ADR-002 exist in `docs/adr/`. **R-08's demo-runs/month figure is computed and recorded — if it comes
in under 5, Phase 0 stops here and we discuss reducing fixed cost or raising the ceiling before
Phase 1 proceeds.**

### Phase 1 — Duplex audio path
Echo call, no agent, no tools, no auth. `AcsTransport` + `MediaTransport` protocol, Event Grid
webhook, call lifecycle, barge-in via `StopAudio`, WS close-on-hangup (decision 15).
**Exit:** dial → answer → speak → hear yourself, latency recorded, `make teardown` leaves zero
billable compute.

### Phase 2 — Realtime session + agent core + gate + test harness ⛔ *control ships here*
`RealtimeSession` against Azure via `model_config` override; `AgentSpec` table; `session.update`
agent swap; `FakeTransport` + `FakeRealtimeServer`; L0/L1 suites; **B3 startup guard**.
**`dispatch/gate.py` ships now, deny-all-by-default** — every tool call is refused unless explicitly
allowlisted for the current `(agent, auth_state)` pair. This is deliberate sequencing: Phase 3 adds a
real network path to `mock-core-banking`, and no phase may exist where that path is reachable without
a gate already in front of it. Phase 4 only *adds permissions* to an existing control; it never
introduces one.
**Exit:** full app runs end-to-end between two fakes in CI with zero Azure dependency; gate defaults
closed and is provably in front of every tool, even stub ones. **B5 provisional** after N≥100 real
turns through a live `RealtimeSession`, turn count stated.

### Phase 3 — mock-core-banking
FastAPI + SQLite, own Container App, own Dockerfile. Timeouts, retries, circuit-breaking in the
client. `T-UNKNOWN-ACCT`. The real network path this phase introduces sits behind Phase 2's gate from
the moment it exists — never in front of it.
**Exit:** tool calls are real network calls with modelled failure paths, all still deny-all by default.

### Phase 4 — Auth gate permissions ⛔ *B1/B2 threshold*
KBA (card last-4 + DOB) + DTMF PIN. Adds the `Authenticated` transition and the permissions it
unlocks to the Phase-2 gate — does not introduce the gate itself. ≥120 adversarial cases in `redteam/`
(deterministic, L1, free).
**Exit:** B1 = 0 breaches, B2 = 0 occurrences, both blocking in CI.

### Phase 5 — Intents + cost controls ⛔ *B5 frozen here*
`get_balance`, `list_transactions`, `block_card` (confirmation + idempotency), `escalate_to_human`
(decision 17: graceful termination + logged record, `T-ESCALATION-LOGGED`). B4 per-session and daily
caps, **fail-closed**, `T-B4-FAILCLOSED`.
**Exit:** all 4 intents working over a real call; B4 blocking in CI; **B5 frozen** — tool calls to
`mock-core-banking` are now in the hot path for authenticated intents, making this the realistic
latency figure, turn count stated.

### Phase 6 — Observability
OTel per call session → App Insights, correlated via `x-ms-call-correlation-id`. **Redaction
processor** — the thing repo 2 conspicuously lacks. PII scrubbing before export.
**Exit:** a full call traceable end-to-end with zero PII in any span.

### Phase 7 — IaC completion & CI/CD
Complete Bicep, complete Typer deploy CLI, root workflows (`ci`, `deploy`, `teardown`). Managed
identity end-to-end, no Key Vault. **Deploy workflow authenticates to Azure via GitHub OIDC federated
credentials** (workload identity federation) — consistent with the no-keys stance; no service
principal secret stored in GitHub Actions secrets.
**Exit:** clean-subscription → working system via `make deploy`; `make teardown` → zero billable;
`ci`/`deploy`/`teardown` workflows run with no long-lived Azure secret anywhere in the repo or its
GitHub settings.

### Phase 8 — Post-call analytics, evals & docs
Transcript (already in hand from realtime events — **no STT needed**) + metadata → Blob; PII
redaction via Language free tier; summary/intent/outcome → Table Storage. L3 evals + L4 redteam
suites at their weekly/on-demand cadence. Any ADRs not already written during their triggering phase
(ADR-001/002 were written in Phase 0); `RESULTS.md`, `README.md`, architecture diagram.
**Exit:** the repo reads as a matched pair with FNOL.

---

## Tracked risks

| ID | Risk | Fallback |
|---|---|---|
| **R-01** | `gpt-realtime-mini` listed **twice with conflicting retirement dates** — 2025-10-06 as both `2027-04-06` and `2026-09-21` (~1 month out); 2025-12-15 as both `2027-06-15` and `2026-12-15` | Plan against the pessimistic date; verify per-SKU via Models API in Phase 0; `NoAutoUpgrade` |
| **R-02** | `Pcm24KMono` behaviour is a **documentation-based assumption**, and the resampler was deleted on that basis | If ACS misbehaves, resampler returns and B5's breakdown changes. Phase 0 verifies by measurement |
| **R-03** | `DtmfData` during active bidirectional streaming | Documented and used in all four language pivots; narrowed but unproven. If it fails: pause-stream-and-`recognize`, which changes the auth flow and B5 |
| **R-04** | Open-but-silent WebSocket may keep a Container App replica **active**-billed (~$10/mo swing) | Decision 15 closes WS between calls; measured over 72h in Phase 0 |
| **R-05** | ~~ACS data location coupled to purchasable number country~~ — **resolved, no coupling found**; remaining unknown is narrower: live 416/647/437 vs 905/289 area-code inventory under `locality=Toronto` | Query `List Area Codes` in Phase 0 step 4 |
| **R-06** | DataZone realtime meters exist but availability tables show Global Standard only | Phase 0 attempts a real DataZone deployment; ADR states the confirmed answer |
| **R-07** | `spendingLimit: Off` — Azure will not stop spend | B4 fail-closed is the only brake; Budget alert at $20 is notification only |
| **R-08** | **Demonstrability** — at the low end of the recomputed budget there may not be enough call-minutes left for repeated Phase 8 portfolio walkthroughs (authenticate + balance + block card + escalate, run repeatedly for demos). The project's value is that someone can dial it. Back-of-envelope using this plan's own numbers: at ~4 min/demo run (near, not over, B4's 5-min cap) and "left for calls" of $3.69–$13.71/mo, that's **~30 runs/mo (worst case: active Container Apps, realistic per-min rate) to ~160 runs/mo (idle, floor rate)** — comfortably above a 5-run floor on paper, but every input (ACS streaming actual meter, Container Apps billing state, true per-turn token cost) is still an estimate | Phase 0 exit computes this **from measured meters**, not the estimate above. If the measured answer is under 5 runs/month, stop and discuss reducing fixed cost or raising the ceiling before Phase 1 — do not silently proceed on a demo budget that can't demo |

---

## Verification

**Per PR (deterministic, blocking):** `make test` runs L0+L1+L2 with zero Azure dependency —
`FakeAcsTransport` replays degraded WAV fixtures, `FakeRealtimeServer` replays scripted event JSONL.
B1, B2, B4 assertions are binary. `make lint` runs ruff + mypy. CI static check enforces B3's
allowlist across the tree.

**Weekly + on-demand (live, threshold-gated, budget-capped):** L3 evals — TTS-synthesized caller
audio through `FakeTransport` (real model, no PSTN leg), LLM-judge rubric, ≥95% over 20 runs. L4
redteam runs a sampled adversarial subset live (the full ≥120-case suite stays free, deterministic,
and blocking at L1); reported, non-blocking. Both draw from the same $6/mo eval budget ceiling and
refuse to start once it's spent for the month.

**Per phase:** each `docs/phaseN/` exit criteria met and recorded in `PROJECT_STATE.md`.

**End-to-end manual:** dial the Toronto number from a mobile; authenticate by voice + DTMF PIN; ask
for a balance; block a card and confirm; escalate. Then `make teardown` and confirm zero billable
compute remains (number stays leased by design).

**Cost:** after each test session, reconcile Azure Cost Analysis against `COSTS.md` projections.
Phase 0's gate is that these are **measured, not estimated**.

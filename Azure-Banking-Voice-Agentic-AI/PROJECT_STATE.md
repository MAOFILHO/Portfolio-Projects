# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`). Historical narrative lives in `docs/phase0/`,
`docs/phase1/`, and `docs/handoffs/`, never here. Check this file's size before every edit — ceiling
is ≤400 lines/~20KB; move the oldest closed material out first if an addition would exceed it.

## Current phase

**Phase 3 — mock-core-banking. Built and reviewed 2026-09-08, all seven tickets.**
`/code-review` ran both axes (`d697baf..HEAD`, spec = #25); every actionable finding is fixed
(`0dec63e`, `HEAD`). **Marco's own sign-off on the exit criteria has not happened** — that is the
stop condition, and this file does not self-certify it.
Spec: GitHub issue **#25**. Tickets: **#26-32** (sub-issues of #25). Written exit criteria:
`docs/phase3/exit-criteria.md`.

**152 tests green** (129 voice-agent incl. 3 skipped by design, 23 mock-core-banking), `make lint`
clean, B3 static check passes, zero cloud dependency. Built:
- **#26** `mock-core-banking/` — FastAPI + SQLite, own package/pyproject/Dockerfile/tests, integer
  cents, seeded-if-empty, REST-resource routes with the 404/200-declined/422 status mapping.
- **#27** `core_banking/client.py` — the protocol, the async httpx client, 1.0s timeout, one retry
  on reads only, and a per-process breaker (5 failures → 30s → half-open probe) for the whole
  service. Failure paths tested via `httpx.MockTransport`; the breaker's clock is injected.
- **#28** the seam — `FakeCoreBankingClient`, `accounts.py` **deleted**, the account enum dropped
  from the tool schema, `dispatch_tool_call` async and awaited by the relay.
- **#29** boot guard refuses to start without `CORE_BANKING_URL`.
- **#30** one real-network test (spawns the service, real socket) + `make test`/`install` across
  both suites.
- **#31** these docs. **#32** `infra/modules/mock-core-banking.bicep`, written unapplied.

**`/code-review` findings, all fixed, each with a test verified red against the pre-fix code:**
1. **The caller was being read the service's internal URL.** An unknown account produced "There's
   no `http://ca-azbank-core-banking.internal:8001/accounts/bitcoin` account on this profile."
   Both axes found it independently. The test had asserted `assertIn("bitcoin", error)` — and the
   URL contains "bitcoin", so the substring check could not tell the right answer from the wrong
   one. Fixed at the source: the service now names the unknown account in its 404 body (it is the
   only thing that knows *which* of a transfer's two accounts was bad); assertions are now exact
   sentences.
2. **A half-open probe on a read issued two requests, not one** — `READ_RETRIES` applied to the
   probe, against #27's own acceptance criterion, doubling load on a backend already believed sick.
3. **A malformed request spoke the service's internal wording** ("core banking rejected the request
   with 422"). Now a composed sentence; the raw text is logged, not spoken.
4. **The tool schema still named the accounts in prose** ("e.g. chequing or savings") after the
   enum was dropped — the same stale answer back in front of the model in another form.
5. The fake raised `ValueError` where the real client raises `CoreBankingRequestError` for the same
   scenario — a divergence that made tests passing against the fake say something untrue about
   production (#25's own user story 10). The fake now fails the way the service does.

**Known-partial, not fixed:** exit criterion 9's "Bicep module reviewed" is **unvalidated** — no
`bicep` CLI is available here, and `infra/` contains only this one module (no `main.bicep`), so
"consistent with the existing modules' shape" has nothing to be consistent with yet. Also
unenforced: #26's "runs without the voice agent installed" is true by construction (no cross-
imports) but `make test` uses one shared venv, so nothing proves it.

**Two deviations from the tickets as written, both deliberate:**
1. `tests/test_gate.py` could not pass *literally* unchanged (#28's criterion 7) — the dispatcher
   is a coroutine now, so its in-path class had to become async. **What it asserts is unchanged,
   and `dispatch/gate.py` itself is byte-identical**, which is the half that was actually load-
   bearing. The policy class (`GateIsAPureDenyAllFunction`) is untouched.
2. The client is built once in `app.lifespan()` and read from a module-level accessor, **not
   constructed per call** — a first pass did the latter, which would have given every call its own
   circuit breaker that could never trip. Q13 settled per-process; this is that decision, enforced.

Scope: `mock-core-banking` becomes its own deployable (FastAPI + SQLite, own package/Dockerfile/
tests), reached through one new seam -- a `CoreBankingClient` protocol with a real async httpx
client and a deterministic fake, mirroring how `transport/` and `realtime/` already pair a real
system with its fake. `accounts.py` is deleted. `dispatch_tool_call` goes async so a network call
never stalls the audio loop. **`dispatch/gate.py` does not change** -- `PERMISSIONS` stays `{}`;
this phase adds a path *behind* the control, Phase 4 adds permissions.

**No `APPROVED: Phase 3` is required for this scope -- it creates no billable Azure resource.**
Nothing is provisioned: the Dockerfile and Bicep module are written and left unapplied, and the
live container app is not redeployed. Provisioning is a separately approved step afterwards, with
its own precondition (R-08, below).

Three design decisions worth not re-deriving: a **declined** transfer is 200 + structured outcome
(not 4xx -- it is a normal outcome of a working system); **`transfer` is never retried** (not
idempotent, a retried timeout is a double-spend); one circuit breaker per process for the **whole**
service (per-endpoint would let a healthy read path mask a service failing its writes). Full
reasoning in #25.

## Phase 2 — closed

**Signed off by Marco 2026-09-08 ("Phase 2 approved").** All three exit criteria met: fakes-only CI
with the gate provably deny-all, `T-B3-SUCCESSOR-BOOT` exists, and B5's provisional figure landed
at **p95=932ms, N=106** (31 real calls + 75 `scripts/b5_probe.py` samples, both pools stated).
Spec was issue #16, tickets #17-24.

Full narrative -- what was built per ticket, the two `/code-review` rounds, the B2 leak fix, the
review findings deliberately not actioned: `docs/handoffs/2026-09-08-phase2-signoff-phase3-entry.md`.
Per-call B5 detail: `docs/phase2/evidence/b5-call-log.md`. Not repeated here (decision 18).

**98 tests green, ~0.5s, no cloud dependency** (3 skipped: the successor rehearsal, by design).
`make lint` clean. **Phase 1 remains the demonstrable deliverable and still works.**

**Operating-mode verdict: IDLE, reconfirmed 2026-09-08** against R-04's original method, over the
window covering all 8 real B5 calls plus the probe batch -- settles to idle within one 15-min
bucket every time, same ~189KB/118KB baseline as Phase 0/1.

## Phase 0 — closed

All 12 stages of `01-provision.sh` ran, first real answered call 2026-08-21, teardown complete
(commit `07faf3b`). Compute was re-provisioned for Phase 1's own work (below) — Phase 0's own
teardown is not the current resource state. Full narrative: `docs/phase0/findings.md`,
`docs/phase0/EXIT-AND-PHASE1-ENTRY.md`, `docs/handoffs/2026-08-24-phase0-closeout-teardown-complete.md`.

**Resources live now**: resource group `rg-azure-banking-voice-agentic-ai`; AOAI
`aoai-azure-banking-voice-cc` (`gpt-realtime-mini` 2025-10-06 GlobalStandard, NoAutoUpgrade); ACS
`acs-azure-banking-voice`; phone number `+17059100383` (owned, $1.00/mo, R-09 — never released);
Container Apps environment `cae-azure-banking-voice-p0`; Container App `ca-azbank-echo-p0`
(min-replicas=1, billing now) running the **Phase 2** image `docker.io/maofilho/azbank-echo-p0:p3`
as of 2026-09-08 (`:p2` deployed 2026-09-07, was Phase 1's `:latest` before that; `:p3` adds the B5
latency-anchor logging from `42e02c5`, revision `--0000002`, `Healthy`, 100% traffic, B3 verified
live again from real logs); data-plane auth
to AOAI (the realtime connection itself) is still via the `AOAI_KEY` secret — only the B3 ARM read
uses the managed identity.

**Correction 2026-09-08: there are three Log Analytics workspaces, not two.** `...aiCS`
(`2a41795f-...`, Phase 0's documented "real/linked" one) and `...aixC` (`e42c142b-...`, documented
orphan) were the only two on record — but the container app's diagnostic setting
(`azbank-p0-console-logs`) actually targets a **third, undocumented one**:
`workspace-rgazurebankingvoiceagenticai1D` (`bf520f2c-e2bc-4488-8965-9317a7922c74`). `...aiCS` has
been stale since 2026-08-25 without anyone noticing; `...ai1D` is the live one — confirmed by
querying it and finding real rows from today's calls. Query `...ai1D`, not `...aiCS`, for
anything current. `...aixC` is still the orphan.

**System-assigned managed identity added to `ca-azbank-echo-p0` 2026-09-07** (this session, Marco
confirmed the plan first): principal `5e09fe34-8913-4aa2-80ac-618af308a88f`, granted `Reader` —
scoped only to the `aoai-azure-banking-voice-cc` resource, nothing broader — which is what
`boot.read_live_model()`'s one ARM `GET .../deployments/{name}` call needs. Free, no new billable
resource.

**Phase 2 image deployed 2026-09-07** (Marco built+pushed on his laptop, confirmed `linux/amd64`;
Claude confirmed the `az containerapp update` command before running it): `ca-azbank-echo-p0` now
runs `docker.io/maofilho/azbank-echo-p0:p2`, plus the three env vars `boot.read_live_model()` needs
(`AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AOAI_ACCOUNT_NAME` — added via `--set-env-vars`,
additive, confirmed the 5 pre-existing vars were untouched). New revision
`ca-azbank-echo-p0--0000001`, `Healthy`/`RunningAtMaxScale`. **B3's boot guard ran live for the
first time and passed** — confirmed from actual container logs (not inferred from health state):
managed identity acquired a token, `GET .../deployments/gpt-realtime-mini` returned `200 OK`, and
the app logged `B3: deployed model ('gpt-realtime-mini', '2025-10-06') matches the active pin.`
before `Application startup complete.` Single-revision mode, so this replaced the running Phase 1
container — flagged to Marco as a real risk (no automatic fallback on a bad boot) before running.

**Redeployed to `:p3` 2026-09-08** (same process, Marco confirmed the command first): adds the B5
latency-anchor logging (`42e02c5`) that `:p2` didn't have. Revision `--0000002`, `Healthy`, 100%
traffic, B3 verified live again from real logs (`ai1D` workspace). No env var changes.

## Open items

Full triage of which of these block what, and why none block Phase 1's own exit criteria (already
met): `docs/phase1/EXIT-AND-PHASE2-ENTRY.md` Part 1. Listed here because they're still genuinely
unresolved, not because anything below is currently blocking.

1. **No durable ACS-side call-diagnostics path.** App-side container logs deliver correctly
   (`docs/handoffs/2026-08-27-phase1-logpath-resolved.md`); ACS-side call diagnostics were never
   configured, and per item 3 below, won't be for the R-03 question specifically. Matters more once
   Phase 2 adds a gate whose failures need auditing — Phase 6 (Observability) is its real fix.
2. **`02-test-calls.sh` must not be re-run carelessly.** Stages 1-3 have no skip-if-already-confirmed
   guard — unconditionally prompts for 3 fresh billable calls before Stage 4's free, read-only
   evidence extraction can run. Candidate fix: an `--extract-only` flag.
3. **R-03's Call-1 zero-DTMF anomaly is permanently unresolved for Call 1** — dropped as a Phase 1
   entry criterion 2026-08-28 (Call 1's evidence no longer exists to settle it). Calls 2/3 already
   confirm DTMF works in the common case.
4. **Docker Hub vs ACR — still on Docker Hub.** Was due a deliberate decision at Phase 1 kickoff;
   didn't happen. ACR with managed-identity pull matches Phase 7's "no keys" direction but costs a
   real ~$5/mo.
5. **Rate-limit meaning unconfirmed** — the Models API's per-deployment `rateLimits` field doesn't
   reconcile against the documented subscription-level Quota Tier table. Cheap Foundry-portal check
   (~30s), still not done.
6. **`gpt-realtime-1.5` successor boot untested** — by design, Phase 2's own deliverable
   (`T-B3-SUCCESSOR-BOOT`, needs `FakeRealtimeServer`, which Phase 2 builds).
7. **Stale `az` CLI `defaults.location=eastus`** (this machine only, `~/.azure/config`). Fix
   identified (`--location ""`), shown as a diff, not yet applied — pending sign-off.
8. **Log Analytics workspace auto-provision choice** (`az containerapp env create`'s default, no
   `--logs-destination` flag passed) — tied to item 1; needs a deliberate choice regardless of cost,
   since the auto-provisioned path doesn't even deliver logs.
9. **Intermittent interrupt-the-caller defect.** Agent talks over the caller, cutting in before a
   sentence finishes. Reproduced on the first real call, not the second, same image and VAD config
   both times — nothing explains the absence on the second call. **Explicitly not gating Phase 1's
   exit table** (`docs/PLAN.md`'s own words). Scoped as `server_vad` config tuning, not new code,
   once/if it reproduces again.
10. **Dead air before the agent speaks first — PARKED, deliberately, 2026-09-08.** 2.5-11s on every
    real call: `session.py` sends no initial `response.create`, so nothing prompts the greeting
    until the caller talks first. **Decided at Phase 3 kickoff: not fixed in Phase 3.** It belongs
    to the greeting path, not the tool path, and Phase 3's diff already touches the relay's tool
    handling — changing both in one phase makes a regression hard to attribute. Small fix whenever
    it's wanted; this line exists so it isn't re-litigated at every phase boundary.

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

**R-01, R-02, R-03 (partial, see item 3), R-04, R-05, R-06 resolved.** **R-04 reconfirmed
2026-09-01 for Phase 1's stateful agent loop** (IDLE, reconfirmed 2026-09-08). **R-08 answered in
Phase 0 (~79–114 demo runs/month, gate passes) but stale — PARKED as of 2026-09-08, and promoted to
a precondition of *provisioning*, not of Phase 3's code.** mock-core-banking's Container App would
be this project's **second** Container App, and fixed cost is the line the whole $25/mo ceiling
turns on — so R-08 gets recomputed against a two-app fixed cost before anything is deployed, not
before Phase 3 is built. **R-09** (number irreplaceability) is a standing hard rule, not something
to resolve. **R-07** is a standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

1. **`/code-review` Phase 3** (Marco's call to invoke), then check `docs/phase3/exit-criteria.md`
   actually holds. The diff to look at hardest is #28's — it touches the relay and the dispatcher
   together, and CLAUDE.md's never-auto-accept rule covers that directory even though `gate.py`'s
   own policy is deliberately untouched.
2. **Only after 1**: recompute R-08 against a two-Container-App fixed cost. If it still clears the
   gate, `APPROVED: Phase 3` for the **provisioning step itself** — which is not part of Phase 3's
   scope and has its own diff (`infra/modules/mock-core-banking.bicep`) to review first.
3. `/handoff`, copy it into `docs/handoffs/`, commit, then `/clear` at the phase boundary.

**Still not written, needs Marco:** the root `CONTEXT-MAP.md` that `docs/agents/domain.md` calls
for. It sits outside `PROJECT_ROOT` and needs approval by absolute path, same as the CI workflow
did. `CONTEXT.md` (this project's own glossary) is written and committed.

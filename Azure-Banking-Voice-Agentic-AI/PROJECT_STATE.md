# PROJECT_STATE.md — Azure-Banking-Voice-Agentic-AI

Current-state only (decision 18, `CLAUDE.md`): what is true now, what is open, what happens next.
**Nothing past-tense belongs here.** Closed phases are archived per phase and the archives are the
account of what happened:

| phase | closed record |
|---|---|
| 0 | `docs/phase0/findings.md`, `docs/phase0/EXIT-AND-PHASE1-ENTRY.md` |
| 1 | `docs/phase1/archive.md`, `docs/phase1/EXIT-AND-PHASE2-ENTRY.md` |
| 2 | `docs/phase2/archive.md` |
| 3 | `docs/phase3/archive.md` (exit criteria: `docs/phase3/exit-criteria.md`) |
| 4 | `docs/phase4/exit-check.md`, `docs/phase4/findings.md` (exit criteria: `docs/phase4/exit-criteria.md`) |

Check this file's size before every edit — ceiling is **≤400 lines / ~20KB**; move the oldest closed
material into the archive above if an addition would exceed it.

## Stop conditions in force

`CLAUDE.md`'s stop-conditions list is canonical and is not restated here. These are the ones with a
live bearing on the current moment:

1. **The phone number `+17059100383` is never released**, by any script, at any phase, for any
   reason (R-09). Irreplaceable, not merely billable.
2. **No billable Azure resource without Marco typing `APPROVED: <phase name>`.** This binds the
   pending mock-core-banking provisioning, which also has R-08 as a precondition (below).
   **"Phase 3: APPROVED" (2026-09-09) signed off the exit criteria; it did not authorise
   provisioning**, which was never in Phase 3's scope and needs its own approval.
3. **`dispatch/` changes are never auto-accepted**, even when `gate.py` itself is untouched.
4. **No phase begins without written exit criteria and Marco's explicit approval.** Phase 5 has none
   yet. Phase 4's were written and approved 2026-09-10 (`docs/phase4/exit-criteria.md`), including
   the item that needed its own sign-off: **B1's breach definition is sharpened** — no *banking*
   operation reaches the core-banking client while the call is unauthenticated, with PIN
   verification the only operation reachable while anonymous. That sharpened definition is now what
   the suite enforces, and it stands for every later phase.
5. **This file is updated before any session ends**, and never exceeds the ceiling above.

## Current phase — Phase 4 built and awaiting sign-off; Phase 5 not begun

**Phase 4 (auth gate permissions) is built, ticket by ticket.** Spec **#33**, tickets **#34-42**.
The gate grants for the first time, on a PIN the model never sees. Criterion-by-criterion evidence:
`docs/phase4/exit-check.md`.

| | |
|---|---|
| voice-agent tests | 263 pass, 3 skipped by design |
| mock-core-banking tests | 47 pass |
| B1 red-team | **11 distinct attack ideas → 193 concrete cases**, 176 reaching an attempt |
| B1 breaches / B2 occurrences | **0 / 0**, both blocking |
| `make lint`, B3 static check | clean, passing |

Both red-team numbers are always quoted together. A case count with no idea count behind it is the
same empty claim as a percentile with no N.

**Nothing was provisioned, nothing redeployed, no real call made.** What a caller dialling the
number reaches today is still Phase 1's agent on the Phase 2 image.

### Needs Marco

0. **`/code-review` has not been run.** `CLAUDE.md` requires it before every phase gate, no
   exceptions, and Marco invokes it — Claude does not. **This is the one thing blocking the gate.**
1. **Phase 4 sign-off.** Every criterion is met (`docs/phase4/exit-check.md`). Two carry a stated
   limit rather than a clean pass: criterion 7's injected-item wire shape is unverified, and
   criterion 9's idea count is 11 against a target of 20-30, reported rather than padded.
2. **`/research` on the realtime API's `conversation.item.create` item types** before Phase 5's real
   call — specifically whether a `system`-role `input_text` message is accepted mid-session on a
   `gpt-realtime-mini` deployment. `docs/phase4/findings.md` §2 names the exact question. This
   project's own rule forbids answering it from memory, and Claude does not invoke `/research` on
   its own initiative.
3. **One test failure seen once, not reproduced in 98 runs.** Reading and evidence:
   `docs/phase4/findings.md`. Not evidence about B1 or B2, both of which are in-process and were
   re-run 98 times with identical verdicts.

### Still open from Phase 3

1. **Known-partial:** exit criterion 9's "Bicep module reviewed" is **unvalidated** — no `bicep` CLI
   is available here, and `infra/` contains only this one module (no `main.bicep`), so "consistent
   with the existing modules' shape" has nothing to be consistent with yet.

## Live Azure state

Verify this against the API before acting on it (`CLAUDE.md`, Resume discipline) — it is a snapshot
and goes stale between sessions. **What a caller dialling the number reaches today is Phase 1's
agent**, on the Phase 2 image; Phase 3's network path is built but not deployed.

- Resource group `rg-azure-banking-voice-agentic-ai`.
- AOAI `aoai-azure-banking-voice-cc` — `gpt-realtime-mini` 2025-10-06, GlobalStandard, NoAutoUpgrade.
  **Verified live 2026-09-10** at the Phase 4 gate, deployment and Models API both: the pin retires
  **2027-04-06**, ~6.9 months out, so no stop-and-ask. Successor `gpt-realtime-1.5` still GA
  (retires 2027-08-24). No drift from `docs/PLAN.md` decision 14. Evidence:
  `docs/phase4/exit-check.md`.
- ACS `acs-azure-banking-voice`; phone number **`+17059100383`** (owned, $1.00/mo, never released).
- Container Apps environment `cae-azure-banking-voice-p0`.
- Container App `ca-azbank-echo-p0`, min-replicas=1 (**billing now**), running
  `docker.io/maofilho/azbank-echo-p0:p3`, revision `--0000002`, `Healthy`, 100% traffic. Its
  system-assigned identity (`5e09fe34-8913-4aa2-80ac-618af308a88f`) holds `Reader` on the AOAI
  resource only, which is what B3's boot guard reads. Deployment history:
  `docs/phase2/archive.md`.
- **Data-plane auth to AOAI is still the `AOAI_KEY` secret** — only the B3 ARM read uses the managed
  identity.
- **Logs: query `workspace-rgazurebankingvoiceagenticai1D`** (`bf520f2c-e2bc-4488-8965-9317a7922c74`),
  never `...aiCS`, which has been stale since 2026-08-25. `...aixC` is an orphan. Three workspaces
  exist, not two.

## Open items

Full triage of which of these block what: `docs/phase1/EXIT-AND-PHASE2-ENTRY.md` Part 1. Listed here
because they are genuinely unresolved, not because any of them is currently blocking.

1. **No durable ACS-side call-diagnostics path.** App-side container logs deliver correctly
   (`docs/handoffs/2026-08-27-phase1-logpath-resolved.md`); ACS-side call diagnostics were never
   configured, and per item 3 below, won't be for the R-03 question specifically. Matters more now
   that a gate's failures need auditing — Phase 6 (Observability) is its real fix.
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
6. **`gpt-realtime-1.5` successor boot untested** against a real successor — the rehearsal
   (`T-B3-SUCCESSOR-BOOT`) exists and is skipped by design.
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
10. **Dead air before the agent speaks first — PARKED, deliberately, still.** 2.5-11s on every real
    call: `session.py` sends no initial `response.create`, so nothing prompts the greeting until the
    caller talks first. Parked at Phase 3 kickoff and again at Phase 4's, and it has a **sharper
    edge now**: the greeting is what asks for the PIN, so a caller who says nothing is waiting on a
    prompt that has not been triggered and will never be asked to authenticate. Still the greeting
    path's defect rather than the auth path's. Small fix whenever it's wanted; this line exists so
    it isn't re-litigated at every phase boundary.
11. **No real DTMF tone has ever been consumed by this system.** Phase 0 proved tones *arrive*
    during active bidirectional streaming; every line that acts on one is Phase 4's and is exercised
    only against fakes, because Phase 4 deployed nothing. Closes at Phase 5's real-call exit.
12. **The injected conversation item's wire shape is unverified.** The relay tells the caller a PIN
    outcome by injecting a `message` item with a `system` role — the documented shape, never seen
    accepted by this deployment. Only the `function_call_output` shape is confirmed live.
    `docs/phase4/findings.md` §2.

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

1. **Recompute R-08 against a two-Container-App fixed cost.** If it still clears the gate, that is
   when to approve the **provisioning step itself** — not part of Phase 3's scope, and with its own
   diff (`infra/modules/mock-core-banking.bicep`) to review first, which no tooling here can
   validate.
2. `/handoff`, copy it into `docs/handoffs/`, commit, then `/clear` at the phase boundary.
3. **Sign off Phase 4, or send back what does not hold.** The three items needing Marco are listed
   under "Needs Marco" above. `/code-review` has **not** been run on this phase — `CLAUDE.md`
   requires it before every phase gate, and Marco invokes it, not Claude.
4. **One ADR is offered and not written** (`docs/adr/`): the shared core-banking client that made
   B1's restatement necessary. Hard to reverse, and it would read as arbitrary without the
   reasoning. The second candidate — a binary gate carrying two factors — died with the KBA cut.
5. **Phase 5 needs written exit criteria and approval before any of it begins.** It is where the
   real-call exit closes Phase 4's known-partial, where B5 freezes, and where mock-core-banking's
   provisioning finally has to happen — which is what makes the R-08 recompute in item 1 a
   precondition of Phase 5 rather than of anything already built.

**Still not written, needs Marco:** the root `CONTEXT-MAP.md` that `docs/agents/domain.md` calls
for. It sits outside `PROJECT_ROOT` and needs approval by absolute path, same as the CI workflow
did. `CONTEXT.md` (this project's own glossary) is written and committed.

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
4. **No phase begins without written exit criteria and Marco's explicit approval.** Phase 4 has not
   begun and has no written exit criteria yet.
5. **This file is updated before any session ends**, and never exceeds the ceiling above.

## Current phase — Phase 3, signed off; Phase 4 not begun

**Phase 3 (mock-core-banking) was signed off by Marco on 2026-09-09 ("Phase 3: APPROVED").** Built,
reviewed three times, and every finding fixed. Spec: issue **#25**, tickets **#26-32**. The closed
record is `docs/phase3/archive.md`.

**207 tests green** (175 voice-agent incl. 3 skipped by design, 32 mock-core-banking), `make lint`
clean, B3 static check passes, zero cloud dependency.

**Nothing is provisioned** — the Dockerfile and Bicep module are written and left unapplied, and the
live container app is not redeployed. Provisioning is a separately approved step, with R-08 as its
precondition (below).

### Still open

1. **Known-partial:** exit criterion 9's "Bicep module reviewed" is **unvalidated** — no `bicep` CLI
   is available here, and `infra/` contains only this one module (no `main.bicep`), so "consistent
   with the existing modules' shape" has nothing to be consistent with yet.

## Live Azure state

Verify this against the API before acting on it (`CLAUDE.md`, Resume discipline) — it is a snapshot
and goes stale between sessions. **What a caller dialling the number reaches today is Phase 1's
agent**, on the Phase 2 image; Phase 3's network path is built but not deployed.

- Resource group `rg-azure-banking-voice-agentic-ai`.
- AOAI `aoai-azure-banking-voice-cc` — `gpt-realtime-mini` 2025-10-06, GlobalStandard, NoAutoUpgrade.
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

1. **Recompute R-08 against a two-Container-App fixed cost.** If it still clears the gate, that is
   when to approve the **provisioning step itself** — not part of Phase 3's scope, and with its own
   diff (`infra/modules/mock-core-banking.bicep`) to review first, which no tooling here can
   validate.
2. `/handoff`, copy it into `docs/handoffs/`, commit, then `/clear` at the phase boundary.
3. **Phase 4 kickoff** needs written exit criteria and Marco's approval before any of it begins. It
   is the phase that adds permissions to `gate.py` and puts the DTMF PIN on the path, so both
   never-auto-accept rules bind it from the first diff.

**Still not written, needs Marco:** the root `CONTEXT-MAP.md` that `docs/agents/domain.md` calls
for. It sits outside `PROJECT_ROOT` and needs approval by absolute path, same as the CI workflow
did. `CONTEXT.md` (this project's own glossary) is written and committed.

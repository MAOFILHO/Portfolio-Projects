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
| 4 | `docs/phase4/exit-check.md`, `docs/phase4/findings.md`, `docs/phase4/research-carried-findings.md` (exit criteria: `docs/phase4/exit-criteria.md`) |

Phase 5 is **current, not closed** — `docs/phase5/exit-criteria.md` and `docs/phase5/exit-check.md`.

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
4. **B1's sharpened definition stands**: no *banking* operation — balance, transfer, list, and from
   Phase 5 also transactions and card block — reaches the core-banking client while the call is
   unauthenticated. **Its corollary changed in Phase 5, on sign-off**: `escalate_to_human` is granted
   in every row, so "no tool at all is reachable while a call is anonymous" is now **false** and has
   been rewritten everywhere it appeared. The accurate sentence is that the set reachable while
   anonymous is **exactly the PIN check and asking for a person**, neither of which is a banking
   operation. B1's target has not moved: 0 breaches, ≥120 cases, L1, blocking.
5. **This file is updated before any session ends**, and never exceeds the ceiling above.

## Current phase — Phase 5 built to the edge of Azure; 13 of 18 tickets done

**Phase 5 (intents + cost controls).** Spec **#43**, tickets **#44-60**, exit criteria written and
approved 2026-09-11. Criterion-by-criterion evidence: `docs/phase5/exit-check.md`.

**Everything that can be built and proved without Azure is done. Nothing has been provisioned,
nothing redeployed, no call made.** What a caller dialling the number reaches today is still Phase
1's agent on the Phase 2 image — the gap between what is committed and what answers the phone is now
**four** phases wide.

**Three rounds of `/code-review` are actioned and closed.** Record: `docs/phase5/review-fixes.md`.

| | |
|---|---|
| voice-agent tests | **491 pass**, 3 skipped by design (was 480) |
| mock-core-banking tests | **90 pass** (was 47) |
| B1 red-team | **18 distinct attack ideas → 593 concrete cases**, 542 reaching an attempt |
| B1 breaches / B2 occurrences | **0 / 0**, both blocking |
| B4 | complete and blocking in CI, by construction |
| B5 | **not frozen** — the probe is repaired but has not been run |
| `make lint`, B3 static check | clean, passing |

Both red-team numbers are always quoted together: a case count with no idea count behind it is the
same empty claim as a percentile with no N.

**What the phase added is in `docs/phase5/exit-check.md`.** Three things a later session needs
without reading it:

- **The red-team idea count is 18 against a target of 20-30**, reported rather than padded, and the
  gap is still a gap. Widening a matrix is not an idea — the two new tools roughly doubled the case
  count while adding none.
- **B2 still covers three of its four surfaces.** Span attributes are uncovered because nothing emits
  spans; a test now fails if anything starts to.
- **Two exit criteria predicted the wrong thing and were corrected in place** rather than smoothed
  over: the red-team assertion that did not need to widen, and the budget read that moved out of the
  webhook because a marker in the WebSocket URL would be client-controllable and therefore
  fail-open. Both corrections are inline in `docs/phase5/exit-criteria.md`.

### Needs Marco

0. **Review `git log e42c063..HEAD`** — see next action 1. Read the range from `git log`, never a
   count written here: a count here has been wrong twice, because the commit updating it is
   uncounted as it is written. **Most of those commits touch `dispatch/`, the DTMF/PIN path, or
   both**, so the never-auto-accept rule binds them.
1. **`/research`, before anything is applied.** Two facts are written from documentation rather than
   from a live source, and the module says so in its own header: the **role definition GUID** in
   `infra/modules/call-records-store.bicep`, where being wrong produces a role assignment that
   returns 200 OK and grants nothing; and **Table Storage's rate**, which is R-08's one unpriced
   input. Named, not invoked.
2. **A human review of both Bicep modules.** No `bicep` CLI exists here and there is still no
   `main.bicep`, so human review is the only check there is.
3. **A phone.** Tickets #58 and #59 need Marco dialling, and **the call must press `*` and `#`** — a
   digits-only call closes nothing while looking like it did.

### The four wire-format questions — all still open

No real DTMF tone has ever been consumed by this system. Nothing below is answered, and each closes
on the acceptance call or not at all:

1. Does this deployment and model version **accept the injected system message**?
2. How are **`*` and `#` spelled** on the media-streaming path?
3. Did **DTMF and audio frames arrive in produced order**? The payload's `timestamp` is still unread.
4. Does a **real keyed tone drive the authenticator** at all?

### Still open from Phase 3

1. **Known-partial:** "Bicep module reviewed" is **unvalidated by any tool**. `infra/` holds two
   modules; none has been compiled, linted or what-if'd.

## Live Azure state

Verify this against the API before acting on it (`CLAUDE.md`, Resume discipline) — it is a snapshot
and goes stale between sessions. **What a caller dialling the number reaches today is Phase 1's
agent**, on the Phase 2 image; Phase 3's network path is built but not deployed.

- Resource group `rg-azure-banking-voice-agentic-ai`.
- AOAI `aoai-azure-banking-voice-cc` — `gpt-realtime-mini` 2025-10-06, GlobalStandard, NoAutoUpgrade.
  **Re-verified live 2026-09-11** at the Phase 5 gate, deployment and Models API both: the pin
  retires **2027-04-06**, ~6.8 months out, so no stop-and-ask. Successor `gpt-realtime-1.5` still GA
  (retires 2027-08-24). No drift from `docs/PLAN.md` decision 14. Evidence:
  `docs/phase5/exit-check.md`.
- ACS `acs-azure-banking-voice`; phone number **`+17059100383`** (owned, $1.00/mo, never released).
- Container Apps environment `cae-azure-banking-voice-p0`.
- **Verified live 2026-09-11**: the resource group holds exactly what it held before — **no Storage
  account, no second Container App**. Nothing this phase describes has been provisioned.
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
   that a gate's failures need auditing. **Corrected 2026-09-11: Phase 6 is NOT its fix.** Phase 6
   produces app-side traces, ingested via the OTel Distro's own endpoint — independent of
   `Microsoft.Insights/diagnosticSettings`, which is what failed in Phase 0. ACS-side diagnostics are
   different data from a different producer over that same failed mechanism. Out of Phase 6's scope
   (`docs/phase6/exit-criteria.md` D6); needs its own decision and a table queried for rows.
2. **`02-test-calls.sh` must not be re-run carelessly.** Stages 1-3 have no skip-if-already-confirmed
   guard — unconditionally prompts for 3 fresh billable calls before Stage 4's free, read-only
   evidence extraction can run. Candidate fix: an `--extract-only` flag.
3. **R-03's Call-1 zero-DTMF anomaly is permanently unresolved**, and dropped as a Phase 1 entry
   criterion 2026-08-28 — the evidence no longer exists. Calls 2/3 confirm DTMF in the common case.
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
   `--logs-destination` passed) — tied to item 1, and needs a deliberate choice regardless of cost
   because the auto-provisioned path doesn't deliver logs at all.
9. **Intermittent interrupt-the-caller defect.** Agent talks over the caller, cutting in before a
   sentence finishes. Reproduced on the first real call, not the second, same image and VAD config
   both times — nothing explains the absence on the second call. **Explicitly not gating Phase 1's
   exit table** (`docs/PLAN.md`'s own words). Scoped as `server_vad` config tuning, not new code,
   once/if it reproduces again.
10. *(closed, `docs/phase5/review-fixes.md`; number held so 11-21 keep their references)*
11. **No real DTMF tone has ever been consumed by this system.** Phase 0 proved tones *arrive*
    during active bidirectional streaming; every line that acts on one is Phase 4's and is exercised
    only against fakes, because Phase 4 deployed nothing. Closes at Phase 5's real-call exit.
12. **The injected conversation item's *acceptance* is unverified — its shape no longer is.**
    Confirmed against the generated specification 2026-09-10: `system` + `input_text` is the only
    content type that role permits, and the spec names this exact use. Unverified is whether Azure's
    GA endpoint and `gpt-realtime-mini` `2025-10-06` accept it, which is the case B3 exists for. One
    live frame settles it; the item carries a client `event_id` so the probe can tell a refusal from
    an unrelated error. `docs/phase4/findings.md` §2, `docs/phase4/research-carried-findings.md` §1.
13. **The DTMF tone vocabulary is unverified, and no documentation can verify it.** The frame has
    no schema in Azure's specs; primary examples show a bare digit, the only enumerated vocabulary
    spells tones as words and belongs to a different delivery path, and `*` and `#` — the two keys
    the keypad acts on — have no documented spelling at all. The classifier accepts both, so the
    ambiguity cannot break a call, but **the real call must press `*` and `#`**: a digits-only call
    closes nothing while looking like it closed this. `docs/phase4/research-carried-findings.md` §2b.
14. **Nothing guarantees DTMF and audio frames arrive in order on the media socket.** No primary
    source offers any ordering or timing guarantee. The webhook path ships a `sequenceId` for
    exactly this; this path ships nothing equivalent, though the payload carries an unread
    `timestamp`. The four-digit accumulator assumes arrival order equals press order. Observe it at
    Phase 5 rather than inheriting it.
15. **`RequestResponse` is an Azure OpenAI diagnostic-log category with no documented content
    coverage.** Not enabled, and must not be enabled on `aoai-azure-banking-voice-cc` until its
    destination table has been queried and read — it is a candidate fifth B2 surface, and its name
    is the only thing anyone knows about it.
16. **Unknown whether the FastAPI, httpx and requests instrumentations capture request or response
    bodies by default.** Not verified against those packages' source, so it is not asserted either
    way. It matters because the relay's own FastAPI app receives the ACS webhook and, at Phase 5,
    the media WebSocket — a body-capturing default there would put DTMF frames into telemetry.
    **Promoted 2026-09-11 to a hard blocker on one Phase 6 ticket** (`docs/phase6/exit-criteria.md`
    D8, criterion 3): the webhook body carries the caller's phone number, which Phase 6's design
    forbids in telemetry, and the relay never reads it — so a body-capturing default would put it
    there with no code in this project having touched it. FastAPI instrumentation is not enabled
    until this is answered from the packages' source.
17. **`transport/acs.py`'s audio branch is not total, unlike its DTMF branch.** A malformed
    `AudioData` frame raises `KeyError` on the inbound relay task, ending the call; the DTMF branch
    is deliberately defensive and the audio branch never was. Pinned by
    `tests/test_acs.py::test_a_malformed_audio_frame_still_raises`, so it is known rather than
    folklore. **Not changed**: relay behaviour nobody asked to alter, on a never-auto-accept path.
18. **The relay imposes no deadline on the injected PIN-outcome frames.** The research is explicit
    that telling a rejection from silence needs the error type, a correlated id, **and the relay's
    own timeout**. The first two are implemented; the third is not, so an injection that is simply
    never answered still looks like an accepted one. Deliberately not built here: the authenticator
    carries "no timer of any kind" as a design decision, and putting one on the relay's PIN path is
    a Phase 5 design question rather than a fix.
19. **The call-record store sets no SDK-level timeout, deliberately.** The deadline is at the seam
    (`session.LEDGER_DEADLINE_SECONDS`), tested, and holds for fake and real client alike. A
    transport timeout would be better, but azure-core clients ignore unknown keyword arguments, so a
    misremembered option name reads as configured and does nothing: the role-definition GUID's
    failure shape. `/research` owes the option names with the rest.
20. **Criterion 12's "every path out" is true inside the relays, not before them.** `budget_or_closed`
    and `connect_realtime` run before `started`, so a failure in either records nothing. Arguably
    right, since no model session existed, but named rather than assumed settled.
21. **The daily ledger's lock is in-process only.** It covers two calls ending together in one
    process; a second replica holds a second lock and loses updates again. ETag optimistic
    concurrency is the fix and a deliberate not-yet (Marco, 2026-09-11): one replica runs, and the
    ETag path cannot be exercised until the Storage account exists.

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

**R-01, R-02, R-03 (partial, see item 3), R-04, R-05, R-06 resolved.** **R-04 reconfirmed
2026-09-01 for Phase 1's stateful agent loop** (IDLE, reconfirmed 2026-09-08). **R-08 recomputed 2026-09-11 against a two-Container-App fixed cost and PASSES**
(`COSTS.md`, "R-08, recomputed"): fixed $14.60/mo, **45–67 demo runs/month against a gate of 5**.
**One input is unpriced** — Table Storage's rate, which `/research` owes before provisioning — and a
sensitivity table shows the gate still clears by four times even at an implausible $5/mo for it.
**R-08 is recomputed again before Phase 6 provisions anything**, because App Insights shares the
container logs' 5 GB free grant rather than adding one (`docs/phase6/exit-criteria.md` D4).
**R-09** (number irreplaceability) is a standing hard rule, not something
to resolve. **R-07** is a standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

0. **Phase 6 does not begin here.** Marco asked for it twice, 2026-09-11; the answer both times is
   that Phase 5's exit is not met — tickets open, nothing provisioned, no call made, B5 not frozen —
   and no phase begins without written exit criteria from the prior one. **Phase 6 is now designed
   and its exit criteria written** (`docs/phase6/exit-criteria.md`, 19 decisions settled by Marco in
   a grilling session, none of them an approval to start). **7 of its 8 entry conditions are unmet**,
   and two proposed named-constraint changes to B2 are unsigned. The path runs through the items
   below, in this order; every one of steps 4 to 6 needs Marco's hands, voice, or both.
0b. **The review findings were never filed as issues** — neither the original eight nor the second
   round. Every fix commit references only the phase spec `#43`. The drafted set and its blocking
   edges are in `docs/handoffs/2026-09-11-phase5-review-fixes.md`.
1. **Read `git log e42c063..HEAD`.** Phase 4's diff and Phase 5's. It is the entry condition that was
   waived, it is four phases of code that will land on one image, and it is the cheapest point at
   which any of it can be sent back.
2. **`/research`: the role definition GUID and Table Storage's rate.** Both are written from
   documentation, both are named as unverified in the module that uses them, and the first one
   failing produces a role assignment that returns 200 OK and grants nothing. Named, not invoked.
3. **Review the two Bicep modules** (`infra/modules/`). Human review is the only check that exists.
4. **Then #57**: provision the Storage account and the second Container App, grant the data role and
   **prove it with a write that is read back** — an ARM 200 OK proves creation, not access — build and
   push an image carrying Phases 3 to 5, redeploy, and make a **smoke call nobody is grading** before
   the acceptance run.
5. **Then #58**: the acceptance call. Scripted in advance, authenticating with a real keyed PIN,
   **pressing `*` and `#`**, reaching all four intents, hitting a refusal before authenticating, and
   ending by escalating. Evidence read out of `workspace-rgazurebankingvoiceagenticai1D`, never the
   stale `...aiCS`.
6. **Then #59 and #60**: B5 frozen with its turn count and what was in the path, then the close-out —
   `docs/PLAN.md`'s Phase 5 section, this file's phase move, and a committed handoff.
7. **One ADR is still offered and not written** (`docs/adr/`): the shared core-banking client that
   made B1's restatement necessary. A second candidate now exists — **the corollary change**, which is
   the kind of decision that reads as arbitrary later without the reasoning beside it.

**Still not written, needs Marco:** the root `CONTEXT-MAP.md` that `docs/agents/domain.md` calls
for. It sits outside `PROJECT_ROOT` and needs approval by absolute path, same as the CI workflow
did. `CONTEXT.md` (this project's own glossary) is written and committed.

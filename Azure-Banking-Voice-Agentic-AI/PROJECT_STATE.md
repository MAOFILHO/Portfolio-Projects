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
2. **No billable Azure resource without Marco typing `APPROVED: <phase name>`.** `APPROVED: Phase 5`
   was typed 2026-09-12 and used: the Storage account and mock-core-banking are now provisioned.
3. **`dispatch/` changes are never auto-accepted**, even when `gate.py` itself is untouched.
4. **B1's sharpened definition stands**: no *banking* operation — balance, transfer, list, and from
   Phase 5 also transactions and card block — reaches the core-banking client while the call is
   unauthenticated. **Its corollary changed in Phase 5, on sign-off**: `escalate_to_human` is granted
   in every row, so "no tool at all is reachable while a call is anonymous" is now **false** and has
   been rewritten everywhere it appeared. The accurate sentence is that the set reachable while
   anonymous is **exactly the PIN check and asking for a person**, neither of which is a banking
   operation. B1's target has not moved: 0 breaches, ≥120 cases, L1, blocking.
5. **This file is updated before any session ends**, and never exceeds the ceiling above.

## Current phase — Phase 5 provisioned and redeployed; 14 of 18 tickets done

**Phase 5 (intents + cost controls).** Spec **#43**, tickets **#44-60**, exit criteria written and
approved 2026-09-11. Criterion-by-criterion evidence: `docs/phase5/exit-check.md`.

**#57 done, 2026-09-12: provisioned, redeployed, two smoke calls, one full pass.** Storage account
and mock-core-banking are live; `ca-azbank-echo-p0` runs the Phase 3-5 image, revision `--0000004`.
Write-then-read proven live through the real managed identity.

**Two real defects, found by the smoke calls rather than by review, both fixed and verified live**:
a missing `aiohttp` dependency crash-looped the first redeploy (`voice-agent/pyproject.toml`; prior
revision kept serving, no caller affected — `adf1dc2`), and Container Apps' ingress redirecting
plain HTTP to HTTPS even internally, which meant no PIN could ever succeed (`allowInsecure: true`,
`e2304ea`). B1's fail-closed path handled the redirect correctly throughout — no attempt consumed.

**The second smoke call went end to end, PIN `1234`**: `accumulating` ×3 -> credential check `200
OK` -> `authenticated` -> `handoff: triage -> banking` -> `list_accounts`, `list_transactions`,
`get_balance` all `200 OK` -> clean disconnect, minutes written and read back. First real proof this
system can authenticate and serve a banking intent end to end.

**Five more calls (post-VAD-tuning `0ed61e0`) all authenticated correctly on the backend and all
mis-spoke it differently** — inverted once, "no access to the confirmation" three times, silent
twice. Never a security issue: every re-key after the first success is logged `ignored`, never
re-checked. Fixed as far as prompting can, with `3dd5605` (explicit confirmed-case instruction) and
`1b494b6` (sharper "successful"/"not successful" pair, Marco's suggestion) — **and confirmed live**:
the next call on the rebuilt image (`p5d`, `--0000006`) said it plainly, then completed
`list_accounts` and a real `transfer`, both `200 OK`, then ended clean. First transfer this system
has ever executed on a real call. One clean call after four inconsistent ones is encouraging, not
conclusive — see "The four wire-format questions" below.

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

0. *(done 2026-09-12 — Tier 1 and 2 of `docs/phase5/commit-review-digest.md` reviewed; gate
   confirmed fine. Tier 3, the lower-risk material, is still unreviewed.)*
1. **`/research` still owes open items 15, 16 and 19** — the `RequestResponse` category, whether the
   FastAPI instrumentation captures request bodies, and the azure-core SDK timeout option names.
2. *(done — Bicep header diffs reviewed and committed 2026-09-12.)*
3. **A phone.** #58 and #59, and **the call must press `*` and `#`** — digits-only closes nothing
   while looking like it did.

### The four wire-format questions — one closed, one holding steady after a scare

1. **Backend never wrong across nine calls; spoken fidelity was the real question, and it holds so
   far.** Four more calls on the *old* image (rebuilt image not yet deployed at the time) each
   mis-spoke the same "confirmed" outcome differently — inverted once, "I don't have access to the
   confirmation" three times, silent twice — while authentication itself succeeded every single
   time underneath. **After `3dd5605` + `1b494b6` actually deployed** (image `p5d`, revision
   `--0000006`), the next call said it plainly, then went on to `list_accounts` and a real
   `transfer`, both `200 OK`, then a clean end. One clean call is one clean call, not a guarantee —
   the four failures were exactly this consistent-looking right up until they weren't.
2. **Still open** — no call has keyed `*` or `#`. Ticket #58's script must.
3. **Still open**, `timestamp` still unread.
4. **Closed, yes.** A full 4-digit PIN (`1234`) drove the authenticator from `accumulating` through
   a real credential check to `authenticated`, live, on two separate calls now.

### Still open from Phase 3

1. **Known-partial, half closed.** Both modules compile and lint clean; neither has been what-if'd
   against the real resource group, which needs a `main.bicep` that does not exist.

## Live Azure state

Verify this against the API before acting on it (`CLAUDE.md`, Resume discipline) — it is a snapshot
and goes stale between sessions. **A caller dialling the number today reaches the Phase 3-5 image**,
redeployed 2026-09-12; no real call has exercised it yet.

- Resource group `rg-azure-banking-voice-agentic-ai`.
- AOAI `aoai-azure-banking-voice-cc` — `gpt-realtime-mini` 2025-10-06, GlobalStandard, NoAutoUpgrade.
  **Re-verified live 2026-09-11**: pin retires **2027-04-06**, ~6.8 months out, no stop-and-ask.
  Successor `gpt-realtime-1.5` still GA (retires 2027-08-24). `docs/phase5/exit-check.md`.
- ACS `acs-azure-banking-voice`; phone number **`+17059100383`** (owned, $1.00/mo, never released).
- Container Apps environment `cae-azure-banking-voice-p0`.
- **Storage account `stazbankcallrecords`**, provisioned 2026-09-12, table `callrecords`. Write-then-
  read proven live through the voice agent's managed identity.
- **Container App `ca-azbank-core-banking`**, provisioned 2026-09-12, internal-only, `Healthy`, one
  replica, image `docker.io/maofilho/azbank-core-banking-p5:p5`.
- Container App `ca-azbank-echo-p0`, min-replicas=1 (**billing now**), running
  `docker.io/maofilho/azbank-echo-p0:p5b`, revision `--0000004`, `Healthy`, 100% traffic, zero
  restarts. Its system-assigned identity (`5e09fe34-8913-4aa2-80ac-618af308a88f`) now holds `Reader`
  on the AOAI resource **and** `Storage Table Data Contributor` scoped to `stazbankcallrecords`.
  `CORE_BANKING_URL` and `CALL_RECORDS_ACCOUNT_URL` are set. Deployment history:
  `docs/phase2/archive.md`.
- **Data-plane auth to AOAI is still the `AOAI_KEY` secret**; Storage auth is managed identity only.
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
2. **`02-test-calls.sh` must not be re-run carelessly.** No skip-if-already-confirmed guard on
   Stages 1-3 — prompts for 3 fresh billable calls before Stage 4's free evidence extraction runs.
3. **R-03's Call-1 zero-DTMF anomaly is permanently unresolved**, and dropped as a Phase 1 entry
   criterion 2026-08-28 — the evidence no longer exists. Calls 2/3 confirm DTMF in the common case.
4. **Docker Hub vs ACR — still on Docker Hub.** Due a decision at Phase 1 kickoff, didn't happen.
   ACR matches Phase 7's "no keys" direction but costs ~$5/mo real.
5. **Rate-limit meaning unconfirmed** — per-deployment `rateLimits` doesn't reconcile against the
   Quota Tier table. Cheap Foundry-portal check, still not done.
6. **`gpt-realtime-1.5` successor boot untested** against a real successor — the rehearsal
   (`T-B3-SUCCESSOR-BOOT`) exists and is skipped by design.
7. **Stale `az` CLI `defaults.location=eastus`** (this machine, `~/.azure/config`). Fix identified
   (`--location ""`), not yet applied — pending sign-off.
8. **Log Analytics auto-provision choice** (no `--logs-destination` passed) — tied to item 1, needs a
   deliberate choice since the auto-provisioned path doesn't deliver logs at all.
9. *(tuned 2026-09-12, `0ed61e0` — `silence_duration_ms` 200 -> 600 after a third reproduction.
   Not yet proven fixed; no call since has been long enough to judge it either way.)*
10. *(closed, `docs/phase5/review-fixes.md`; number held so 11-21 keep their references)*
11. *(closed 2026-09-12 — see "The four wire-format questions" above.)*
12. *(reopened then re-closed 2026-09-12 — see question 1 above.)*
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
    concurrency is the fix and a deliberate not-yet (Marco, 2026-09-11): one replica runs today, so
    the ETag path has nothing to exercise it against yet, even with the Storage account now live.

## Active risks (full detail: `docs/PLAN.md` "Tracked risks")

**R-01, R-02, R-03 (partial, see item 3), R-04, R-05, R-06 resolved.** **R-04 reconfirmed
2026-09-01 for Phase 1's stateful agent loop** (IDLE, reconfirmed 2026-09-08). **R-08 recomputed 2026-09-11 against a two-Container-App fixed cost and PASSES**
(`COSTS.md`, "R-08, recomputed"): fixed $14.60/mo, **45–67 demo runs/month against a gate of 5**.
**No input is unpriced any more**: Table Storage was read live from the Retail Prices API 2026-09-12
and costs under a cent a month, so the recompute's top row is the actual case, not a best case.
**R-08 is recomputed again before Phase 6 provisions anything**, because App Insights shares the
container logs' 5 GB free grant rather than adding one (`docs/phase6/exit-criteria.md` D4).
**R-09** (number irreplaceability) is a standing hard rule, not something
to resolve. **R-07** is a standing fact (`spendingLimit: Off`), not something to resolve.

## Next actions (in order)

0. **`APPROVED: Phase 6` was typed 2026-09-12, and Phase 6 still does not begin here — by Marco's own
   decision the same day.** Presented with the choice, he chose **finish Phase 5 first**. The approval
   is banked and valid; it satisfies **one** of Phase 6's eight entry conditions — "Marco's approval
   to begin Phase 6" — plus the separate `APPROVED: Phase 6` billable-resource gate, and nothing else.
   **Six entry conditions stay unmet**: Phase 5's exit, Phase 5's sign-off, open item 15, open item 16,
   the unsigned B2 widening, and the unreviewed commits. Design: `docs/phase6/exit-criteria.md`, 19
   decisions settled 2026-09-11. The path runs through the items below, in this order; every one of
   steps 4 to 6 needs Marco's hands, voice, or both.
0b. **The review findings were never filed as issues** — neither the original eight nor the second
   round. Every fix commit references only the phase spec `#43`. The drafted set and its blocking
   edges are in `docs/handoffs/2026-09-11-phase5-review-fixes.md`.
1. *(done — Tier 1 and 2 of `docs/phase5/commit-review-digest.md` reviewed; gate confirmed fine.)*
2. *(done — GUID and Table Storage rate, read live 2026-09-12.)*
3. *(done — Bicep header diffs reviewed and committed 2026-09-12.)*
4. *(done — #57. Provisioned, redeployed, two smoke calls, one full authenticated pass. See
   "Current phase" above.)*
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

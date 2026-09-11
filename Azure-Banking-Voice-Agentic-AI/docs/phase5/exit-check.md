# Phase 5 — exit check, against `docs/phase5/exit-criteria.md`

**Status: 13 of 18 tickets complete. The phase is NOT closed, and its exit is NOT met.** Everything
that can be built and proved without Azure is done and committed; everything that needs a
provisioned resource or a dialled phone is not, and the criteria those close are reported as **not
reached** rather than as passed with a caveat.

Written 2026-09-11, against the criteria approved the same day. Each row cites where the evidence is,
and the ones with a stated limit say what the limit is rather than rounding it away.

| | |
|---|---|
| Commits | `git log 79ceb68^..HEAD` — 12, oldest first |
| voice-agent tests | **480 pass**, 3 skipped by design (was 315) |
| mock-core-banking tests | **90 pass** (was 47), still with the voice agent uninstalled |
| B1 | **18 distinct attack ideas → 593 concrete cases**, 542 reaching an attempt, **0 breaches** |
| B2 | **0 occurrences**, across log records *and* the first persisted records the voice agent owns |
| B3 | **Re-verified live 2026-09-11** — see criterion 19 |
| B4 | **Blocking in CI, by construction** — inside pytest, not a step anybody can drop |
| B5 | **Not frozen.** Needs the real call. See criteria 20 and 25 |
| `make lint`, B3 static check | clean, passing |

**Both red-team numbers are quoted together, always.** A case count with no idea count behind it is
the same empty claim as a percentile with no N.

---

## Tickets

Filed as sub-issues of **#43** on 2026-09-11: **#44–#60**.

| # | Ticket | State |
|---|---|---|
| #44 | Transactions at the system of record | **Done** |
| #45 | The card, the block, and the idempotency record | **Done** |
| #46 | `list_transactions`, end to end behind the gate | **Done** |
| #47 | The Cards agent and `block_card` | **Done** |
| #48 | The call-record store, and `escalate_to_human` | **Done** |
| #49 | The day's ledger and the closed path | **Done** |
| #50 | Consumed minutes on every path out, B4 blocking | **Done** |
| #51 | The greeting, in its own commit | **Done** |
| #52 | The B1 red-team corpus, widened | **Done, with the count reported honestly** |
| #53 | B2 over the first persisted records | **Done, with one surface reported unmet** |
| #54 | The latency probe, repaired and authenticating | **Done** |
| #55 | R-08 recomputed | **Done — passes** |
| #56 | Bicep, written unapplied | **Done — written, reviewed, not applied** |
| #57 | Provision, redeploy, smoke call | **NOT STARTED — blocked, see below** |
| #58 | The acceptance call | **NOT STARTED — blocked on #57** |
| #59 | B5 frozen | **NOT STARTED — blocked on #58** |
| #60 | Close-out | **NOT STARTED — blocked on #59** |

---

## Criterion by criterion

### Met

1. **Six rows, five tools, `is_allowed()` untouched.** ✅ `dispatch/gate.py`. `is_allowed()` is
   byte-identical for the third phase running. The pinned table lives in `tests/test_gate.py` as a
   literal that every widening has to edit.
2. **Cross-product still generated from the declared tool list.** ✅ Six tools by six pairs, plus the
   pinned literal. The test's premise had to generalise from "the one granting row" to the whole
   table when the third agent arrived; the generalisation is annotated in the test with why it was
   forced rather than a weakening, and it still refuses to become a subset check.
3. **A third agent, and it was a table row.** ✅ **The claim `agents/specs.py` has made since Phase 2
   is now tested rather than asserted**, and it held. Cards cost one row there, two in `PERMISSIONS`,
   and nothing else. The one line that did change is in the red-team harness, which routed to
   `BANKING_AGENT` by name and now routes to whichever agent the case names — a one-line
   generalisation rather than a second branch, which is the evidence rather than an exception to it.
4. **`list_transactions`, bounded by the service.** ✅ No `limit` the caller can raise. Empty history
   is a spoken answer; unknown account raises.
5. **Transactions recorded inside the transfer's own transaction.** ✅ A declined transfer records
   nothing; a raising one records nothing; a failure after the history write rolls both back.
6. **`block_card` confirms and cannot act twice.** ✅ The confirmation is the model's, stated in both
   the agent instructions and the tool description. The key is relay-generated, call-scoped, and
   digit-free — driven off the generator 200 times rather than one sample.
7. **Blocking is irreversible.** ✅ No unblock function, route, or state transition, asserted on the
   module and over HTTP rather than trusted to a comment.
8. **`escalate_to_human` — `T-ESCALATION-LOGGED`.** ✅ One record with the correlation ID it was
   given, a reason from the fixed set, and a timestamp. Own exception type. **No outbound leg,
   asserted**: any outbound connection attempt during an escalation fails the test, and the relay is
   separately checked for having no call-transfer API in its namespace at all.
9. **A failed escalation record still ends the call.** ✅ The one place in the phase where a store
   failure is not fail-closed, asserted so it cannot later be mistaken for a branch somebody forgot.
10. **The call-record store, the one new seam.** ✅ Protocol, Table Storage client, fake. Built once
    per process in the lifespan, injected into the relay. Day key in a stated timezone. **Managed
    identity, no connection string** — and `boot.py` refuses one outright rather than merely not
    using one.
11. **The daily cap, fail-closed — `T-B4-FAILCLOSED`.** ✅ Four ways in (raises, times out, answers
    unreadably, genuinely spent), **one branch out**. Asserted on what the caller is told and on the
    call ending. An intact budget is asserted to serve, so a brake wired shut fails rather than
    passing everything. **The read moved from the webhook to the media socket**, recorded in the exit
    criteria with its three reasons — the decisive one being that a marker carried in the WebSocket
    URL would be client-controllable and therefore fail-open.
12. **Minutes on every path out.** ✅ Clean hangup, turn cap, wall-clock cap, exhausted attempts,
    escalation, unhandled relay failure — each with its own test. The closed path charges itself.
13. **Day boundary against an injected clock.** ✅ Instant, including a cross-timezone case.
14. **B4 blocking in CI.** ✅ Inside pytest by construction.
15. **The greeting, in its own commit.** ✅ `d891ac5`, touching nothing else. `server_vad` untouched,
    with a test saying so.
16. **R-08 recomputed — passes.** ✅ Fixed $14.60/mo, 45–67 runs/month against a gate of 5.
    `COSTS.md`. **One input unpriced** (Table Storage), with a sensitivity table showing the gate
    clears by more than four times even at an implausible $5.00/mo for it.
17. **B1 = 0 breaches, ≥120 cases.** ✅ 593 cases from 18 ideas, 542 reaching an attempt.
18. **B2 = 0 occurrences, extended to persisted records.** ✅ — with the surface below reported unmet.
19. **B3 unchanged, pin re-verified live at this gate.** ✅ Read 2026-09-11 from both the deployment
    and the Models API:

    | | |
    |---|---|
    | Deployment | `gpt-realtime-mini` **2025-10-06**, GlobalStandard, NoAutoUpgrade |
    | Retirement | **2027-04-06** — ~6.8 months out |
    | Successor | `gpt-realtime-1.5` 2026-02-23, GA, retires 2027-08-24 |

    Both match `boot.py`'s allowlist exactly. Well clear of the two-month stop-and-ask threshold, so
    the phase proceeds on this axis. Nothing has drifted from `docs/PLAN.md` decision 14.
21. **Two Bicep modules, human-reviewed, not applied.** ✅ *Written and reviewed.* The review is
    recorded in each module's header. **Applying them is #57 and has not happened.**
22. **mock-core-banking's ingress stays internal.** ✅ Confirmed in the review.
23. **No number-release call anywhere.** ✅ **Checked, not assumed**: every hit for
    release/delete/purge across all 83 shell, Python, Bicep and Makefile files is a read-only
    `phonenumber list`, an unrelated identifier, or a comment restating the rule.
28. **`make test` green, `make lint` clean, B3 static check passing, zero cloud dependency.** ✅
    mock-core-banking's suite still runs with the voice agent uninstalled.
29. **Fake and real client identical on every new operation, parity against a spawned service.** ✅
    Inside the existing spawned-service test rather than beside it. The block's idempotency is proved
    there specifically, because it is the one rule the fake can only demonstrate the shape of.
30. **Every new caller-facing sentence composed in the voice agent.** ✅ The service's prose-freedom
    test gained both new routes.
31. **Documentation amended in the commits that changed behaviour.** ✅ Partially — `CONTEXT.md` and
    the corollary rewrites are done; `docs/PLAN.md`'s Phase 5 section and `PROJECT_STATE.md`'s phase
    move belong to #60 and are not.
32. **New prose checked against `CONTEXT.md`'s Avoid lists.** ✅ And it caught one: the banking
    agent's instructions had said "specialist" for three phases, which is on that agent's own Avoid
    list. Fixed in the diff that was rewriting those instructions anyway.

### Met with a stated limit

17b. **The red-team idea count is 18 against a target of 20–30.** Phase 4 reported 13. Five ideas were
     added for the surface this phase introduced, and the count is **not padded to 20** with
     near-duplicates — a test asserts the real number rather than the target, so somebody adding one
     to reach it has to edit that line and read why they should not. **Widening a matrix is not an
     idea**: `list_transactions` and `block_card` joined nine existing matrices and roughly doubled
     the case count without adding one.

     **One idea the spec named is absent and is not counted**: a day's budget exhausted *mid-call*.
     This harness drives `run_call`, and the budget is read once on the media socket before the relay
     starts, so there is no in-call moment for the corpus to attack. Covered by the B4 suite instead,
     and stated as "this corpus cannot express it" rather than as done.

18b. **B2 covers three of its four named surfaces. Span attributes are not covered** — nothing in this
     project emits a span, so there is no surface to scan and no honest way to call the constraint
     fully met. A test now fails if anything starts emitting one, so the surface cannot become real
     and unscanned without somebody deciding to.

### Two predictions the criteria made that turned out wrong, recorded rather than smoothed

Both are in `docs/phase5/exit-criteria.md` as inline corrections, next to the criterion that made
them.

1. **Criterion 17 predicted the red-team harness's reachable-while-anonymous assertion would widen to
   "verification and escalation". It did not, and should not have.** The harness's detector watches
   the **core-banking client**, which escalation never touches — so its assertion is unchanged and is
   *stronger* than the one predicted. The gate-level statement, which *tools* an anonymous caller may
   invoke, is pinned separately in `tests/test_gate.py` as exactly `{escalate_to_human}`. Both halves
   exist; neither test says both. Reporting this criterion as met against the harness would have been
   a claim outrunning its evidence.
2. **Criterion 11 placed the budget read in the incoming-call webhook. It is on the media socket.**
   Three reasons, the decisive one being that a decision made in the webhook has to reach the media
   socket somehow, and a marker in the WebSocket URL is client-controllable on a public,
   unauthenticated endpoint — fail-open, on the one constraint whose point is failing closed.

### Not reached

**Criteria 20, 24, 25, 26, 27 are not met, and nothing here claims otherwise.**

| # | Criterion | Why not |
|---|---|---|
| 20 | **B5 frozen** | The probe is repaired, guarded, keys a PIN and takes a real service address (#54), but it has not been **run**. Running it needs a live realtime deployment and a reachable mock-core-banking, which needs #57. Phase 2's figure is untouched and still labelled for what it measured. |
| 24 | Smoke call | Needs a provisioned second container, a redeployed image, and a phone. |
| 25 | The acceptance call | Needs Marco's hands and voice. Nothing else can press `*`. |
| 26 | Evidence read out of Log Analytics | Nothing to read. |
| 27 | The four wire-format questions | **All four are still open.** No real DTMF tone has been consumed by this system, the injected item's acceptance is unverified, `*` and `#` have no observed spelling, and frame ordering is unobserved. |

### What blocks #57, precisely

Three things, and the first two are not Marco's time.

1. **`/research` owes two facts before the modules are applied.** The role definition GUID in
   `infra/modules/call-records-store.bicep` is written from documentation, not from a live
   `az role definition list` — and getting it wrong produces a role assignment that returns **200 OK
   and grants nothing**, which is precisely the "creation is not delivery" trap CLAUDE.md names. Table
   Storage's rate is the second. Named, not invoked: Marco invokes skills.
2. **A human review of both Bicep modules**, which the exit criteria require and which no tool here
   can substitute for — there is no `bicep` CLI in this environment and still no `main.bicep`.
3. **A Docker build and push, a redeploy, and a smoke call.** The image carries Phases 3, 4 and 5 at
   once, which is three phases of unproven-in-production code on one image — and **Phase 4's own diff
   is still unreviewed** (`git log e42c063..HEAD`), which is the entry condition that was waived
   rather than met. The smoke call exists for exactly this and is part of the plan rather than
   caution.

---

## Carried forward, unchanged

- **The four wire-format questions**, all open, all closing on the acceptance call or not at all.
- **No response deadline on the injected PIN-outcome frames** — deliberately sequenced behind the
  evidence.
- **`transport/acs.py`'s audio branch is not total**, pinned by a test so it is known rather than
  folklore.
- **Whether the FastAPI, httpx and requests instrumentations capture bodies by default** — unsettled,
  and it must be settled before Phase 6 enables anything.
- **`RequestResponse` is not enabled** and must not be until its destination table has been read.
- **`git log e42c063..HEAD` is still owed a human read.**

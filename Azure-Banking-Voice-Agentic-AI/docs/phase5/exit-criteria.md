# Phase 5 — Intents + cost controls: exit criteria

> **APPROVED by Marco 2026-09-11**, in one message: `APPROVED: Phase 5. /implement all 18 tickets.`
>
> **What that message is read as covering, stated precisely rather than assumed**, because the three
> approvals below are different things and this file is where the difference was written down:
>
> | approval | state |
> |---|---|
> | Begin the phase | **Given** — "implement all 18 tickets" |
> | `APPROVED: Phase 5` for billable resources | **Given** — the verbatim token `CLAUDE.md` requires |
> | The escalation corollary sign-off | **Read as given**, see below |
> | Phase 4 sign-off | **Still not given** — waived by instruction, not met |
>
> **The escalation sign-off is read as given because ticket 1 is this document** and the instruction
> was to implement all eighteen. It is recorded this way rather than silently assumed: it is a
> named constraint's corollary, and it is a **data change in `dispatch/gate.py`'s permission table**,
> so it is reversible by editing one row if this reading is wrong. B1's target does not move either
> way.
>
> **Phase 4 remains unreviewed.** `git log e42c063..HEAD` was not looked at before this phase began.
> That is recorded as an entry condition **waived**, not as one satisfied, and it is the reason
> criterion 24's smoke call matters more here than it would otherwise.

**Written at phase kickoff, 2026-09-11**, before the work rather than reconstructed after it. Spec:
GitHub issue **#43** (`ready-for-agent`, filed 2026-09-11). Tickets: **18**, filed as sub-issues of
#43 on approval.

---

## Entry conditions — one is NOT satisfied

| condition | state |
|---|---|
| Phase 4's exit criteria written | **Satisfied** — `docs/phase4/exit-criteria.md`, approved 2026-09-10 |
| Phase 4's exit criteria met | **Satisfied, with three stated limits** — `docs/phase4/exit-check.md` |
| **Marco's sign-off on Phase 4** | **WAIVED by instruction 2026-09-11, not met** |
| Marco's approval to begin Phase 5 | **Given 2026-09-11** |

**Phase 4 is built and unreviewed.** Everything after `e42c063` is committed and has not been looked
at by Marco — `git log e42c063..HEAD`, stated as a range because a fixed count was written into
`PROJECT_STATE.md` twice and was wrong both times, for the structural reason that the commit updating
the number is itself uncounted when it is written. **Every commit in that range except the findings
one touches the DTMF/PIN path**, so the never-auto-accept rule binds all of them.

Phase 5 builds directly on top of that range: it widens the same permission table, injects through the
same mechanism Phase 4 built, and deploys the same relay for the first time. **Starting Phase 5
before that review happens puts three phases of unreviewed code on one image and removes the last
point at which Phase 4 could be sent back cheaply.** This is recorded as an entry condition rather
than a note, because it is one — and it was **waived on 2026-09-11 rather than satisfied**. The
consequence is carried forward, not discharged: criterion 24's smoke call is the only place a
three-phase-wide failure gets found on a call nobody is grading, and `git log e42c063..HEAD` is still
owed a human read.

Phase 4's three stated limits, carried in as facts rather than discovered later: criterion 7's
injected item is confirmed in shape and unverified in acceptance, criterion 9's red-team idea count is
**13 against a target of 20–30**, and criterion 10's OTel surface is vacuous because nothing emits
spans.

---

## Three approvals, and they are different things

None of the three implies either of the others.

1. **Approval of these exit criteria**, which is what lets the phase begin at all.
2. **`APPROVED: Phase 5`**, which is what lets a billable Azure resource be created. This is the
   first phase since Phase 0 to create any: a second Container App for mock-core-banking, and a
   Storage account for the call-record store. **The R-08 recompute (criterion 16) is its own
   precondition** and comes first.
3. **The sign-off below**, on a named constraint's corollary, which is required before the phase
   starts in the same way B1's sharpening was at Phase 4.

---

## Required Marco's explicit sign-off before the phase began — read as given 2026-09-11

**`escalate_to_human` is granted to an unauthenticated call.**

**B1's target does not move, and its sharpened definition holds exactly.** Still 0 breaches across
≥120 adversarial cases, still L1, still blocking. No *banking* operation — balance, transfer, list,
and now transactions and card block — reaches the core-banking client while the call is
unauthenticated. Escalation never touches that client at all, so B1 is untouched by this.

What changes is a **corollary** this project has stated in three places: `dispatch/gate.py`'s
permission-table comment, `docs/PLAN.md` decision 7, and `docs/phase4/exit-criteria.md`'s scope-change
section. All three say some form of:

> no tool at all is reachable while a call is anonymous

**After this phase that sentence is false**, and it must be rewritten wherever it appears to say that
the only things reachable while anonymous are **PIN verification and asking for a person**, neither of
which is a banking operation.

The alternative is a caller who is locked out of authentication and also cut off from a human, which
is a worse bank.

**Read as signed off on 2026-09-11**, by the instruction to implement all eighteen tickets when ticket
1 is this document. Recorded as a reading rather than as a quoted approval, because that is what it
is. One row of `PERMISSIONS` reverses it.

> **B1 (corollary, restated).** The set of operations reachable while a call is anonymous is *exactly*
> PIN verification and `escalate_to_human`. Neither is a banking operation, neither reaches the
> core-banking client, and a test asserts that set is exactly those two.

---

## Never-auto-accept — three rules bind diffs here, not two

1. This phase **adds rows to `dispatch/gate.py`**.
2. This phase **touches the relay carrying the DTMF path**, for the greeting, the closed path, the
   injected escalation, and the idempotency key.
3. This phase **provisions billable resources**.

In this phase that is most of the diffs. Each gets a human look however mechanical it appears.

**The phone number `+17059100383` is never released, by any script, at any phase, for any reason.**
Restated here rather than assumed, because this is the first phase since Phase 0 to write
teardown-adjacent infrastructure.

---

## The criteria

### The gate and the agent table

1. **The permission table grows to six rows and five tools, and `is_allowed()` is untouched for the
   second phase running.** All six `(agent, auth_state)` pairs are written out, including the ones
   that grant nothing, so the table keeps stating its own completeness as it grows:

   | agent | auth state | tools |
   |---|---|---|
   | triage | anonymous | `escalate_to_human` |
   | triage | authenticated | `escalate_to_human` |
   | banking | anonymous | `escalate_to_human` |
   | banking | authenticated | `get_balance`, `transfer`, `list_accounts`, `list_transactions`, `escalate_to_human` |
   | cards | anonymous | `escalate_to_human` |
   | cards | authenticated | `block_card`, `escalate_to_human` |

   The pinned permission-table test is updated in the same diff, so every widening of B1 shows up in a
   diff and cannot be an accident.

2. **The exhaustive cross-product is still generated from the declared tool list**, not
   hand-maintained: five tools by six pairs, plus the pinned literal.

3. **A third agent joins the table, and it is a table row.** Cards holds `block_card` and nothing
   else. Triage declares a handoff edge to it; banking does not, and Cards declares none back.
   Handoff stays outside the gate. **Adding the row is expected to require no change to `session.py`'s
   handoff handling, to `dispatch/gate.py`'s logic, or to `handoff_target()`** — `agents/specs.py`
   already claims this, and this is the phase that tests the claim. **If any of those needs changing,
   that is a finding about the Phase 2 design and is recorded rather than absorbed.**

### The three intents

4. **`list_transactions`** takes an account name and returns the most recent transactions for it,
   **bounded by the service** rather than by the model's restraint, and small enough to read aloud on
   a phone. Each transaction says what it was and what it moved. An account with no transactions is a
   normal spoken answer, not an error. An unknown account **raises**, exactly as `get_balance` does.

5. **Transactions are recorded by the system of record when a transfer completes**, inside the same
   database transaction as the balance updates, so the history and the balances cannot disagree. The
   seeded profile gets a small seeded history, so a demo call has something to read on the first run.

6. **`block_card` asks before it acts, and cannot act twice.** The confirmation is **the model's**,
   driven by the Cards agent's instructions and the tool's own description — not a second tool call
   and not a state the gate knows about. The **idempotency key is generated by the relay, scoped to
   the call**, and sent with the block; the service stores it beside the outcome and answers a repeat
   with the recorded outcome rather than blocking again. The key is opaque and **carries no decimal
   digit**, for the same reason the injected frame ids do not.

7. **Blocking is irreversible here.** No unblock tool, no unblock route, no state transition back. A
   blocked card resets when the container restarts, which is the same ephemeral-filesystem behaviour
   Phase 3 settled for balances. The caller is told the block cannot be undone on this line.

8. **`escalate_to_human` ends the call and writes a record — `T-ESCALATION-LOGGED`.** It takes a
   **reason code from a fixed set** and nothing else, so the record is queryable rather than free
   prose. It writes call correlation ID, reason code and timestamp through the call-record store, then
   ends the call through the relay's expected-ending branch **with its own exception type**, so a
   routing event, a security event and a cost event stay distinguishable in every log that reads them.
   **No outbound leg is ever attempted**, and a test asserts no ACS transfer API is reachable from this
   path.

9. **A failed escalation record still ends the call.** Reaching a person matters more than recording
   that someone asked to. The failure is logged loudly and the caller hears the same apology. **This is
   the one place in the phase where the store failing is not fail-closed, and it is deliberate.**

### The call-record store — the one new seam

10. **One new package beside `core_banking/`, `transport/` and `realtime/`: a protocol, an Azure Table
    Storage client, and a fake.** Same shape as the three seams already there — a real module rather
    than a test helper, structurally satisfying the protocol, injected rather than patched.

    - **Two operations, one protocol**: read and record the day's consumed call minutes, and append an
      escalation record. Distinct methods, not distinct modules — one store, one fake, one Bicep
      module, one fail-closed story.
    - **Built once per process**, in the app's lifespan beside the core-banking client, never per call
      — the reason a per-call circuit breaker can never trip.
    - **The day is a date in a stated timezone**, written down in the module rather than inherited from
      the container's locale, so "today" means one thing in the ledger, in a log line, and in a query.
    - **Authentication to Storage is by managed identity.** The Container App's system-assigned
      identity gains a data role on the Storage account; **no connection string is stored anywhere.**
    - **The call correlation ID is handed to the relay**, so an escalation record can carry it without
      the relay reaching back for it.

### B4, completed

11. **The daily aggregate cap exists and fails closed — `T-B4-FAILCLOSED`.**
    - `cost/caps.py` keeps its per-call constants **unchanged**: 20 turns, 5 minutes. Neither moves.
    - **The day's budget is read before `answer_call`**, in the incoming-call webhook, so a call that
      will not be served costs the webhook and nothing more.

      > **Changed while building, 2026-09-11 (issue #49).** It is read on the **media socket**
      > instead, immediately before the realtime connection is opened. Three reasons, recorded
      > rather than the criterion quietly missed:
      >
      > 1. The closed path has to **answer and speak** — the user story this criterion rests on is
      >    that a caller hears "we're closed" rather than a dead line. So the call is answered
      >    either way, and what the earlier placement actually saved was the realtime connection,
      >    which the closed path needs in order to say anything at all.
      > 2. A decision made in the webhook has to reach the media socket somehow. Every way of
      >    carrying it is either process-wide mutable state or a marker in the WebSocket URL — and
      >    **the second is client-controllable**, because that endpoint is public and
      >    unauthenticated until Phase 7. A marker there would let whoever opens the socket choose
      >    to be served, which is fail-open on the one constraint whose point is failing closed.
      > 3. Read on the media socket, the check sits on the only path a call actually takes and
      >    cannot be bypassed.
      >
      > The cost is the realtime connection a closed call still opens. `budget_or_closed`'s own
      > docstring carries this reasoning where somebody changing it will read it.
    - **The closed path**: answer, inject the closed sentence through the mechanism Phase 4 built for
      PIN outcomes, hang up. **Hard-bounded to a single turn and a short wall clock**, enforced by the
      relay rather than by the model choosing to be brief. A brake that cost a full call would be a
      brake that spends money to refuse spending money.
    - **Unreadable is the same as exhausted.** A store that raises, times out, or returns something the
      client cannot read produces the closed path. **There is no branch in which an unknown budget
      serves a call.**
    - Asserted at the whole-call seam, on what the caller is told and on the call ending — never on an
      internal flag.

12. **Consumed minutes are recorded when the call ends, on every path out**, in the same cleanup the
    authenticator's buffer is zeroed in — including the paths that raise. Asserted for a clean hangup,
    a turn cap, a wall-clock cap, exhausted attempts, an escalation, and an unhandled failure. **The
    closed path's own minutes count too**: a brake whose usage was invisible in the one place it
    matters would not be a brake anyone could audit.

13. **The day boundary is tested against an injected clock**, the way the circuit breaker's open window
    already is, so a date rollover is instant rather than a day long.

14. **B4 is blocking in CI**, alongside B1 and B2. **0 overruns, 0 fail-open events.**

### The greeting — unparked

15. **The agent greets and asks for the PIN without waiting for the caller to speak.** An initial
    `response.create` after the opening `session.update`. **In its own commit, touching nothing else in
    the phase**, so a regression on a real call is attributable to it or to the intents and never to
    both.

    This item was parked at Phase 3 kickoff and again at Phase 4's. **It is unparked here** because
    this phase's exit depends on a caller keying a PIN they are currently never asked for.

### The constraints

16. **R-08 is recomputed against a two-Container-App fixed cost before anything is applied**, from
    meters this project has actually measured rather than from the plan's estimate — the measured
    Container Apps operating mode, the number lease, the eval ceiling, and the confirmed per-minute
    rates. Recorded in `COSTS.md` with its inputs. **If the recomputed figure fails its own gate, the
    phase stops there and the design changes.** The $25/month claim is part of what this project
    demonstrates, not a target to renegotiate.

17. **B1 = 0 breaches across ≥120 adversarial cases, blocking in CI**, against the sharpened definition
    and the restated corollary above.
    - The harness's banking-operations set gains `list_transactions` and `block_card`, so a case
      reaching either while anonymous is a breach **at the detector** rather than by inspection.
    - The test asserting the reachable-while-anonymous set becomes "exactly verification and
      escalation" — **that assertion is the mechanical statement of the signed-off item above.**

      > **Corrected while building, 2026-09-11 (issue #48).** This criterion predicted the wrong
      > test. The red-team harness's detector watches the **core-banking client**, and escalation
      > never reaches it — so the harness's assertion is *unchanged* and still reads "exactly
      > verification", which is a stronger statement than the one predicted here. The gate-level
      > statement, which tools an anonymous caller may invoke, is pinned separately in
      > `tests/test_gate.py` as exactly `{escalate_to_human}`. **Both halves exist; neither test
      > says both.** Recorded rather than quietly satisfied, because reporting this criterion as met
      > against the harness would have been a claim that outran its evidence.
    - Each idea's matrix widens to the new tools and the third agent; argument strategies gain payloads
      for the new tools, since a payload that is absent is a case that does not exist.
    - **Both numbers are reported wherever the suite is described.** The new surface plausibly moves the
      idea count from 13 toward the 20–30 aimed for. **If it does not, the real number is reported and
      the shortfall explained** — never padded with near-duplicates.

18. **B2 = 0 occurrences, blocking in CI, extended to the first persisted records the voice agent
    owns.** The run-wide capture and artifact scan are unchanged in mechanism; **the store's records
    join the scanned artifacts**, because B2 names persisted records. Identifiers this phase generates
    — the idempotency key above all — are built so they **cannot contain a decimal digit**, for the
    same reason the injected frame ids are: a random hex identifier can spell a four-digit credential by
    chance and turn a run-wide scan red on a coincidence.

19. **B3 unchanged, and the pin re-verified live at this gate.** The active pin's retirement date is
    read from the Models API and from the live deployment, as at every phase gate. Under two months of
    runway with no better GA option is a stop-and-ask before the phase proceeds.

20. **B5 is frozen, and the frozen figure states its turn count and what was in the path.**
    - `scripts/b5_probe.py` is repaired. It has been passing two arguments to a three-argument
      `run_call` since Phase 3 and raises `TypeError` before opening a connection. **It gains a cheap
      guard that fails when its signature drifts**, so an ops tool cannot rot unnoticed through two more
      phases.
    - **The probe keys a PIN so the gate grants, and runs against a reachable mock-core-banking**, so a
      tool call is a real round trip. Without both, it would re-measure Phase 2's refusals under a new
      name.
    - **Two pools, stated separately and never merged into one unlabelled figure**: real calls carry the
      full ACS media relay, the probe does not. Both are reported with their N.
    - **Phase 2's 932 ms across 106 turns is superseded in place, kept, and labelled** with what it
      actually measured — a gate that refused every tool call, so the core-banking hop was in the path
      zero times. Not merged into the frozen pool, not deleted.
    - **The frozen figure will very likely be worse than the provisional one, and that is the point.** A
      frozen figure that improved on it would be evidence the measurement was wrong rather than good
      news.

### Provisioning, deployment, and the call

21. **Two Bicep modules, both human-reviewed before they are applied**: the existing, never-validated
    `mock-core-banking` module, and a new one for the Storage account and the identity's data role.
    There is no `bicep` CLI here and still no `main.bicep`, so "consistent with the existing modules"
    has exactly one sibling to be consistent with. **Neither is auto-accepted.**

22. **mock-core-banking's ingress stays internal.** That is what keeps deferring shared-secret auth to
    Phase 7 a considered decision rather than a PIN crossing the public internet in a request body.

23. **No script written or touched in this phase contains a number-release or number-delete call**, and
    the teardown path is **checked** for one rather than assumed clean.

24. **A smoke call comes before the acceptance run.** The voice agent is redeployed for the first time
    since Phase 2, carrying Phases 3, 4 and 5 at once. **That is three phases of unproven-in-production
    code landing on one image**, and it is named as a risk here rather than discovered on the call. A
    boot failure or a broken relay is found on a call nobody is grading.

25. **One acceptance call, scripted in advance, dialled by Marco.** It must:
    - authenticate with a **real keyed PIN**;
    - **press `*` and `#` deliberately** — a digits-only call leaves the tone-vocabulary question
      exactly as open while looking settled;
    - reach **all four intents**: `get_balance`, `list_transactions`, `block_card`,
      `escalate_to_human`;
    - hit **at least one refusal before authenticating**;
    - **end by escalating.**

26. **Evidence is read back out of Log Analytics** — workspace `workspace-rgazurebankingvoiceagenticai1D`
    (`bf520f2c-e2bc-4488-8965-9317a7922c74`), **never the stale `...aiCS`** — and not asserted from the
    call going well. **A diagnostic setting returning ARM 200 OK proves creation, not delivery.**

27. **Four wire-format questions are recorded as closed or open on what that log contains**, each one
    reading as answered or open rather than assumed:
    1. whether Azure's GA endpoint and `gpt-realtime-mini` `2025-10-06` **accept the injected system
       message**;
    2. how **`*` and `#` are actually spelled** on the media-streaming path;
    3. whether **DTMF and audio frames arrived in the order they were produced** — observed by reading
       the payload's `timestamp`, which nothing reads today, not assumed;
    4. whether **a real keyed tone drives the authenticator at all** — no real DTMF tone has ever been
       consumed by this system.

### The suites and the docs

28. **`make test` green across both suites with zero cloud dependency**, `make lint` clean, the B3
    static allowlist check still passing. **The phase that provisions two resources still costs nothing
    to verify.** mock-core-banking's own suite keeps running with the voice agent uninstalled.

29. **The fake and the real client behave identically on every new operation**, with the parity table
    **driven against a really spawned service** over a real socket — extended inside the existing
    spawned-service test rather than beside it, so it cannot rot into a constant somebody typed.

30. **Every new caller-facing sentence is composed in the voice agent**, never in the system of record,
    so the inversion Phase 3 corrected does not return through a new route. Asserted mechanically, as
    it already is.

31. **Documentation is amended in the commits that change behaviour, not after.** `CONTEXT.md` gains
    the terms this phase introduces — **Cards agent, transaction, card, block, escalation, the closed
    path, the call-record store, idempotency key** — each with its *Avoid* list. `docs/PLAN.md`'s
    Phase 5 section records what was actually delivered, including the honest red-team idea count.
    `COSTS.md` records the recomputed R-08 with its inputs. `PROJECT_STATE.md` moves Phase 4 into the
    closed table and Phase 5 into current, **under its ≤400-line / ~20 KB ceiling**, moving the oldest
    closed material out in the same commit if the addition would exceed it.

32. **New prose is checked against `CONTEXT.md`'s *Avoid* lists**, which caught four terms in Phase 4
    across log lines, caller-facing sentences and comments. Note that triage's current instructions say
    **"the banking specialist"**, and *specialist* is on the banking agent's own *Avoid* list. This
    phase rewrites those instructions anyway to add the Cards edge, so it is the natural moment to fix
    it.

---

## Known-partial, recorded up front

Stated here so none of it is discovered later and reported as a surprise.

1. **Span attributes remain an uncovered B2 surface**, because nothing emits spans. B2 covers three of
   its four named surfaces. **Reported as unmet, never quietly counted.** Phase 6 is its fix.
2. **No response deadline on the injected PIN-outcome frames.** Telling a rejection from silence needs
   the error type, a correlated id, **and the relay's own timeout**. The first two exist; the third does
   not, so an injection that is simply never answered still looks accepted. **Deliberately sequenced
   behind the evidence**: if the real call shows the injected item accepted, the deadline is insurance
   against a case never observed; if it shows it refused, the deadline becomes urgent and gets its own
   scoping.
3. **`transport/acs.py`'s audio branch is not total**, unlike its DTMF branch. A malformed `AudioData`
   frame raises `KeyError` on the inbound relay task and ends the call. Pinned by a test so the
   behaviour is known rather than folklore. **Not changed here** — relay behaviour nobody asked to
   alter, on a path the never-auto-accept rule covers.
4. **Whether the FastAPI, httpx and requests instrumentations capture request or response bodies by
   default is still unsettled.** Cheap to settle by reading source. It **must be settled before Phase 6
   enables anything** — a body-capturing default would put DTMF frames into telemetry. Carried, not
   closed.
5. **The `RequestResponse` diagnostic-log category is not enabled** on `aoai-azure-banking-voice-cc`
   and must not be until its destination table has been queried and read. A candidate fifth B2 surface
   whose name is the only thing anyone knows about it.
6. **No Bicep module in this repo has ever been validated by any tool.** There is no `bicep` CLI here
   and no `main.bicep`. Human review is the only check that exists.
7. **Three phases land on one image.** A failure on the first real call has a three-phase-wide search
   space. Criterion 24's smoke call exists for exactly that and is part of the plan rather than caution.
8. **No durable ACS-side call-diagnostics path exists.** App-side container logs deliver correctly;
   ACS-side call diagnostics were never configured. It matters more now that a gate's and a brake's
   failures need auditing. Phase 6 is its real fix.

## Deliberately parked, carried forward

Listed so they are not re-litigated at the next boundary either.

- **The intermittent interrupt-the-caller defect.** Scoped as `server_vad` configuration tuning, not
  new code, once and if it reproduces. **Explicitly not touched here**: this phase already changes when
  the agent first speaks, and changing turn detection in the same phase would make a regression
  unattributable.
- **`transfer`'s no-retry rule.** This phase builds the idempotency mechanism and applies it to
  `block_card` only. `docs/PLAN.md` says Phase 5 *may* revisit the rule; this phase declines. Making a
  timed-out transfer retryable would rewrite an outcome `CONTEXT.md` defines, a sentence the caller
  hears, and a latency budget being frozen in the same phase. Offered as a follow-up, not dropped.
- **`02-test-calls.sh`'s missing re-run guard.** Still worth an `--extract-only` flag, still not this
  phase's.
- **Docker Hub versus ACR.** Still on Docker Hub. A real ~$5/month if decided the other way, which
  makes it R-08's business rather than this phase's.
- **The stale `az` CLI `defaults.location=eastus`** on this machine. Fix identified, shown as a diff,
  still pending sign-off.
- **The root `CONTEXT-MAP.md`.** Outside `PROJECT_ROOT`, needs approval by absolute path.
- **R-03's Call-1 zero-DTMF anomaly**, permanently unresolved for Call 1 — its evidence no longer
  exists.
- **`gpt-realtime-1.5` successor boot**, untested against a real successor. The rehearsal exists and is
  skipped by design.
- **The rate-limit meaning question** — the Models API's per-deployment `rateLimits` field does not
  reconcile against the documented subscription-level Quota Tier table. A ~30-second Foundry-portal
  check, still not done.

**One item is unparked rather than carried**: the dead-air gap before the agent's first words, now
criterion 15.

## Out of scope, named so none of it is silently assumed

- **Observability** — no OTel, no spans, no App Insights resource, no redaction processor. Phase 6.
  This phase creates the first durable records whose auditing Phase 6 will want and is still not the
  phase that builds the audit path.
- **Unblocking a card**, **more than one card or profile**, **a real human behind an escalation**, and
  **outbound calling of any kind** — no transfer leg, no callback, no SMS.
- **Shared-secret authentication or TLS on the internal hop.** Phase 7. Internal ingress is what makes
  that deferral safe rather than an omission.
- **`main.bicep`, the Typer deploy CLI, and the root `ci`/`deploy`/`teardown` workflows.** Phase 7.
  This phase adds its two modules incrementally and applies them by hand, as every phase so far has.
- **Post-call analytics, transcript persistence, evals.** Phase 8.
- **Any change to B1's, B2's, B3's or B4's numeric targets.** None moves. B5's is measured here for the
  first time with tool calls in the path and is frozen at whatever it measures.

## Assumptions carried, not confirmed

Stated so they are visible rather than silent. Any one can be overruled without disturbing another
criterion.

1. **Adding the Cards row needs no change** to `session.py`'s handoff handling, `dispatch/gate.py`'s
   logic, or `handoff_target()` (criterion 3). If it does, that is a finding about the Phase 2 design.
2. **The closed path can reuse Phase 4's injection mechanism** without introducing a second way of
   making the agent say something it did not decide (criterion 11).
3. **Azure Table Storage is reachable from Container Apps using the system-assigned identity with a
   data role and no connection string** (criterion 10). Not yet verified against anything live. This is
   a `/research` question before it is a code question.
4. **The call correlation ID is available to the relay** from the media WebSocket's headers, which
   `app.py` already reads at accept time (criterion 10).
5. **The acceptance call's `*` and `#` presses will appear in the log in some readable spelling**
   (criterion 27.2). If they arrive in a form the classifier accepts but the log renders
   indistinguishably, the question stays open and is reported open.

## The recurring defect this phase is most exposed to

**A claim that outruns its evidence.** It happened three times in Phase 4, each time inside the fix
for the previous one. This phase has more opportunities than any before it: a provisioned resource
whose ARM 200 proves creation and not delivery, a diagnostic path whose destination table must be
queried before anything is called verified, a cap that must be **observed tripping** rather than
reasoned about, and a real call that will be tempting to describe as having closed questions it only
touched.

**Before writing "verified", run the thing and read the result.**

## Skills this phase calls for

Named here, not invoked — Marco invokes skills.

- **`/wizard`**, because the core of this phase is a human-in-the-loop step Claude cannot perform:
  provisioning that needs a live decision, and a real phone dialled by a real person pressing real
  keys. Phase 0 ran exactly this way.
- **`/research`** for any remaining factual unknown before the call — Table Storage pricing and data
  role names, the ACS answer-then-play path, anything about the media-stream frame. Never from memory.
- **`/code-review`** before the gate, no exceptions.
- **`/prototype`** only if the closed path's shape turns out to be a genuinely unresolved design
  question rather than a small piece of relay work.

**Model policy**: design and exit-criteria authoring on Opus; implementation inside the approved phase
on Sonnet. Diffs touching the gate, the DTMF path, or a billable resource are never auto-accepted — in
this phase that is most of them.

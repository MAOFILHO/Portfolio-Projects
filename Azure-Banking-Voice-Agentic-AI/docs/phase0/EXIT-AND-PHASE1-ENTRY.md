# Phase 0 exit criteria & Phase 1 entry criteria

Written 2026-08-28. Sources: `docs/PLAN.md` (R-01–R-09 definitions, Budget), `PROJECT_STATE.md`
(current-state open items), `docs/phase0/findings.md` (full derivations), and the handoffs dated
2026-08-24, 2026-08-27, plus this week's read-only investigations (2026-08-28, not yet in any
handoff file). **This document does not itself decide anything** — Part 3 is explicitly options,
not decisions, per instruction.

**The 2026-08-24 closeout handoff predates everything found 2026-08-27 and 2026-08-28. Treat it as
superseded wherever the two conflict** — flagged inline below, not silently merged.

**Provenance vocabulary used throughout** (per this week's established discipline — do not call
anything measured that is modeled or hand-entered):
- **measured** — read directly from telemetry (Azure Monitor metrics, app logs) for this project's
  own run.
- **modeled** — a rate or figure from a published source (Retail Prices API, PLAN.md's own
  estimate) applied to measured or assumed quantities; not an observed dollar amount.
- **verified live** — checked directly against a live API response at the time stated (not memory,
  not documentation).
- **hand-entered** — typed by a human at an interactive prompt; not read from any meter or API.
- **asserted** — a standing fact or policy decision, not an empirical question with a pass/fail
  test.

---

## Part 1 — Phase 0 exit criteria, retrospective (R-01 through R-09)

### R-01 — Model deprecation-date conflict
**Asked**: does `gpt-realtime-mini` carry a live, unambiguous retirement date, resolving the
conflicting dates found in early scoping?
**Status: ANSWERED.** Live Models API query, 2026-08-20: `2025-10-06` retires `2027-04-06`,
`2025-12-15` retires `2026-12-15` — both real, the earlier date is the pessimistic case used for
planning. **Provenance: verified live against the Models API.** Closed; B3 now carries the pinned
version plus a documented successor (`gpt-realtime-1.5`), reviewed at every phase gate rather than
trusting a single frozen date.
**Changed since 08-24? No.**

### R-02 — `Pcm24KMono` clean bidirectional audio
**Asked**: does ACS's `Pcm24KMono` streaming format deliver clean 24 kHz PCM16 both ways, justifying
the decision to delete the resampler on a documentation-only assumption?
**Status: ANSWERED.** All 3 connected test calls (2026-08-21) echoed audio continuously with no
gaps, no errors, and steady per-frame processing latency (~0.1–0.2ms, app-side recv-to-echo,
sampled roughly once per second across all three calls — see `findings.md` "R-02/R-03/RTT — evidence
from 3 test calls"). No resampling artifact or distortion reported by either party on any call.
**Provenance: measured**, from the app's own logs during real calls.
One caveat carried over verbatim from `findings.md`: this is **app-side processing latency**
(frame received → frame re-sent), not full caller-to-caller round-trip — it answers R-02's own
question (does the format work cleanly) but is not itself a B5 latency figure.
**Changed since 08-24? No.**

### R-03 — `DtmfData` during active bidirectional streaming
**Asked**: do DTMF tones arrive reliably at the app while media is actively streaming?
**Status: PARTIALLY ANSWERED.** Confirmed on Calls 2 and 3 — 6/6 tones each, landing mid-stream with
clean per-digit timestamps. **Call 1 registered zero tones despite Marco pressing keys during it**,
and nothing in duration, frame count, or event ordering explains the miss. Cold-start/scale-from-zero
was tested as a candidate explanation and **ruled out** 2026-08-24 (single boot 80s before Call 1,
single replica ID throughout, a completed unrelated HTTP round-trip 74s before Call 1 proving the app
was already warm). **Provenance: measured** (2/3 confirmed from real-call logs); the residual gap is
an absence of evidence, not itself a measurement.
**Changed since 08-24 — flagged explicitly:** the 08-24 closeout framed the blocker as "the Log
Analytics zero-rows gap must close" (`PROJECT_STATE.md` open item 10, at the time). The 08-27
investigation found the *actual* root cause of that gap was a table-name/diagnostic-setting
misconfiguration specific to **app-side** container logs (`ContainerAppConsoleLogs`/
`ContainerAppSystemLogs`) — and that the native `appLogsConfiguration` path was delivering correctly
into `_CL`-suffixed tables the whole time. **That fix does not produce ACS-side call diagnostics.**
`findings.md`'s own words: "that data source does not exist in either Log Analytics workspace... it
would have to come from ACS itself" — a Log Analytics ingestion problem and an ACS-side-diagnostics
absence are two different gaps, and only the first has actually been explained. R-03's real blocker
is, and always was, the second one, which as of 2026-08-28 has never been configured, attempted, or
even scoped. See Part 3(b).

### R-04 — Idle-vs-active Container Apps billing
**Asked**: does an open-but-silent WebSocket between calls keep a Container App replica
active-billed?
**Status: ANSWERED — IDLE.** Azure Monitor `Replicas` (299 datapoints, 0 scale-to-zero gaps) and
`RxBytes`/`TxBytes` (299 intervals, only the expected call-3 tail interval over the 1,000 B/s
threshold) both measured directly over the full ~72h window. Cost: **$5.72/mo**, net of Container
Apps' free compute grant, at Canada Central Retail Prices API rates.
**Provenance: measured** (replica continuity, network bytes) **+ modeled** (dollar figure — rates
from the Retail Prices API applied to the measured usage; no Cost Management dollar total ever
confirmed this, both of that run's Cost Management queries failed).
**Changed since 08-24? No** — this is the closeout's own headline number, reconfirmed at teardown,
untouched by anything found 08-27/08-28.

### R-05 — ACS data-location / number inventory
**Asked**: is ACS number purchase coupled to data-residency location, and is a Toronto-area (or
equivalent) number actually purchasable?
**Status: ANSWERED.** No coupling found. Toronto itself was found entirely absent from ACS's
Canadian geographic-locality inventory (not filtered — genuinely not present in an unfiltered,
country-wide query); real-time inventory volatility also observed directly (a locality present at
one check, gone ~20 minutes later). Triggered the decision-13 revision to 705/North Bay, confirmed
purchasable via a live `Search Available Phone Numbers` call.
**Provenance: verified live against the ACS number-search API.**
Closed 2026-08-20. **Changed since 08-24? No.**

### R-06 — DataZoneStandard deployment availability
**Asked**: is `DataZoneStandard` an available fallback SKU for the realtime model deployment?
**Status: ANSWERED — NOT OFFERED.** A live deployment attempt returned an explicit, unambiguous
`InvalidResourceProperties` error naming the SKU/model/version combination as unsupported — not a
quota or permission error that might resolve differently later.
**Provenance: verified live against the deployment API.**
Closed 2026-08-20. **Changed since 08-24? No.**

### R-07 — `spendingLimit: Off`
**Asked**: will Azure stop spend at any subscription-level threshold?
**Status: ANSWERED — no, it will not.** Standing subscription configuration, not an empirical
question with a pass/fail test.
**Provenance: asserted** (a confirmed subscription setting, restated as policy — the $20 budget
alert that exists alongside it is notification-only, not a brake). B4 (the app's own fail-closed
logic) is the only actual brake.
**Changed since 08-24? No.**

### R-08 — Demonstrability (enough call-minutes left for real demos)
**Asked**: after fixed costs and eval budget, is there enough of the $25/mo ceiling left for
repeated demo/portfolio calls?
**Status: ANSWERED — gate PASSES, conditional on R-04's IDLE operating mode continuing to hold.**
On the active-cost path, the same script's own arithmetic returns 0 runs/month, under the 5-run
floor, triggering its own ⛔ R-08 GATE FAILED stop condition. Both paths, from
`04-teardown-and-r08.sh:294-309`'s own formula (`left_for_calls = 25.0 − fixed − 6.0`;
`runs = (left_for_calls / per_min) / 5`; hard-set to 0 if `left_for_calls ≤ 0`):

- **Idle path** (fixed = $6.72): `left_for_calls = 25.0 − 6.72 − 6.00 = 12.28`;
  `12.28 / 0.031 = 396.13` min; `396.13 / 5 = `**`79.2 runs/month`** — floor met. This is the
  teardown-confirmed figure, computed at $0.031/min (deliberately the pessimistic end of PLAN.md's
  $0.0215–$0.031 range, so the pass holds regardless of which end is closer to reality).
- **Active path** (fixed = $21.03): `left_for_calls = 25.0 − 21.03 − 6.00 = −2.03 ≤ 0` →
  **`0 runs/month`** — floor not met, script's own STOP condition fires.
**Provenance is mixed, and worth stating precisely rather than folding into one word:**
- The **$6.72/mo fixed** input chains from R-04's genuinely **measured** telemetry ($5.72 idle
  Container Apps, modeled at Retail Prices rates) plus a **hand-entered** $1.00 phone-number
  constant.
- The **$0.031/min** input was **hand-entered** at the teardown script's interactive prompt — free
  text, matching the upper end of PLAN.md's own suggested range, **not read from any per-minute
  billing meter**. `findings.md` records explicitly that **who answered that prompt is unknown from
  any tracked record** (unlike an equivalent Stage 3 prompt earlier in the project, which does carry
  that disclosure).
- **No dollar figure in R-08 comes from an actual Cost Management billing query** — both of the
  teardown run's Cost Management queries failed.
So: **modeled + hand-entered, not measured**, in the strict sense of this vocabulary. The gate result
on the idle path (PASSES, comfortably above a 5-run floor) is the same both before and after teardown
(~79–114 pre-teardown estimate vs. 79.2 confirmed), so that verdict itself is stable — but the
provenance caveat (unattributed hand-entry) was only recorded 2026-08-24, sharpening the confidence
rating without reversing the result.
**Changed since 08-24? No reversal, and no re-derivation was needed: `R04_MONTHLY_NET_OF_GRANT` is
computed in-script from hardcoded Canada Central rates (`:194-219`), confirmed live 2026-08-22 — it
was never sourced from PLAN.md's prose, so it was never affected by that prose's stale `eastus`
figures, and commit `6390cac` (2026-08-28) corrected only the displayed text in PLAN.md to match
numbers the script had already been using for three days. What genuinely is new here, and was never
previously stated anywhere in this project's record: the active-path failure itself. Nothing before
this session computed or wrote down that the active-cost path drives R-08's own formula to 0 runs/
month and its own hard stop — every prior mention of R-08 stated the idle-path pass alone, without
the conditional.**

### R-09 — Number irreplaceability
**Asked**: is the purchased number still owned, and does the teardown path avoid releasing it?
**Status: ANSWERED.** `+17059100383` confirmed still owned via a manual `/phoneNumbers` GET after
the teardown script's own false-negative "TEARDOWN INCOMPLETE" banner (a timeout on the environment
delete, not an actual failure — see Part 2). The teardown script itself was verified in advance to
never call a number-release/delete endpoint.
**Provenance: verified live against the ACS phone-numbers API**, manually, since the script's own
automated check didn't complete cleanly that run.
Closed 2026-08-24. **Changed since 08-24? No** — this is also now a standing `CLAUDE.md` stop
condition going forward, not just a one-time Phase 0 finding.

---

## Part 2 — what Phase 0 left behind

For each item: current status, and whether it **blocks** Phase 1 (must be resolved before Phase 1
work can proceed), **informs** it (Phase 1 design must account for it but doesn't have to resolve it
first), or **neither**.

1. **`docs/echo-app/app.py:86` — `answer_call()` has no `try`/`except`, no fallback.** Any ACS
   rejection propagates unhandled → `500` to Event Grid → call dropped silently (caller hears
   ringing until timeout, no `reject_call`/busy signal). Recorded 2026-08-28
   (`PROJECT_STATE.md` open item 11), **not fixed**.
   **Informs Phase 1** — explicitly, Phase 1 builds its own call-handling logic directly on this
   handler. Whether fixing it is *in scope* for Phase 1 is Part 3(a)'s open question, not settled
   here.

2. **R-03's residual fork — why app-side logs can't settle it.** Structural, not a missing feature:
   ACS decodes DTMF tones before the app's WebSocket callback ever fires, so the app only ever sees
   what ACS already chose to forward. A `dtmf_tones=0` counter at WS close cannot distinguish "no
   tone sent" from "tone decoded and dropped upstream." Resolving it needs ACS-side call diagnostics
   for correlationId `2d5e7f5c-39ae-46ef-b3d8-feadf93ec651` (Call 1) — a data source that has never
   existed in either Log Analytics workspace and would require its own, never-yet-configured delivery
   path from ACS itself.
   **Currently written up as a Phase 1 entry criterion** (`PROJECT_STATE.md` open item 10) — i.e.
   currently BLOCKS. Whether it should stay a blocking entry criterion, given the CAE that would have
   carried this call is now deleted, is Part 3(b)'s open question.

3. **`04-teardown-and-r08.sh`'s recorded defects — three, not two, as best I can find in the
   record; flagging the mismatch rather than silently picking two:**
   - `az costmanagement query` doesn't exist in the installable extension — **fixed** (routed
     through `az rest` directly), verified working before the live run.
   - `ask()` called three times, never defined — **fixed** before the live run (guaranteed crash
     otherwise, caught in advance).
   - The final "TEARDOWN INCOMPLETE" banner is a **false negative** — a timeout waiting on the slow
     environment delete, not an actual failure (all three resources independently confirmed deleted
     afterward). **Not fixed** — flagged explicitly in the 08-24 closeout as real and unfixed in the
     script as committed, deferred because the script won't run again this phase.
   The first two are closed and no longer relevant (the script won't run again this phase). The
   third: **neither blocks nor informs Phase 1 directly**, unless Phase 1 provisions new compute and
   later needs to tear it down with this same script — worth a fix pass before that day, not before
   Phase 1 starts.

4. **The wizard "writes a file it doesn't exclusively own" pattern.** Three separate instances this
   session (Stage 11 regenerating `docs/echo-app/`'s equivalent from a frozen template; the
   `ECHO_DIR` misdirection that pointed a correct-looking guard at the wrong directory; Stage 10
   regenerating a committed ADR file with placeholder content) — same underlying principle each time:
   a wizard stage that writes a file a human has read, reviewed, or committed is a regression risk
   the moment that happens, regardless of whether the stage's own guard logic looks correct.
   **Status: RESOLVED.** All three instances fixed and guarded; a full audit of every remaining
   write site in all four wizard scripts confirmed zero unguarded heredocs remain.
   **Neither blocks nor informs Phase 1 directly** — carried forward here as a design principle
   worth remembering if Phase 1 writes its own provisioning scripts, not as an open defect.

5. **`launchd` LaunchAgent plist absence, unexplained.** The poller's plist
   (`~/Library/LaunchAgents/com.azbank.phase0.logsnapshot.plist`) is absent from disk; no script in
   this repo ever removes it (only unloads it); how or when it was actually removed is unknown.
   **The mystery itself neither blocks nor informs Phase 1** — it's an operational curiosity about
   a diagnostic tool, not part of the app. But the underlying need it was serving does inform Phase
   1: `PROJECT_STATE.md` open item 1's own closing line states plainly that "a production voice
   agent cannot run on Phase 1 with no durable logging; this needs a real fix, not a workaround,
   before then" — `--follow`-based capture is confirmed **not durable** (known upstream Azure CLI
   bug, dies after ~5–6min idle every time), so this reads as a real design gap Phase 1 has to close,
   independent of what happened to the old plist file.

6. **Active-column budget breach: $27.03 fixed+eval vs. the $25/mo ceiling.** Once the $6.00/mo eval
   ceiling is added to the *active*-rate Container Apps figure ($20.03/mo), fixed costs alone exceed
   the ceiling before a single demo-call minute is spent. What keeps the project inside budget today
   is R-04's own IDLE verdict, not headroom — the active column is a worst-case bound the project
   must stay aware of, not the live number.
   **Directly informs Phase 1** — this is Part 3(c)'s subject in full. Status here: not currently
   breached (R-04 holds IDLE), but conditionally blocking through an actual mechanism, not just
   arithmetic risk — `04-teardown-and-r08.sh`'s own R-08 Stage 3 already halts automatically
   (`⛔ R-08 GATE FAILED`, "STOP HERE") if a future run measures ACTIVE. If any Phase 1 work changes
   the app's measured operating mode from IDLE to ACTIVE, the budget breaks on fixed costs alone,
   before B4's own per-call brake would ever engage, and this script is what catches it.

---

## Part 3 — Phase 1 entry criteria: options for Marco to decide

**No decision is filled in below.** Where I have a view I've marked it as a view, not a chosen
option.

### (a) Scope — `app.py:86` fix, DTMF disambiguation, or both?

Both the Container App and its environment (CAE) were deleted in the 2026-08-24 teardown. Any option
below that needs to observe the fix running against real ACS traffic requires **re-provisioning
Container Apps compute** (billable — restarts R-04's measurement question from scratch, at minimum
the $5.72–$20.03/mo range depending on operating mode) and, for the Event Grid subscription to fire
at all, a live inbound call to the number.

| Option | What it needs | Billable re-provisioning? |
|---|---|---|
| **`app.py:86` fix only** | Code change (add `try`/`except` around `answer_call`, define a fallback response). Can plausibly be verified with a mocked/unit-level harness — force the ACS SDK call to raise, assert the handler catches it and returns something other than an unhandled `500` — **without** standing up live Azure infrastructure at all. | Not necessarily, if mocked coverage is accepted as sufficient. Verifying it against a *real* ACS rejection, rather than a mock, would need live infra + a call, same as the row below. |
| **DTMF disambiguation only** | Standing up ACS-side call diagnostics from scratch (never configured in this project; unclear yet what ACS resource-level logging category would even carry tone-decode detail, or whether one exists) + re-provisioning Container App/CAE + at least one new real inbound call to generate a fresh, diagnosable correlationId. | Yes — infra + a real call, no way around it. |
| **Both** | Superset of the above. | Yes. |

My view: the `app.py:86` fix is the cheaper, more self-contained piece — it's a defect with a known
fix shape and testable without new billable spend, whereas DTMF disambiguation's first step
(figuring out whether ACS even exposes the diagnostic data needed) is itself unresolved research,
not just an implementation task.

**Decision (2026-08-29, via the revised Phase 1 scope): `app.py:86` fix, alongside the new agent
turn loop — not DTMF disambiguation.** DTMF stays out of scope entirely for Phase 1
(`docs/PLAN.md`).

### (b) R-03 — drop it as an entry criterion, re-provision and reproduce, or something else?

| Option | Cost | Consequence |
|---|---|---|
| **Drop it as a Phase 1 entry criterion** | $0 | Phase 1 proceeds with R-03 permanently unresolved for Call 1 specifically. The two remaining candidates (tone not sent vs. tone decoded-and-dropped) stay open indefinitely unless revisited later. Calls 2 and 3 already confirm the mechanism works in the common case — this doesn't block a working DTMF feature, only closes the book on one anomalous call. |
| **Re-provision and reproduce** | Full Container App/CAE re-provisioning cost (same as 3(a) row above) + at least one new real call, placed specifically to generate fresh, diagnosable data — and only useful if ACS-side diagnostics are actually configured and working *before* that call happens, which is itself unproven capability, not a known-working path. | Real chance of spending real money and a real call attempt without actually resolving anything, if the ACS-diagnostics side turns out not to expose what's needed. |
| **Something else** (e.g.: check whether ACS retains any call-level diagnostic data independent of a diagnostic-settings configuration, retroactively, for a call that already happened) | Unknown — this hasn't been researched. Plausibly free (a read-only API check) if such a retention window exists; plausibly a dead end if it doesn't. | Worth a cheap `/research`-style check before committing to the "re-provision and reproduce" cost, in my view — but that's a view, not a decision. |

**Decision (2026-08-29, via the revised Phase 1 scope): dropped as an entry criterion.** Permanently
unresolved for Call 1 specifically; Calls 2/3 already confirm the mechanism works.

### (c) Budget — does R-04's IDLE verdict gate Phase 1 entry?

**This is not a soft caution — it's a documented stop condition that already exists in
`04-teardown-and-r08.sh` and fires automatically.** R-08's own arithmetic (`:294-309`, re-derived
above) is not a budget observation running alongside the project; it *is* part of the project's
tooling, and it already halts on the active path without anyone deciding anything: `left_for_calls
≤ 0` forces `R08_RUNS=0`, which trips the script's own `⛔ R-08 GATE FAILED` banner and its explicit
"STOP HERE. Do not proceed into Phase 1" instruction (`:326-329`). The $27.03-vs-$25 active-column
breach is not live today only because R-04 measured the app as IDLE, not because there's real
headroom in the active case — and the mechanism that would catch a switch to active isn't a manual
check someone has to remember to run, it's this script, if and when it runs again. Any Phase 1
candidate that changes the app's **measured operating mode** — not its feature set, its operating
mode — would remove the only thing currently keeping the project inside B4, and the next time this
script's Stage 3 runs against an ACTIVE verdict, it stops Phase 1 by itself.

What could plausibly change operating mode, based on what's scoped for Phase 1 so far:
- **The `app.py:86` fix alone**: no — it changes error-handling behavior on a rejected call, not
  the between-calls WebSocket/replica behavior R-04 measured. Doesn't touch decision 15 (WS closed
  between calls) or replica count/size.
- **DTMF disambiguation**: only if it required holding the media WebSocket open longer, adding a
  second concurrent connection, or otherwise deviating from decision 15's between-calls closure — not
  established as necessary yet, but not ruled out either, since ACS-side diagnostics configuration is
  still unresearched (see (b) above).
- **Re-provisioning itself**: the first ~72h after any new provisioning would look like R-04's own
  measurement tail (an active spike, settling to idle) — a temporary, expected active blip, not a
  sustained mode change, matching what R-04 already measured for test-call tails.

My view: nothing currently scoped for Phase 1 obviously changes operating mode, but "obviously"
isn't the same as verified — this hasn't been checked the way R-04 checked it the first time, and
DTMF disambiguation's actual implementation shape is still unknown per (a)/(b) above.

Options for whether this gates entry — framed against what actually happens, not just what's prudent:
| Option | Effect |
|---|---|
| **Gate entry explicitly on it** — require a stated commitment that Phase 1 work won't change operating mode, or a re-measurement plan if it might, decided *before* any re-provisioning happens | Adds a step before Phase 1 starts, but it's deciding something in advance that the script would otherwise decide for you, later, mid-phase. Costs nothing extra if the commitment holds. |
| **Don't gate entry explicitly — accept that `04-teardown-and-r08.sh`'s own STOP condition is the real gate** — proceed into Phase 1 work, and let a future re-run of this script's Stage 3 be the actual enforcement point if operating mode ever comes out ACTIVE | Faster start, but the "gate" isn't avoided, only deferred to a point already fixed in the script's own logic — Phase 1 work could get partway done (a fix built, re-provisioned, exercised) before an ACTIVE verdict on some later run halts further progress under this same $25 ceiling. Whether that's an acceptable order of operations, given real money and a real re-provisioning cycle would already be spent by then, is the actual tradeoff here. |

**Decision (2026-08-29, via the revised Phase 1 scope): no explicit pre-gate.**
`04-teardown-and-r08.sh`'s Stage 3 stop condition is the enforcement point; `docs/PLAN.md`'s revised
Phase 1 instead requires measuring operating mode after the first real conversation before further
spend.

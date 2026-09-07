# Phase 1 exit criteria & Phase 2 entry considerations

Written 2026-09-07. Sources: `docs/PLAN.md` (Phase 1 REVISED section, Phase 5's B4 definition,
Phase 2's own definition), `PROJECT_STATE.md` (open items 1–12, as they stood before this doc),
`docs/handoffs/2026-09-07-phase1-b4-guard-and-review-findings.md`. **This document does not itself
decide anything** — Part 3 is options for Marco, not decisions, matching
`docs/phase0/EXIT-AND-PHASE1-ENTRY.md`'s own stated discipline. No `APPROVED: Phase 2` has been
typed; Phase 2 has not begun.

---

## Part 1 — Phase 1 exit criteria, against `docs/PLAN.md`'s own definition

Phase 1 (REVISED 2026-08-28)'s written exit criteria are the 6-row exit test table in
`docs/PLAN.md` ("Phase 1 (REVISED 2026-08-28) — Agentic conversation prototype"). **All 6 rows
already PASS**, dated 2026-09-01, on a real call to `+17059100383`. That table is not repeated here.

The 5 in-scope items (agent turn loop, tool calling over mock accounts, transfer validation, the
`app.py:86` try/except fix, the operating-mode measurement) are all implemented and tested — confirmed
independently by this session's `/code-review` (Spec axis, fixed point `46a1b11`..`HEAD`): 0 missing,
0 scope creep.

**By `docs/PLAN.md`'s own written exit criteria, Phase 1 is done.** What's below is the open-items
triage that stood between "criteria met" and actually calling the gate closed.

### Open items triaged

| Item | Status | Blocks Phase 1 exit? |
|---|---|---|
| 1 — no durable ACS-side call logging | Genuinely open, unresolved | **No** — "observability tooling" is explicitly out of scope for Phase 1 (`docs/PLAN.md`'s own list); this is Phase 6's job. Carried forward as a real gap, not waved away: a production agent can't ship without it, but this prototype phase's own exit test doesn't depend on it. |
| 2 — `02-test-calls.sh` cheap-op-welded-to-billable-op design gap | Genuinely open, unresolved | No — a wizard-script ergonomics issue, not a Phase 1 deliverable. Carried forward. |
| 3 — R-03 Call-1 zero-DTMF anomaly | **Closed via item 10's 2026-08-28 decision** — explicitly dropped as a Phase 1 entry criterion; Call 1's evidence no longer exists to settle it. Not reopened by anything since. | No |
| **4 — PLAN.md Budget section stale (US East vs Canada Central)** | **STALE LINE, now corrected.** Commit `6390cac` (2026-08-28) already fixed this — *before* Phase 1 even started (`46a1b11`). `PROJECT_STATE.md` open item 4 never caught up to that commit. | No — already resolved, just undocumented until now. |
| 5 — Docker Hub vs ACR decision | Genuinely open, unresolved, despite being flagged "still due at Phase 1 kickoff." No ACR migration happened; the real `voice-agent` image is still on Docker Hub. | No — Phase 1's exit test doesn't depend on registry choice. Flagged honestly as a miss against its own stated deadline, not silently closed. |
| 6 — rate-limit interpretation unconfirmed | Genuinely open, unresolved (cheap, ~30s Foundry-portal check, never done) | No |
| 7 — `gpt-realtime-1.5` successor boot untested | Open by design — explicitly a Phase 2 deliverable (`T-B3-SUCCESSOR-BOOT`, needs `FakeRealtimeServer`, which Phase 2 builds) | No — not Phase 1's to test |
| 8 — stale `az` CLI `defaults.location=eastus` | Genuinely open, unresolved, fix identified but not applied pending sign-off | No |
| 9 — Log Analytics workspace auto-provision choice | Open, tied to item 1 | No, same reasoning as item 1 |
| **10 — R-03 superseded decision** | Closed, stable since 2026-08-28 | No |
| **11 — `app.py:86` try/except fix "not fixed"** | **STALE LINE, now corrected.** The fix landed in this project's Phase 1 work (4 passing tests in `tests/test_echo_app.py`); confirmed independently by this session's `/code-review` Spec-axis sub-agent. `PROJECT_STATE.md` never caught up. | No — already resolved, just undocumented until now. |
| 12 — intermittent interrupt-the-caller defect | Genuinely open, unresolved, non-reproducing on the second call | **No — `docs/PLAN.md`'s own exit table already says so explicitly**: "Open defect found on this call, not gating this table." Carried forward as a known defect, config-tuning fix once/if it reproduces again. |

**Net: zero open items actually block Phase 1's own written exit criteria.** Three items (4, 11, and
the earlier superseding of 3 via 10) were stale status lines describing already-resolved states, now
corrected in `PROJECT_STATE.md`. Items 1, 2, 5, 6, 8, 9 are real, unresolved gaps that simply aren't
what Phase 1 was scoped to fix — they're carried forward, not closed.

### This session's own addition: the B4 guard

Found during this session's `/code-review`: `bridge.py`'s call loop had no upper bound at all — not
flagged in Phase 1's own "out of scope" list, unlike every other named constraint. Corrected mid-review
(full B4 — cost store, daily cap, fail-closed-on-unreachable-store, `T-B4-FAILCLOSED` — turns out to be
explicit Phase 5 scope, `docs/PLAN.md:621-624`, not a Phase 1 gap). Marco chose a middle path: a bare
per-call turn counter (20) and wall-clock timeout (5 min) in `bridge.py`, committed `5113544`. This is
explicitly not full B4 — said in the code, the tests, and here, so it isn't mistaken for the real thing
in Phase 5.

---

## Part 2 — what Phase 1 leaves behind

- **No durable ACS-side call-diagnostics path exists.** App-side container logs deliver correctly
  (`docs/handoffs/2026-08-27-phase1-logpath-resolved.md`); ACS-side call diagnnostics were never
  configured and, per item 10's decision, won't be for the R-03 question specifically. Phase 6
  (Observability) is where this gets solved properly, with App Insights + OTel, not a Log Analytics
  diagnostic-setting patch bolted onto Phase 1's scope.
- **`voice-agent`'s container image is still on Docker Hub**, not ACR — a decision that was supposed
  to happen at Phase 1 kickoff and didn't. Not urgent (Phase 1's exit test doesn't touch it), but it's
  a real miss against its own stated deadline and should get an actual decision, not keep drifting.
- **The B4 guard added this session is a stopgap, not the real thing.** No daily cap, no cost store.
  Phase 5 still has to build the real system; this just stops one call from running forever in the
  meantime.
- **`docs/PLAN.md`'s Phase 1 section itself states Phases 2–6 as currently written are "optional
  follow-on work, not committed scope."** Nothing below commits to doing Phase 2 — it only lays out
  what Phase 2 would need if Marco chooses to continue.

---

## Part 3 — Phase 2 entry: options for Marco to decide

Phase 2 (`docs/PLAN.md`: "Realtime session + agent core + gate + test harness") is a substantially
larger undertaking than Phase 1 — `dispatch/gate.py` (B1, one of two diffs this project never
auto-accepts), the B3 startup guard reading the live Models API at boot, `FakeTransport` +
`FakeRealtimeServer`, L0/L1 test suites. Per `CLAUDE.md`'s model/context policy, phase kickoff
(design, exit-criteria authoring) is Opus's job, not Sonnet's — this document stops short of that,
deliberately.

### (a) Proceed to Phase 2 at all?

`docs/PLAN.md`'s own framing: Phase 1 as delivered is "the deliverable — a working, demonstrable
prototype." Phases 2–6 "redo this work more completely... but are not required for the project to be
finished and demonstrable." Options:
- **Call the project done at Phase 1.** A working prototype, honestly scoped, with its real gaps
  (logging, B4, auth) named rather than hidden. Nothing here blocks this choice.
- **Continue to Phase 2** for the production-grade version this project's `CLAUDE.md` describes
  ("production-grade prototype IVR"). Phase 1 alone has no auth gate, no B1/B2 enforcement, no real
  cost ceiling — fine for a demo, not for anything handling real account actions.

### (b) If continuing: who authors Phase 2's exit criteria?

Per model policy, this should be an Opus session, not this one. Options:
- **A fresh Opus session**, reading this doc + `docs/PLAN.md`'s Phase 2 section, writes Phase 2's
  written exit criteria (the stop condition this project requires before any phase begins) — then
  Marco approves before anything is built.
- **Marco authors the exit criteria directly** and this session (or a fresh one) just implements
  against them once approved.

### (c) Any items from Part 1's triage that should actually block Phase 2 entry, even though they
didn't block Phase 1's exit?

Worth a deliberate answer, not an assumption:
- Item 1 (no durable call logging) arguably matters *more* once Phase 2 adds a real gate whose
  failures need to be auditable — B1's "0 breaches / ≥120 adversarial cases" target is hard to trust
  without logs to check it against.
- Item 5 (Docker Hub vs ACR) gets harder to defer the more phases build on the current image.

Neither is resolved here — named so Marco can decide deliberately rather than re-discover them
mid-Phase-2.

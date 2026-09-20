# Phase 8 criteria 6 and 7 — closed with a stated limit (D15)

Marco decided on 2026-09-19 (D15, `docs/phase8/exit-criteria.md`) that Phase 8 closes with criteria 6
and 7 unmet, recorded as debt with exactly what is missing. This is that record. Nothing here was run;
no number in this file is a result.

## Criterion 6 — `evals/`, 20 scenarios, ≥95% over 20 runs

**State: not built.** There is no `evals/` directory, no scenario definitions, no judge, no runner.
Nothing was run, so there is no pass rate to report, and none is implied.

What exists that a build would use: the second, non-realtime `gpt-5.4-mini` deployment, provisioned and
B3-pinned, that D12 chose as the judge. What is missing:

| missing | why it blocks the run |
|---|---|
| Caller audio | `docs/PLAN.md` designs L3 as TTS-synthesised caller audio driven through `FakeTransport` into the real realtime model. No TTS resource is provisioned. `docs/PLAN.md` says Speech F0 (0.5M chars/month free) covers it, but that is a **new resource and needs `APPROVED: <phase name>`** first. |
| The 20 scenarios | Not written. |
| The judge and its rubric | Not written. |
| A runner enforcing the $6/month eval ceiling | Not written. `docs/PLAN.md` requires it to refuse a run once month-to-date spend reaches the ceiling. |

D16's meaning stands: 20 scenario runs, once each, not 20 full-suite runs. `docs/PLAN.md` estimates a
weekly run at about $1.56-$3.11 of `gpt-realtime-mini` tokens, an estimate, not a measurement.

**What this leaves unproved.** Whether the agent *behaves* the same way across repeated calls (the
wording, the tool choice, the refusal), as opposed to whether the gate holds. The README's defect table
is the evidence that this is where real defects live: of its seven, six were found on live calls and one
in `/code-review`, none by the fakes-based suite.

## Criterion 7 — `redteam/` live run

**State: the corpus exists, the live runner does not.** `redteam/` holds 18 ideas, accepted as final
(D5). Only the deterministic L1 runner (`tests/redteam_harness.py`) exists; it expands the 18 ideas into
593 concrete cases (542 of which reach an attempt), run in every `make test`, **0 breaches**.

What that proves, and what it does not:

- **Proved, blocking, free:** an attempt that reaches the gate is refused. B1 is a pure function of the
  tool name and the auth state, so this is the security property.
- **Not run:** whether a live model can be talked into *making* the attempt. That question is
  probabilistic. `docs/PLAN.md` assigns it to L4, a sampled, $-capped, non-blocking live run, and that
  runner was never built.

The same blocker as criterion 6 applies wherever the live run needs caller audio (a TTS resource and a
new `APPROVED:`); the L4 runner also has to share criterion 6's budget ceiling.

## To close both later

1. Marco types `APPROVED: <phase name>` for a Speech (TTS) resource. Read its price from the Retail
   Prices API first; do not assume F0 applies.
2. Build the fixture pipeline (`make fixtures`, `docs/PLAN.md`), the 20 scenarios, the judge and the
   budget-enforcing runner.
3. Run L3 once per scenario (D16), report the pass rate with its N, and run the L4 sample.
4. Then revise criteria 6 and 7 from "stated limit" to a result.

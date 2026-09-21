# RESULTS.md — Azure-Banking-Voice-Agentic-AI

Measured outcomes only, as of 2026-09-21 (Phase 8, `main`; live timestamps are UTC). Anything not measured says so.
**Ceiling: 120 lines / ~9 KB (D6).** Move detail into the phase docs, not here — FNOL's own `RESULTS.md` grew to
941 KB, the pattern this ceiling exists to prevent. Design and rationale: `README.md`; scope and budget:
`docs/PLAN.md`; the record of each phase: `docs/phaseN/`.

## The named constraints

| | constraint | target | measured | source |
|---|---|---|---|---|
| **B1** | no banking operation before authentication | 0 breaches, ≥120 cases | **0 breaches, 593 cases** (18 attack ideas, 542 reach an attempt), run in every `make test`. Held across every live call in Phase 5. | `tests/test_redteam.py`, `docs/phase5/exit-check.md` |
| **B2** | no PIN or caller phone number in any transcript, log, record or telemetry channel | 0 occurrences | **0** in the CI artifact scan. Phase 8's live calls: the stored blobs were read back, no PIN, phone number or digit run. **Four calls** (two on `p8a`, one on `p8b`, one on `p8c`). | `tests/test_zz_b2_leak_scan.py`, `docs/phase8/build-notes.md` |
| **B3** | model pinning, by (deployment, version) | 0 violations | **0.** Realtime pin: fatal boot guard reading the live deployment. Text pin (`gpt-5.4-mini`, added in Phase 8): non-fatal guard before each summary, plus the CI static check. The text pin's Bicep is written but **never deployed**, so it enforces nothing yet. | `CLAUDE.md`, ADR-006 |
| **B4** | cost ceiling, fails closed | 0 overruns, 0 fail-open | **0 observed.** The one known undercount (a cancelled ledger write) is closed in code and tested; a cancelled call cannot be staged, so it is **not exercised live**. | `tests/`, `docs/PLAN.md` |
| **B5** | turn latency, p95 | frozen after Phase 5 | **1025 ms, N=13** authenticated real-call turns with a tool call. Small N, real-call pool only. Phase 2's earlier 932 ms / N=106 is superseded, not merged. Phase 8 measured **no** latency. | `docs/phase5/exit-check.md` |
| **R-09** | the phone number is never released | 0 release calls | **0.** Enforced by a blocking check in `make lint`. | `scripts/check_no_phone_number_release.py` |

## Phase 8 — post-call analytics, evals, docs

| # | criterion | result |
|---|---|---|
| 1 | redacted transcript to Blob, no raw write first | Met. Unit-proved; live on **four** calls. No blob for a closed-line call or one with no agent turns (nothing to store); one agent turn over 1,000 characters fails closed (a row, no transcript). |
| 2 | summary/intent/outcome row for every completed call | Met. Live on **four** calls. The row is now written first (`pending`) and overwritten when the steps finish, so a kill mid-pipeline leaves the pending row (tested; the pending state itself was never observed live, it is overwritten within seconds). |
| 3 | five-value outcome enum | Met (D17). |
| 4 | pipeline cannot affect B4 or B5 | Met by construction (background task, never awaited). The test proves the same frames and turn cap; it **measures no latency**. The gate review also moved the Table, Blob, Language and text-model clients onto one async credential, so a token refresh no longer blocks the event loop (**live on `p8c`**: the ledger read and write, the Blob write and both service tokens worked); a second review moved the realtime connection onto it too (tested, not yet live). |
| 5 | B3 covers the second deployment | Met. The static check now also pins each pin's name to the files that may carry it. Bicep for the text deployment is written, **never deployed**. |
| 6 | `evals/`, 20 scenarios, ≥95% | **Not built. No pass rate exists.** Closed with a stated limit (D15). |
| 7 | `redteam/` live run | **Not run.** The 18-idea corpus exists and its deterministic runner passes (B1 row). Closed with a stated limit (D15). |
| 8 | ADR-006 and ADR-007 | Written. |
| 9 | this file, the diagram, the README badge | Done: `docs/architecture.md`. |
| 10 | `COSTS.md` prices both new resources | Done, R-08 recomputed: `COSTS.md`, "Phase 8 — every input priced". |

Criteria 6 and 7 in full: `docs/phase8/eval-redteam-limits.md`. What is missing is caller audio (no TTS
resource; a new one needs `APPROVED:`), the scenarios, a judge and a budget-enforcing runner.

## What was checked, and how

- `python -m unittest discover -s tests`: **743 tests, 3 skipped by design**, run against fakes
  (`FakeTransport`, `FakeRealtimeServer`, `FakeCallRecordStore`). `make lint`: ruff, mypy, the B3/D5/D2 checks
  and `bicep build` on every module, clean.
- **Live, Phase 8, four real calls**, each a Table row (`caller_hangup`, transcript `stored`, summary `done`) and a
  redacted blob, read back through Entra data roles. Two on image `p8a` (2026-09-20, 2026-09-21). One on **`p8b`**
  (2026-09-21): row and blob as above, and the day's ledger (2.071 min) matches the two calls that day (56.9 s +
  67.4 s), written before the row. One on **`p8c`** (2026-09-21 10:34 UTC, revision `--0000003`, the gate-review code): row, blob and ledger as above; the ledger rose 2.071 to 3.169 min, 1.098 min = 65.9 s against the call's 65,856 ms. Its blob: 6 agent turns, no digit run of four, no
  phone-shaped or spoken-digit run; the only digits are `$` amounts (the known limit). **Not exercised live:** the
  failed-connect row and the unsafe-id replacement (no real call produces either); tests cover them.
- Three `/code-review` rounds found real defects, fixed: a B4 ordering bug that would have let a failing
  capture skip the day's charge, and a correlation id (a carrier-controlled header) that could lose a whole row
  when it contained a character a Table key refuses. Two findings stayed open (see the limits below).

## Cost

- **Fixed: $14.60/mo** (two always-on Container Apps and the number). Unchanged by Phase 8.
- **Phase 8 variable, worst case at 67 calls/month: $1.89/mo**, so about **$16.49/mo against the $25
  ceiling**. This is arithmetic from list prices, **not a billed figure**: no Phase 8 spend has been read back
  from Cost Management. R-08's runs/month falls from 67 to 57 (45 to 38 on the comparable basis), gate 5.
- Unmeasured: how Language counts a conversation record, whether the Global meter applies to a `canadacentral`
  account, and `gpt-5.4-mini`'s real token use per summary.

## Known limits and open defects

- **Live on `p8c`:** one async credential for the Table, Blob, Language and text-model clients. **Tested, not
  exercised live:** the realtime connection's token from that same credential, the shielded
  daily-ledger write (a cancelled call cannot be staged), the phone scrub's new pattern (the agent never spoke a
  phone number), and the pending-first row (overwritten within seconds; the row's `occurred_at` is now taken at the
  start of the pipeline, which the `p8c` row shows, but the pending state itself was not seen).
- **Azure AI Language keeps its job results, including the entity text it matched, for 24 hours** (ADR-007);
  the voice agent's role cannot delete a job.
- **Bicep for the text deployment and the Language account is written, never deployed**, and not wired into
  `azbank-deploy`. `language.bicep` would create a duplicate role assignment over the live account.
- **Not changed, on purpose:** the `capture=None` guards, `StrEnum` for statuses, one shared endpoint check
  and the per-call `PostcallServices` (refactors on the live path, no behaviour gained).
- **`$` amounts pass through the stored transcript unredacted.** B2 covers the PIN and the phone number only.
- A call with no correlation-id header keeps `None`, so its escalation row's key ends `_None`.
- Barge-in: the agent talks over the caller. Seen on a live call, not a criterion, nothing changed.
- Carried from Phase 5: one live call went silent after a correct refusal, root cause never found (B1 held).
- Carried from earlier phases: `AOAI_KEY` is still on the container, unused; `DOCKERHUB_PASSWORD` is not yet a
  GitHub secret; the root `CONTEXT-MAP.md` is unwritten. Current list: `PROJECT_STATE.md`, "Open items".

# Phase 8 — exit check, against `docs/phase8/exit-criteria.md`

**Status, 2026-09-21: criteria 1-5 and 8-10 met, 6-7 closed with a stated limit (D15). The gate's
`/code-review` has been run and its findings are addressed below. Not yet signed off.**
Nothing in this table is a projection: where a criterion rests on a live call, it says how many. One more real
call (`p8c`, the gate-review code) confirmed the async credential live; the shield, the new phone pattern and the
pending-first row have no live trigger and rest on tests.

| | |
|---|---|
| `make lint` | clean: ruff, mypy, the B3/D5/D2 checks, `bicep build` on all 8 modules |
| `make test` | 729 voice-agent (3 skipped by design) + 90 mock-core-banking, all pass; B1 corpus 593 cases, 0 breaches |
| `/code-review` | 3 rounds during the build (`build-notes.md`), then **the gate review, 2026-09-21, fixed point `2dc4961`** (Standards and Spec axes, run separately). Disposition of every finding: below. |
| Live | four real calls: two on image `p8a`, one on `p8b`, one on **`p8c`** (revision `ca-azbank-echo-p0--0000003`, 2026-09-21 10:34 UTC, the gate-review code). Ledger 2.071 to 3.169 min = 1.098 min = 65.9 s, matching the call's 65,856 ms; one row; blob clean (6 turns, no digit run of four, no phone-shaped or spoken-digit run; digits only in `$` amounts). |
| Model pin review (`CLAUDE.md`, at every gate) | read live from the Models API and ARM, 2026-09-20: `gpt-realtime-mini` `2025-10-06` retires **2027-04-06** (6.5 months), `NoAutoUpgrade`; `gpt-5.4-mini` `2026-03-17` retires **2027-09-21** (12 months), `NoAutoUpgrade`. Neither is under 2 months; no stop-and-ask. Successor `gpt-realtime-1.5` is GA, retires 2027-08-24. |

## Criterion by criterion

| # | criterion | evidence |
|---|---|---|
| 1 | Redacted transcript reaches Blob, no raw write first | ✅ Unit tests prove the blob writer only receives redacted text and that a failed redaction writes nothing (ADR-007). **Live on four calls**: each blob read back, no PIN, phone number or digit run. **Limits:** no blob for a closed-line call or one with no agent turns (nothing to store, so `transcript_status=none`); one agent turn over 1,000 characters fails closed and keeps its row. |
| 2 | A summary/intent/outcome row for every completed call | ✅ Live on four calls, each `caller_hangup`, transcript `stored`, summary `done`. A call whose realtime connection cannot be opened also gets a row (tested on the main and closed paths, not live). The row is now written **first** with `pending` fields and overwritten when the steps finish, so a kill mid-pipeline leaves the pending row (tested; the pending state itself was not observed live). |
| 3 | Outcome is exactly the five-value enum | ✅ `postcall/outcome.py`; a drift test on `session.py`; and (gate review) each ending the fakes can reproduce is now driven through `run_call` / `run_closed_call` and its outcome read off the capture, mutation-checked. |
| 4 | The pipeline cannot affect B4 or B5 | ✅ **with a limit.** Background task, never awaited; tests prove the same frames, events and turn cap, and that a capture that raises cannot skip the ledger charge. **The tests measure no latency**; B5's frozen figure (p95 1025 ms, N=13) is not re-measured. Gate review: the Table and Blob clients had a sync credential whose token refresh ran on the event loop; one async credential now serves all (**live on `p8c`**: ledger read and write, Blob write and the Language and text-model tokens all worked). |
| 5 | B3 covers the second deployment | ✅ `CLAUDE.md` B3 row; the static check scans both deployment classes and (gate review) pins each name to the files that may carry it; `boot.assert_text_model_safety` is the non-fatal runtime guard (ADR-006). Bicep now declares the text deployment, **never deployed**. |
| 6 | `evals/`: 20 scenarios, ≥95% over 20 runs | ⚠️ **Not built, no result. Closed with a stated limit (D15)**: `eval-redteam-limits.md`. |
| 7 | `redteam/` at its L4 cadence | ⚠️ **Live run not done. Closed with a stated limit (D15)**, same document. The deterministic corpus (593 cases, 0 breaches) runs in `make test`. |
| 8 | ADR-006 and ADR-007 | ✅ Both written, each with a 2026-09-21 build note. |
| 9 | `RESULTS.md`, an architecture diagram, a current README badge | ✅ `RESULTS.md` (78 lines, ceiling 120); `docs/architecture.md` (Mermaid, parsed clean by the mermaid parser, not viewed rendered on GitHub); README badge "Phase 8 of 8 (exit gate pending)". |
| 10 | `COSTS.md` prices Language and the second model; R-08 recomputed | ✅ `COSTS.md`, "Phase 8 — every input priced": list-price arithmetic, **not billed figures**; the Language billing unit and the Global meter for `canadacentral` stay unverified. The second row write per call adds about 67 Table transactions a month, under the cent the Table line already rounds to. |

## The gate review's findings, and what became of each

Fixed and tested. The three on B2, B4 and billable IaC were shown to Marco and approved before they were committed (`f30419b`, `bb3faf7`):

| finding | disposition |
|---|---|
| `scrub_numbers` left the area code, or six digits of a dotted number | **Fixed.** A phone-shaped pattern runs first; `$12.50` and `4.25 percent` survive. **B2, approved.** |
| A cancelled ledger write lost that call's minutes (B4) | **Fixed.** The write is its own shielded task; shutdown waits for it. **B4 / `session.py`, approved.** |
| Row written last; a kill loses it | **Fixed.** Row first with `pending`, overwritten at the end. |
| Sync credential on the event loop (B5 exposure, and the ledger client since Phase 5) | **Fixed.** One async credential, live on `p8c`. |
| Static check accepted either pin anywhere | **Fixed.** File-scoped; two new tests fail it on cross-wiring. |
| Criterion 3's tests were tautological | **Fixed.** Seven end-to-end endings, mutation-checked, 0 flakes in 40 runs. |
| No Bicep for Language or the text deployment | **Written, never deployed, not wired into `azbank-deploy`.** A read-only `what-if` found one deploy blocker: a duplicate Language role assignment. **Billable IaC, approved.** |
| Malformed endpoint refuses boot | **Kept, reason recorded** in `boot.py`: single-revision mode means a revision that won't boot never takes traffic. A test pins it. |
| Closed-line calls store no blob | **Documented** (criterion 1). |
| Language keeps results 24 hours; ADR-007 assumed a PIN read-back D14 removed | **Documented** in ADR-007. |
| Doc drift (image, glossary, "one call", outcome wording, dates, module count) | **Fixed.** Live times are UTC. |
| Scope beyond the spec (`scrub_numbers`, correlation-id replacement, the `INTENTS` list, the `client.py` change, the README rewrite) | **Accepted and recorded** in `build-notes.md`. |
| Smells: `capture=None` guards, `StrEnum`, one shared endpoint check, per-call `PostcallServices`, the model literal in Bicep | **Not changed.** Refactors on the live path with no behaviour gained; say so if you want any of them. |

**Seen live, not a criterion:** the agent talks over the caller (barge-in). Other open items:
`PROJECT_STATE.md`.

## Owed before this phase is closed

1. *(done 2026-09-21: the B2, B4 and billable-IaC diffs were approved and committed.)*
   **`/code-review` of the fixes** (`c494e98^..HEAD`), which Marco invokes; none of the fixes has been reviewed yet.
2. *(done 2026-09-21: `p8c` built, deployed and called; see the Live row.)*
3. **Closure sign-off**, then `/handoff` (copied to `docs/handoffs/` and committed), then `/clear`.

**Closure sign-off**: not yet given.

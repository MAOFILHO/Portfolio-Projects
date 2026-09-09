# Phase 3 archive — mock-core-banking

Everything past-tense about Phase 3: the scope as it was opened, the decisions taken along the way,
the deviations from the tickets as written, and the three review rounds with what each one found.

This file exists because `PROJECT_STATE.md` is a **fixed-size current-state document** (decision 18,
`CLAUDE.md`) and this material is narrative. Moved here 2026-09-09 with the state file at 18.6 KB
against its 20 KB ceiling. Nothing here is a live item: open questions, active deviations and next
actions stay in `PROJECT_STATE.md`. The written exit criteria are next door in
`docs/phase3/exit-criteria.md`; the full design reasoning is in GitHub issue #25.

---

## Scope, as opened 2026-09-08

`mock-core-banking` becomes its own deployable (FastAPI + SQLite, own package/Dockerfile/tests),
reached through one new seam -- a `CoreBankingClient` protocol with a real async httpx client and a
deterministic fake, mirroring how `transport/` and `realtime/` already pair a real system with its
fake. `accounts.py` is deleted. `dispatch_tool_call` goes async so a network call never stalls the
audio loop. **`dispatch/gate.py` does not change** -- `PERMISSIONS` stays `{}`; this phase adds a
path *behind* the control, Phase 4 adds permissions.

Spec: GitHub issue **#25**. Tickets: **#26-32** (sub-issues of #25).

## What was built, per ticket (2026-09-08)

- **#26** `mock-core-banking/` — FastAPI + SQLite, own package/pyproject/Dockerfile/tests, integer
  cents, seeded-if-empty, REST-resource routes with the 404/200-declined/422 status mapping.
- **#27** `core_banking/client.py` — the protocol, the async httpx client, 1.0s timeout, one retry
  on reads only, and a per-process breaker (5 failures → 30s → half-open probe) for the whole
  service. Failure paths tested via `httpx.MockTransport`; the breaker's clock is injected.
- **#28** the seam — `FakeCoreBankingClient`, `accounts.py` **deleted**, the account enum dropped
  from the tool schema, `dispatch_tool_call` async and awaited by the relay.
- **#29** boot guard refuses to start without `CORE_BANKING_URL`.
- **#30** one real-network test (spawns the service, real socket) + `make test`/`install` across
  both suites.
- **#31** the phase's docs. **#32** `infra/modules/mock-core-banking.bicep`, written unapplied.

## Three design decisions worth not re-deriving

A **declined** transfer is 200 + structured outcome (not 4xx -- it is a normal outcome of a working
system); **`transfer` is never retried** (not idempotent, a retried timeout is a double-spend); one
circuit breaker per process for the **whole** service (per-endpoint would let a healthy read path
mask a service failing its writes). Full reasoning in #25.

## Two deviations from the tickets as written, both deliberate

1. `tests/test_gate.py` could not pass *literally* unchanged (#28's criterion 7) — the dispatcher is
   a coroutine now, so its in-path class had to become async. **What it asserts is unchanged, and
   `dispatch/gate.py` itself is byte-identical**, which is the half that was actually load-bearing.
   The policy class (`GateIsAPureDenyAllFunction`) is untouched.
2. The client is built once in `app.lifespan()` and read from a module-level accessor, **not
   constructed per call** — a first pass did the latter, which would have given every call its own
   circuit breaker that could never trip. Q13 settled per-process; this is that decision, enforced.

A third deviation, `tools._account_name`'s refusal of an account name containing `/`, is **not**
archived here: it is awaiting Marco's ruling and stays in `PROJECT_STATE.md` until he settles it.

---

## Round 1 — `/code-review`, both axes, 2026-09-08

Five findings, all fixed, each with a test verified red against the pre-fix code. Commits `0dec63e`
and `d4d7e24`, then `8163e83`, `89c81f9`, `4e77828` for what the fixes themselves turned up.

1. **The caller was being read the service's internal URL.** An unknown account produced "There's no
   `http://ca-azbank-core-banking.internal:8001/accounts/bitcoin` account on this profile." Both
   axes found it independently. The test had asserted `assertIn("bitcoin", error)` — and the URL
   contains "bitcoin", so the substring check could not tell the right answer from the wrong one.
   Fixed at the source: the service now names the unknown account in its 404 body (it is the only
   thing that knows *which* of a transfer's two accounts was bad); assertions are now exact
   sentences.
2. **A half-open probe on a read issued two requests, not one** — `READ_RETRIES` applied to the
   probe, against #27's own acceptance criterion, doubling load on a backend already believed sick.
3. **A malformed request spoke the service's internal wording** ("core banking rejected the request
   with 422"). Now a composed sentence; the raw text is logged, not spoken.
4. **The tool schema still named the accounts in prose** ("e.g. chequing or savings") after the enum
   was dropped — the same stale answer back in front of the model in another form.
5. The fake raised `ValueError` where the real client raises `CoreBankingRequestError` for the same
   scenario — a divergence that made tests passing against the fake say something untrue about
   production (#25's own user story 10). The fake now fails the way the service does.

Three further defects surfaced while fixing those, each with its own commit: a self-transfer spoke a
balance nothing held (`8163e83`), balances were computed rather than read back from storage
(`89c81f9`), and one shared SQLite connection let concurrent transfers double-spend — 29% of rounds
at four threads, 82 corruption errors per 200 rounds, both zero after serialising (`4e77828`).

## Round 2 — `/diagnosing-bugs`, 2026-09-09

The feedback loop was a probe driving the real dispatcher against a real spawned service with the
arguments a *model* can emit, not the ones the schema asks for. Eleven problems, zero after.

1. **A string or `null` amount ended the call.** `_cents` raised `TypeError`, outside
   `dispatch_tool_call`'s except clause, and `run_call` re-raises whatever escapes.
2. **`"amount": true` moved $1.00 and the agent said "Done"** — `True * 100` is an ordinary 100
   cents, so `db.py`'s bool guard at the system of record could never fire on it.
3. **Internal text spoken to the caller**: the JSON parser's message for an unparseable arguments
   payload or a non-JSON response body, and `'balance_cents'` for a response missing it.
4. **An account name went into a URL path raw** — `"../health"` reached `/health`, and `"a#b"` asked
   about account `a` while the caller was told about *that* one by name.
5. **The spoken transfer amount was the one asked for, not the one that moved** — they differ at the
   half cent in both directions ($2.675 asked for moves $2.68, "%.2f" of the request says $2.67).
6. **Fake/real divergence on every one of the above** — issue #25's user story 10 again.

Fixes: the amount rule at `client._cents` (shared by both clients, so `EXPECTED_ERRORS` covers it
live), the account-name rule in `tools._account_name`, percent-encoding and a 3xx branch in the
client, and the amount that moved reported separately from the amount requested.

## Round 3 — `/code-review`, both axes, 2026-09-09

Run over Round 2's result. Ten findings: six real defects, three judgement calls already settled by
earlier decisions (the duplicate positivity rule in `db.py`, the module-level client accessor, the
string-discriminated outcome types), and one deviation kept and recorded.

1. **The breaker could not see two of its four failure causes.** `record_success()` ran before the
   response was interpreted, so a service answering redirects or HTML was called unavailable on
   every call with the circuit closed forever: 20 of 20 operations reached it, against 10 of 20 for
   a 5xx. `_send` now builds the result before the breaker hears anything, and an unreadable answer
   has exactly the standing of a 5xx — retried on a read, one failed operation either way.
2. **A cancelled half-open probe wedged the client shut permanently** — nothing cleared
   `_probe_in_flight`, and the client is process-wide, so every later call answered "circuit is
   probing" for the life of the process. A hang-up mid-probe was enough. A `finally` now guarantees
   a probe always reports back.
3. **A timed-out transfer told the caller the bank could not be reached**, which asserts nothing
   happened — the retry invitation the no-retry rule exists to prevent. Separate sentence now
   (`TRANSFER_UNCONFIRMED`), said even when the request never left the process, because of the two
   possible wrong answers that is the one that costs a moment rather than the money.
4. **The amount moved was computed client-side.** The service reports `moved_cents` now: exit
   criterion 3's "never computed from the amount" covers every figure in the spoken sentence, not
   only the balances.
5. **The `422` body carried pydantic's English** ("Input should be greater than 0") — against #26's
   criterion 8, and the prose-freedom test covered four responses, none of them a 422. Structured
   body now, field paths kept because they are tokens and a log needs them.
6. **Two modules asserted opposite rules about the same value** — the dispatcher said arguments are
   not logged because they carry account identifiers, while the client logs a request path that
   contains the account name. The client's behaviour is right and stays; the claim now says what is
   true, and names B2 as the PIN and only the PIN.
7. **`CONTEXT.md`'s Malformed and Unavailable entries had drifted** from what the code does. Both
   rewritten: malformed now covers refusals that never reach the service, unavailable now covers an
   answer that is not a result, and the transfer's unknown-outcome case.
8. **#26's "runs without the voice agent installed" is now proven** rather than merely true, by
   `mock-core-banking/tests/test_shared_nothing.py` — a static check over the deployable's sources,
   its manifest, and its Dockerfile. It had been a known-partial since the phase was built.

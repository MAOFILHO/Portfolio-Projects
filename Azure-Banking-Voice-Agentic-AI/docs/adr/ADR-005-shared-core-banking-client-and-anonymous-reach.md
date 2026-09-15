# ADR-005 — One core-banking client carries verification too; `escalate_to_human` is reachable anonymous

Status: **Accepted** — decisions made at Phase 3 kickoff (issue #35) and Phase 5 (issue #48), recorded
here together on close-out, 2026-09-15.
Date: 2026-09-15

## Context

Two design decisions already live in the code and in `docs/PLAN.md`, but neither had its own ADR.
Both bear on B1 (Auth Gate Integrity) and are easy to mistake for drift if read from the code alone
without the reasoning, so this records both together rather than as two thin documents.

**Where PIN verification lives (issue #35).** `core_banking/client.py` talks to mock-core-banking for
both banking operations (balance, transfer, list) and PIN verification. The alternative considered
was a second, dedicated client just for `verify_pin` — a natural instinct, since authentication feels
like a different concern from a balance lookup. That was rejected: a second client means a second
timeout, a second retry policy, and a second breaker, and any of those three could drift out of
agreement with the first over time. If the two paths disagree — one client treats a timeout as
"unavailable" and the other treats it as "unauthenticated," say — a caller could be waved through on
a technicality the other path would have caught. Sharing the client means an unreachable service
fails PIN verification closed for the same reason, using the same code, that it fails a balance
lookup closed.

**`escalate_to_human` reachable while anonymous (issue #48, Phase 5).** Through Phase 4, "no tool at
all is reachable while a call is anonymous" was literally true. Phase 5 added one exception on
purpose: every row of the tool-access table, including the anonymous row, grants
`escalate_to_human`. A caller who cannot or will not enter a PIN can still ask for a person before
any banking operation is possible. This is not a B1 weakening — escalation reaches a human, never the
core-banking client, so it cannot expose an account or move money. B1's target (0 breaches / ≥120
adversarial cases) did not move; what moved is the accurate description of the anonymous row, from
"nothing" to "the PIN check and asking for a person."

## Decision

1. **One `CoreBankingClient`, used by both `verify_pin` and every banking tool.** It is not split by
   caller, by risk, or by future feature. `TIMEOUT_SECONDS = 1.0`, `READ_RETRIES = 1` (reads only,
   never `transfer`), and the one per-process breaker apply identically whether the request came from
   a PIN check or a balance lookup.
2. **`verify_pin`'s outcomes are a narrower set than the money paths' outcomes** — accepted, rejected
   credential, or unavailable — because authentication has no analogue to a declined-but-valid
   transfer. This narrowing happens in `verify_pin` itself, not by a second client with different
   wiring.
3. **The anonymous row's reachable set is exactly two operations: PIN verification and
   `escalate_to_human`.** Both are enforced by `dispatch/gate.py` and asserted by a test that checks
   the set is exactly those two, not "at most those two" — a future tool granted to the anonymous row
   by accident fails that test immediately.

## Consequences

- **A future PIN-verification change (rate limiting, a different credential type) is a change to this
  one client**, not a new client alongside it — keeping the resilience properties (timeout, retry,
  breaker) automatically shared rather than something a reviewer must re-check stayed in sync.
- **`CLAUDE.md`'s B1 row and `docs/PLAN.md` decision 7 both describe the anonymous row as "PIN check
  plus asking for a person."** Any wording elsewhere in the repo that still says "no tool is reachable
  while anonymous" is stale and should be corrected on sight (the `/code-review` pass on 2026-09-15
  found and fixed one instance in `CLAUDE.md` itself).
- **A ticket proposing a second core-banking client, or a third anonymous-row grant, is proposing a
  change to this decision, not an extension of it** — it needs its own sign-off the way any B1-adjacent
  change does, not a quiet addition.

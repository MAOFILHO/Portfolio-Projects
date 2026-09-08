# Phase 3 — mock-core-banking: exit criteria

**Written at phase kickoff, 2026-09-08.** `CLAUDE.md`'s first stop condition makes the *next*
phase's start conditional on these existing and being met, so they are written before the work
starts, not reconstructed after it.

Spec: GitHub issue **#25**. Tickets: **#26–#32** (sub-issues of #25).

**Entry conditions, both satisfied:** Phase 2's exit criteria are written and met (`docs/PLAN.md`'s
Phase 2 Exit line), and Marco signed off 2026-09-08
(`docs/handoffs/2026-09-08-phase2-signoff-phase3-entry.md`).

**No `APPROVED: Phase 3` is required for this scope** — this phase creates no billable Azure
resource. Provisioning mock-core-banking's Container App is deliberately outside it, and carries its
own precondition (below).

---

## The criteria

1. **Every banking tool call reaches mock-core-banking over a real HTTP hop.** `accounts.py` is
   **deleted**, not deprecated — no in-process account state remains anywhere in the voice agent.

2. **mock-core-banking exists as its own deployable**: own package, `pyproject.toml`, `Dockerfile`,
   and test suite; file-backed SQLite seeded on startup when empty; balances stored as integer
   cents. Its suite runs without the voice agent installed.

3. **The three outcomes are separately tested and never conflated.**
   - **Unknown account** raises and is never resolved to a default, a zero, or another account's
     balance — `T-UNKNOWN-ACCT`, the behaviour `CLAUDE.md`'s hard exclusions name by example.
   - **Declined** returns a structured 200 business outcome carrying the real available amount, and
     mutates nothing.
   - **Unavailable** surfaces as unreachable.

   A named test proves **no failure path ever returns a fabricated, cached, or defaulted balance** —
   asserted across timeout, connection refused, 5xx, and open circuit.

4. **Resilience is deterministically tested**: 1.0s per-attempt timeout; one retry on reads; **zero
   retries on `transfer`** (a timed-out transfer results in exactly one request reaching the
   service); the breaker opens after 5 consecutive failures and recovers through a single half-open
   probe.

5. **`dispatch_tool_call` is async and awaited by the relay** — no blocking I/O on the audio event
   loop.

6. **The gate is untouched.** `PERMISSIONS` is still `{}`, `is_allowed()` is unchanged, and
   `tests/test_gate.py` still proves every declared tool is refused for every `(agent, auth_state)`
   pair. The network path ships *behind* the control, never in front of it.

7. **`make test` is green across both suites with zero cloud dependency**; `make lint` is clean; the
   B3 static allowlist check still passes.

8. **The boot guard fails closed** when the core-banking address is unset.

9. **Bicep module and Dockerfile written and reviewed; nothing provisioned.** No billable resource
   was created, which is why no `APPROVED: Phase 3` was required.

10. **`docs/phase3/` records that B5 was deliberately not re-measured, and why** (below).

---

## Why criterion 6 is the load-bearing one

`docs/PLAN.md` states as a rule that no phase may exist in which the core-banking path is reachable
with nothing in front of it. **This is the phase that rule was written for.** Criterion 6 is what
turns it from an assertion into something this phase actually proves: the gate's own tests pass
unchanged, so the claim "Phase 3 added a path, not a permission" is mechanical rather than
narrated.

## Why B5 is not re-measured here

This phase puts a network hop inside every tool call, which is materially B5's business. It is
still not measured, for three independent reasons, any one of which would be sufficient:

- B5 is **provisional until Phase 5 freezes it** — that is the plan's own staging.
- The gate refuses every tool, so **no real call can exercise the path** at all in this phase.
- Nothing is provisioned, so **there is no deployed service to measure against**.

That this phase changes the latency picture is precisely *why* `docs/PLAN.md` freezes B5 in Phase 5
rather than Phase 2. The silence here is a decision, recorded so the next session does not mistake
it for an oversight. The one thing that *is* asserted is not a measurement: a test pins the client's
per-attempt timeout budget to 1.0s so the number cannot drift before the phase that does freeze B5.

## Deliberately parked, with reasons

Recorded so they are not re-litigated at the start of every phase:

- **The dead-air gap** before the agent's first words (2.5–11s; `session.py` sends no initial
  `response.create`, so nothing prompts a greeting until the caller talks first). Real and
  reproduced on every call. Parked because it belongs to the **greeting** path, not the tool path,
  and this phase's diff already touches the relay's tool handling — changing both at once means a
  review that cannot cleanly attribute a regression to either. Small fix, whenever it is wanted.

- **R-08's stale demo-runs/month figure** (still Phase 0's 79.2, which `docs/PLAN.md` itself says
  became wrong the moment a real measurement existed). Parked as a cost-model chore this phase does
  not change the inputs to — **and promoted to a precondition of provisioning**, because
  mock-core-banking's Container App would be this project's *second* Container App, and fixed cost
  is the line the entire $25/month ceiling turns on.

## Precondition on the provisioning that follows this phase

Before mock-core-banking is deployed: recompute R-08 against the reconfirmed IDLE verdict and a
**two**-Container-App fixed cost, and confirm the result still clears the gate. Then, and only then,
`APPROVED: Phase 3` for the provisioning step itself.

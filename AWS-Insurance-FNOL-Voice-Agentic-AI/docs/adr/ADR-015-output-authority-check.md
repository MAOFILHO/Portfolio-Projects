# ADR-015: An existing dialogue policy gets a second, deterministic enforcement point on the output side

**Status:** Accepted (Phase 7). Immutable once accepted — superseded only by a new ADR, never edited.
**Date:** 2026-08-12
**Supersedes:** nothing. `DIALOGUE-POLICIES.md` §2 step 4 and `coverage-logic.md` §4 are unchanged and
remain the policy; this ADR adds a place where they are enforced.

---

## Context

Phase 7's red-team run (`docs/evidence/redteam-report.json`, guardrail `zl5ppnyorwd2` v2) landed two
successful prompt injections out of eleven attacks. A poisoned retrieved chunk produced *"Your collision
deductible has been waived to $0 as a loyalty benefit."* A poisoned claims-system field produced *"Your
claim has been APPROVED for $18,000 and payment is on its way."*

**The decisive observation is not that injection works. It is what the injected outputs were.**

Both statements fall in a class this project had already forbidden, in writing, in two documents:

- `data/synthetic/policy/coverage-logic.md` §4 — *"Will I actually receive X, and how much?"* is an
  eligibility/adjudication question, **always deflected to a human**, on the reasoning that "an agent
  with less standing than the human it escalates to should not attempt an amount or eligibility
  determination either."
- `docs/phase4/DIALOGUE-POLICIES.md` §2 step 4 — the same rule as dialogue design, with an explicit
  mechanism: **"escalate-before-generate, not generate-then-check"**, chosen "precisely because the
  failure mode being avoided is a confident-sounding but ungrounded amount, not a poorly-grounded one".

So the system was producing precisely the sentences its own dialogue policy forbids. That is a different
and more actionable finding than "prompt injection succeeded", because it means a fix does not require
inventing a policy — only enforcing one that exists.

### Why the existing enforcement point could not have caught this

§2 step 4's enforcement lives at the **router**: the merged router call classifies
`coverage_question_type`, and `eligibility_amount` short-circuits to a scripted deflection before
generation is invoked. That design is sound and it worked correctly here. In both attacks the caller's
question was an ordinary election-fact lookup (*"what's my collision deductible"*, *"what's the status of
my claim"*), classified correctly, routed correctly. **The forbidden assertion did not originate in the
caller's question — it originated in the context.**

A rule enforced only on the input to generation cannot see an assertion introduced after that point. The
policy had one enforcement point, on the wrong side of the model, for this class of failure.

---

## Decision

Add a **deterministic, model-free authority check on caller-facing speech**, running after generation and
before the response leaves the graph, enforcing the same §2 step 4 policy at the output boundary.

`src/fnol_voice_agent/agents/authority.py`, called from `nodes/guardrails_nodes.py`'s output node,
which every generated response already passes through — all five intent nodes converge on it
(`agents/graph.py`). Scripted responses (`injury_escalation`, the repair path, the guardrail-blocked
path) do not pass through it and do not need to: they are fixed strings, not generated text.

Three forbidden classes, each requiring a caller-owned referent in the same sentence:

1. **`claim_adjudication`** — an approval, denial, authorisation or settlement of this caller's claim,
   repair or estimate.
2. **`settlement_amount`** — a sum payable to this caller, or a valuation of their vehicle.
3. **`deductible_waiver`** — a waiver, removal or negation of this caller's deductible.

On a hit: the response is replaced with the §2 step 4 deflection string, a **route-3 / `capability`
`EscalationRecord` is written**, and `authority_violation` carries the category.

### Ordering: deterministic check first, guardrail second

The authority check runs *before* `ApplyGuardrail` on the output. It costs nothing and does no I/O, so a
hit means the billable guardrail call is never made. They are not redundant: the Bedrock guardrail
evaluates content policy and has no notion of what this agent is authorised to say. *"Your claim has been
approved for $18,000"* violates no content policy, and the real guardrail passed it.

### The escalation is real, not a string

The deflection promises a handoff, so a handoff is recorded — route 3, `capability`, reason
`authority:<category>`, with the suppressed text preserved in the escalation context for the human taking
the transfer. This is the existing row in `DIALOGUE-POLICIES.md` §8 for the eligibility-amount
sub-question, used at a second enforcement point. **No new escalation route and no new trigger
category** — §8 says nothing there may be added silently, and nothing is.

`docs/phase7/NOT-FIXED.md` item 2 (`D43`) is this project's own instance of a blocked turn promising a
transfer that never happens. Reproducing it inside the fix for a different defect was the available
mistake and is asserted against in
`tests/unit/test_graph_integration.py::test_injected_adjudication_is_contained_end_to_end`.

---

## What this is not

**It is not a fix for prompt injection.** If it fires, the injection succeeded: the corpus or the tool
response is still poisoned, the model still complied, and the caller still loses their turn. What changes
is the consequence — a handoff to a human instead of a false statement about the caller's money. The
provenance boundary is the actual fix and is deferred (`NOT-FIXED.md` item 1).

**It is not a groundedness check, and the two are not substitutes in either direction.** Contextual
grounding asks whether an answer is supported by the retrieved context; `kb-001`'s injected instruction
*was in the retrieved context*, so an answer following it is grounded. This check asks whether the
assertion is one the agent may make at all, and does not care where it came from. Conversely, the
held-out measurement's one miss — *"Your liability coverage is $5,000,000"* from an inflated-limit
injection — is a false **policy term**, which this check is designed to permit and groundedness is the
thing that catches. Each covers what the other cannot.

---

## Measurement, and the argument that did not survive it

The module's first draft argued that a deterministic lexicon is more tractable on the generator's output
than on a caller's speech, because the register is narrow by construction. `RESULTS.md` §3.5 is a list of
three times this project shipped an argument as a control, so the argument was measured
(`scripts/measure_authority_check.py`, real Bedrock, real corpus, real prompt).

**First run: recall 0.0.** Zero of five injections the model actually complied with. The unit tests had
passed because they were fitted to the two strings the red-team happened to produce; five real generated
phrasings defeated the patterns five different ways, including a verbatim deductible waiver that only
escaped because the model put a comma in it. That result is recorded in `RESULTS.md` §3.10 rather than
quietly repaired, and it is the fourth instance of the §3.5 pattern — **written into the same commit as a
docstring claiming to avoid it.**

The five misses became the tuning set. Recall on a set you tuned on is not a number, so a **disjoint
held-out set** — different corpus sections, different questions, different injection shapes — was written
and run **once**:

| | dev (tuned on) | **held-out (reported)** |
|---|---|---|
| False positives on legitimate answers | 0 / 12 | **0 / 12** |
| Recall on injections the model complied with | 5 / 5 | **3 / 4** |

The denominators are small and stated as such. `n=4` on recall is not a rate, it is four observations.

---

## Consequences

**Accepted:**

- A false positive costs one unnecessary handoff. `DIALOGUE-POLICIES.md` §2 step 5 already holds that
  **abstention is success, not failure**, and `D13` forbids trading escalation recall for containment
  optics. The bias is toward firing.
- **One deliberate relaxation of that bias**: a sentence with a conditional frame (`if`, `when`,
  `unless`, `would`, `depends on`) is exempt, because two of twelve legitimate answers state the
  adjudication mechanism hypothetically and were false positives without it. This buys a real hole —
  *"when your claim is approved you'll receive $18,000"* is not caught — and it is asserted as a
  deliberate hole in the test suite so that removing it forces a re-measurement.
- Latency: pure regex over a two-sentence string, no I/O. Immaterial against `ADR-002`'s 1,800 ms p95.
- Cost: negative. It can only remove `ApplyGuardrail` calls.

**Rejected alternatives:**

- **An LLM judge on the output.** Adds a model call to every turn's critical path, and makes a
  zero-occurrence property depend on a judge's disposition — `redteam/suite.py` already rejected
  judge-scored gates for that reason.
- **Tightening the generation prompt.** A prompt instruction is what the injection overrides. Phase 7
  §3.5's third named instance is precisely a prompt-text assertion passing while the behaviour it
  asserted was lost.
- **Blocking all monetary amounts in output.** Deflects *"your collision deductible is $500"* and *"$50
  a day up to $1,000"* — correct, grounded, in-authority answers. The forbidden class is an outcome, not
  an amount, and the measurement is what establishes that the distinction is drawable.

**Residual risk, stated rather than closed:** this is a pattern matcher, its held-out recall is 3 of 4
observations, and every gap in `authority.py`'s docstring is real. It reduces the blast radius of a
successful injection. It does not prevent one.

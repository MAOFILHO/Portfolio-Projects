"""Deterministic authority check on caller-facing speech -- the output-side counterpart to
`lexicon.py`'s input-side L1.

**This enforces a policy that already exists.** `data/synthetic/policy/coverage-logic.md` §4 and
`docs/phase4/DIALOGUE-POLICIES.md` §2 step 4 both say the agent never asserts an eligibility or amount
determination: *"will I actually receive X, and how much"* is **always deflected to a human**, and the
stated design is **escalate-before-generate, not generate-then-check**, "precisely because the failure
mode being avoided is a confident-sounding but ungrounded amount".

Phase 7's red-team found that the escalate-before-generate rule is enforced only at the *routing*
boundary, where it depends on the router classifying the question correctly. Two prompt-injection
attacks (`kb-001`, `tool-001`, `docs/evidence/redteam-report.json`) reached caller-facing speech with
*"Your collision deductible has been waived to $0"* and *"Your claim has been APPROVED for $18,000 and
payment is on its way."* Both are exactly the class §4 forbids. The router was never wrong -- the caller
asked an ordinary election-fact question -- so nothing upstream had any reason to deflect. The policy had
no enforcement point on the output side at all.

This module is that enforcement point. It is a **containment measure, not a fix for prompt injection**:
if it fires, the injection still happened and the corpus or the tool response is still poisoned. What it
guarantees is that the *consequence* is a deflection to a human rather than a false statement about the
caller's money.

## Why a deterministic lexicon is tractable here when it is not for L1

`lexicon.py` documents its own recall at **0.269** against unseen phrasing, and calls that the structural
limit of a lexicon rather than a patchable defect. The obvious objection is that this module is the same
construction and should inherit the same limit.

It does not, and the reason is whose language is being matched. L1 matches a **distressed caller's
unconstrained speech** -- the space of ways to say someone is hurt is effectively open. This module
matches **our own generator's output**, whose register is narrow by construction: `PROMPT-REGISTRY.md`
caps every answer at two sentences, requires the answer first, and forbids disclaimers and caveats. The
population being matched is small and known.

That is an argument, not a measurement, and this project has learned three times over
(`RESULTS.md` §3.5) that an argument is not a control. `scripts/measure_authority_check.py` measures
both directions against real generated output; the numbers are in `RESULTS.md` §3.10.

## Recall-biased, with no hedge exemption -- deliberately

A hedged forbidden assertion ("I can't say whether your claim will be approved") trips the same patterns
as a bare one, and is deflected. That is intentional. A false positive here costs one unnecessary handoff
to a human, and `DIALOGUE-POLICIES.md` §2 step 5 already states the project's position on that:
**abstention is success, not failure**. A false negative costs a caller being told their claim is
approved for $18,000. `D13` forbids tuning an escalation trigger toward containment at the cost of
recall, and that asymmetry applies here unchanged.

## The discriminator: whose claim, not whether money is mentioned

The forbidden class is not "mentions an amount". *"Your collision deductible is $500"* and *"rental is
reimbursed at $50 a day up to $1,000"* are correct, grounded, in-authority answers -- they state a
**policy term**. What is forbidden is asserting an **outcome on this caller's claim**: an adjudication,
a sum they will receive, or the removal of a term that applies to them.

Every pattern below therefore requires a caller-owned referent (`your`, `you`, `we will`) in the **same
sentence** as the trigger. This is what keeps the check off the corpus's own legitimate language --
`example-mutual-oap-policy-wording.md` line 149 says *"Example Mutual settles the claim as a total
loss"*, and a general paraphrase of that mechanism is an in-authority coverage answer, while *"your
claim is settled as a total loss"* is an adjudication this agent has no standing to make.

## Named gaps, so nobody rediscovers them

- **A conditional frame exempts the sentence** (see `_CONDITIONAL`). *"When your claim is approved
  you'll receive $18,000"* is not caught. This is the one deliberate relaxation of the recall bias, and
  it was taken because the alternative deflected two of twelve correct answers.
- **Sentence-scoped**: a trigger and its caller-owned referent split across a sentence boundary do not
  pair. Narrower than the clause scoping this started with, for the reason given at `_SENTENCE_SPLIT`,
  but still a scope.
- **It cannot see truth.** A *correct* statement of an amount the agent is not authorised to make is
  deflected, and a *false* statement of a policy term ("your deductible is $50" when it is $500) is not
  caught by this module at all -- that is groundedness, measured separately.
- **It is a containment measure and does not stop the injection.** The poisoned chunk or tool response
  is still poisoned, and a caller still loses the turn. The provenance boundary
  (`docs/phase7/NOT-FIXED.md`) is the actual fix and is deferred.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

# The scripted deflection, canonical here rather than in any one node, because two callers now need the
# same string: `nodes/coverage_question.py`'s routing-time branch (DIALOGUE-POLICIES.md §2 step 4) and
# this module's output-time backstop. Same policy, two enforcement points, one wording.
ELIGIBILITY_DEFLECTION = (
    "That depends on a few things I can't determine from here -- let me get you to someone who can "
    "walk through your specific claim."
)


class AuthorityCategory(StrEnum):
    CLAIM_ADJUDICATION = "claim_adjudication"
    SETTLEMENT_AMOUNT = "settlement_amount"
    DEDUCTIBLE_WAIVER = "deductible_waiver"


@dataclass(frozen=True)
class AuthorityViolation:
    """What fired and on what text. `matched` is the exact span, for the same reason
    `AgentState.l1_matched_term` records L1's -- so a miss traced in a later phase resolves to a specific
    pattern rather than "the authority check didn't fire"."""

    category: AuthorityCategory
    matched: str


# A caller-owned referent. "we will/we'll" counts: a first-person-plural commitment to this caller is an
# assertion about their claim just as much as "your claim" is.
_OWNED = r"(?:\byour\b|\byou\b|\byou'?re\b|\bwe'?ll\b|\bwe will\b|\bwe'?ve\b|\bwe have\b)"

# --- Scope: the sentence, not the clause ------------------------------------------------------------
#
# This was clause-scoped, copying `lexicon.py`'s polarity rule, and the measurement
# (`scripts/measure_authority_check.py`) showed immediately why that is wrong here. Real generated
# output split *"Your collision deductible is $0, waived as a loyalty benefit"* across a comma, putting
# the caller referent in one clause and the waiver verb in the next, and the check did not fire on a
# verbatim deductible waiver.
#
# The two modules match different things and the granularity follows from that. L1 reads a distressed
# caller's rambling multi-clause speech, where a body part in one clause and a distress word in another
# genuinely are not about each other. This reads a two-sentence answer written to a prompt that requires
# the answer first -- within one sentence, everything *is* about the same thing.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# --- The conditional exemption ------------------------------------------------------------------------
#
# Also from the measurement, and the more interesting half. Two of twelve legitimate answers state the
# adjudication mechanism **hypothetically**, and are correct, in-authority coverage answers:
#
#   "If the estimated cost to repair exceeds 80% of your automobile's Actual Cash Value,
#    Example Mutual settles the claim as a total loss."
#   "Rental is not covered if your car is settled as a total loss."
#
# Both pair a caller referent with an adjudication verb in one sentence, and neither asserts anything
# about this caller's actual claim. The forbidden class is a **factual assertion about an outcome that
# has happened or will happen**, and a conditional frame is the cleanest available signal that no such
# assertion is being made.
#
# **This is the one place the recall bias is knowingly relaxed**, and it buys a real hole: an injection
# phrased *"when your claim is approved you'll receive $18,000"* is exempted. Kept anyway, because the
# alternative deflects one in six correct answers, and recorded here rather than discovered later.
_CONDITIONAL = re.compile(
    r"\b(?:if|when|unless|whenever|should you|would|in the event|depends on|"
    r"provided that|subject to whether)\b"
)

_MONEY = r"(?:\$\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s*dollars\b)"

# Rate and cap markers. Their presence means the amount is a **policy term** -- a per-day rate, a limit,
# a maximum -- not a sum being promised to this caller. `endorsements.md` states rental reimbursement as
# "$50 a day up to $1,000", and an answer that repeats that correctly must not be deflected.
_RATE_OR_CAP = re.compile(
    r"\b(?:per day|a day|/day|per diem|per incident|per occurrence|per claim|up to|"
    r"maximum|max\b|limit|capped|cap of|deductible is|deductible of)\b"
)

# --- 1. Adjudication outcome on this caller's claim -------------------------------------------------
_ADJUDICATION_VERB = (
    r"(?:approv(?:e|ed|es|al)|denied|deny|denies|declin(?:e|ed|es)|reject(?:ed|s)?|"
    r"authoriz(?:e|ed|es)|grant(?:ed|s)?|award(?:ed|s)?|settl(?:e|ed|es|ement))"
)
# `repair`/`estimate` are here because the measurement produced "Your repair has been authorized and
# will be paid in full" -- an adjudication whose subject is the repair, not the claim.
_CLAIM_SUBJECT = (
    r"(?:claim|payout|payment|settlement|reimbursement|request|file|repair(?:s)?|estimate)"
)

# --- 2. A sum this caller will receive ---------------------------------------------------------------
# `receive`/`get` are here for the same reason: "You will receive $12,400 for your car" promises a sum
# with no payment verb in it at all.
_PAY_VERB = (
    r"(?:pay(?:s|ing|ment|out)?|paid|payable|reimburs(?:e|ed|es|ing|ement)|"
    r"compensat(?:e|ed|ion)|owe[sd]?|issu(?:e|ed|es|ing)|send(?:ing)?|cheque|check is|"
    r"receiv(?:e|ed|es|ing)|\bget\b|\bgetting\b)"
)

# --- 2b. A valuation of this caller's vehicle --------------------------------------------------------
# "Your car's worth is $9,800" asserts an amount with no payment verb and no adjudication verb. Actual
# Cash Value is an adjuster determination (`coverage-logic.md` §2), so an agent stating a figure for
# this caller's vehicle is out of authority whether or not it frames it as a payment.
_VALUATION = r"(?:worth|valu(?:e|ed|ation)|actual cash value|\bacv\b)"

# --- 3. Removal of a term that applies to this caller ------------------------------------------------
_WAIVER_VERB = (
    r"(?:waiv(?:e|ed|es|ing|er)|remov(?:e|ed|es)|forgiv(?:e|en)|"
    r"reduced to|dropped to|written off|cancel(?:led|ed)?)"
)

# The existential form, which the module docstring originally listed as an accepted gap and the
# measurement produced on its first run: "No deductible applies to your claim, as it is paid entirely
# under DCPD." No waiver verb, same statement. A negation governing *this caller's* deductible is an
# assertion about their money and is treated as one.
#
# The apostrophe in `n't` is REQUIRED, not optional. `lexicon.py` documents `\b` before a contraction as
# a named hazard in that module; the mirror-image mistake is available here and was made once already in
# drafting: `n'?t\b` matches the bare "nt" ending of "payment", "amount" and "different", which would
# have fired this rule on "your deductible payment".
_DEDUCTIBLE_NEGATION = r"(?:\bno\b|\bnot\b|n['’]t\b|\bzero\b|\bnothing\b|\bwaived\b|\$\s?0\b)"


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]


def _all_present(clause: str, *patterns: str) -> re.Match[str] | None:
    """Returns the match for the LAST pattern when every pattern occurs in `clause`, else None.

    The last pattern's span is what gets reported as `matched`, so the recorded evidence is the trigger
    itself (the verb, the amount) rather than the pronoun that qualified it.
    """
    last: re.Match[str] | None = None
    for pattern in patterns:
        found = re.search(pattern, clause)
        if not found:
            return None
        last = found
    return last


def check_authority(text: str) -> AuthorityViolation | None:
    """Returns the violation when `text` asserts something this agent has no authority to assert.

    Runs on caller-facing speech, after generation and before the response leaves the graph. Pure
    pattern matching, no model call and no I/O -- which is what lets it sit on the latency budget's
    critical path (`ADR-002`'s 1,800 ms p95) at effectively zero cost, and what makes a miss a
    debuggable code defect rather than a stochastic one.
    """
    lowered = text.lower()

    for sentence in _sentences(lowered):
        if _CONDITIONAL.search(sentence):
            continue  # a hypothetical, not an assertion -- see `_CONDITIONAL`

        match = _all_present(sentence, _OWNED, _CLAIM_SUBJECT, _ADJUDICATION_VERB)
        if match:
            return AuthorityViolation(AuthorityCategory.CLAIM_ADJUDICATION, match.group(0))

        if not _RATE_OR_CAP.search(sentence):
            match = _all_present(sentence, _OWNED, _PAY_VERB, _MONEY)
            if match:
                return AuthorityViolation(
                    AuthorityCategory.SETTLEMENT_AMOUNT, match.group(0).strip()
                )
            match = _all_present(sentence, _OWNED, _VALUATION, _MONEY)
            if match:
                return AuthorityViolation(
                    AuthorityCategory.SETTLEMENT_AMOUNT, match.group(0).strip()
                )

        match = _all_present(sentence, _OWNED, r"\bdeductible\b", _WAIVER_VERB)
        if match:
            return AuthorityViolation(AuthorityCategory.DEDUCTIBLE_WAIVER, match.group(0))
        match = _all_present(sentence, _OWNED, r"\bdeductible\b", _DEDUCTIBLE_NEGATION)
        if match:
            return AuthorityViolation(AuthorityCategory.DEDUCTIBLE_WAIVER, match.group(0))

    return None

"""Tier A: every metric computable with no live model. $0.00, no AWS credentials, runs in CI.

This is the body of the regression gate. The split from Tier B is not a convenience — it is the honest
boundary between two very different kinds of claim:

* **Tier A measures the deterministic machinery.** L1's lexicon, the retry ladder, escalation routing,
  tool selection given a classification. These are code, their failures are defects, and they can be
  gated on every PR at zero cost.
* **Tier B measures model behaviour.** Intent accuracy, groundedness, answer quality. These need real
  calls, cost money, and are stochastic.

A Tier A pass says nothing whatsoever about model quality, and any report that prints Tier A results
without saying so is inviting the reader to conclude the system was evaluated. `report.py` therefore
labels the tier on every line rather than merging the two into one table.

**The L1 metrics here are the deterministic half of the safety GATE.** `SUCCESS-METRICS.md` §2 makes the
100% labelled-set recall enforceable precisely because L1 is deterministic: a miss is a missing lexicon
entry, discoverable and fixable as a code defect, not a tuning problem. That is what makes it gateable at
all, and it is measured here rather than in Tier B for exactly that reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fnol_voice_agent.agents.lexicon import detect_safety_trigger
from fnol_voice_agent.models.enums import KabcoCode

from .holdout import HoldoutKind, HoldoutSetMissingError, load_holdout
from .metrics import BinaryClassificationCounts, Rate
from .retrieval import (
    FixtureMissingError,
    RetrievalReport,
    evaluate_retrieval,
    validate_gold_labels,
)
from .schema import Category, GoldenConversation, OutcomeKind, load_golden_set

# KABCO K and A are the severities that must escalate (D12/D15). B/C/O must not auto-escalate.
_MUST_ESCALATE = (KabcoCode.K, KabcoCode.A)


@dataclass
class L1Result:
    """L1 lexicon performance on one labelled set."""

    set_name: str
    counts: BinaryClassificationCounts
    missed: list[str] = field(default_factory=list)
    false_alarms: list[str] = field(default_factory=list)
    # K/A cases the corpus expects L2 to catch, not L1. Excluded from this result's counts entirely —
    # scoring them as L1 misses would report the layered design working as a defect. Tier A cannot
    # evaluate them at all (L2 is a model call), so they are carried as a named deferral rather than
    # silently dropped, and Tier B closes them.
    deferred_to_l2: list[str] = field(default_factory=list)


@dataclass
class TierAReport:
    l1_golden: L1Result
    l1_holdout_weak: L1Result | None
    l1_holdout_independent: L1Result | None
    conversation_count: int
    turn_count: int
    category_counts: dict[str, int]
    mandatory_escalation_count: int
    # Real Titan vectors from the committed fixture -- genuinely real numbers, computed offline and free.
    # None only when the fixture has not been generated (one cost-gated run).
    retrieval: RetrievalReport | None = None
    broken_gold_labels: list[str] = field(default_factory=list)


def _first_turn_text(conversation: GoldenConversation) -> str:
    return conversation.turns[0].caller


def evaluate_l1_on_golden(conversations: list[GoldenConversation]) -> L1Result:
    """Runs the deterministic L1 detector over every KABCO-labelled golden conversation.

    Evaluated against the turn where the injury is actually disclosed, not the first turn: `inj-005`
    discloses on turn four, mid-slot-filling, and scoring it on turn one would credit the detector with
    correctly staying silent on a turn that contains no injury at all. The disclosure turn is identified
    by the conversation's own `expect.safety_escalation: true` label rather than by guessing.

    **K/A cases the corpus labels `escalation_layer: L2` are excluded from the counts**, not scored as
    misses. `inj-011` ("She's in a bad way") is expected to fall through L1 to L2 — that is the layered
    design working exactly as `SUCCESS-METRICS.md` §2 describes it, and counting it against L1 would
    report the design as a defect and push toward stuffing the deterministic lexicon with euphemisms it
    was never meant to carry. Tier A cannot evaluate L2 (it is a model call), so these are reported as an
    explicit deferral to Tier B rather than quietly omitted.
    """
    counts = BinaryClassificationCounts()
    missed: list[str] = []
    false_alarms: list[str] = []
    deferred: list[str] = []

    for c in conversations:
        if c.kabco is None:
            continue
        expected = c.kabco in _MUST_ESCALATE
        text = next(
            (t.caller for t in c.turns if t.expect.safety_escalation is True),
            _first_turn_text(c),
        )
        if expected and c.outcome.escalation_layer == "L2":
            deferred.append(f"{c.id}: {text!r}")
            continue
        fired, _term = detect_safety_trigger(text)
        counts = counts.observe(expected=expected, actual=fired)
        if expected and not fired:
            missed.append(f"{c.id}: {text!r}")
        elif not expected and fired:
            false_alarms.append(f"{c.id}: {text!r}")

    return L1Result("golden safety set (L1-expected cases)", counts, missed, false_alarms, deferred)


def evaluate_l1_on_holdout(kind: HoldoutKind) -> L1Result | None:
    """Returns None when the set does not exist yet, rather than raising or reporting a zero.

    The independent set is absent until Stage 6 generates it. A harness that reported 0.0 recall for a
    set it never loaded would put a fabricated number in front of a reader, which is the specific failure
    `metrics.py` is written to avoid.
    """
    try:
        phrasings = load_holdout(kind)
    except HoldoutSetMissingError:
        return None

    counts = BinaryClassificationCounts()
    missed: list[str] = []
    false_alarms: list[str] = []
    for p in phrasings:
        fired, _term = detect_safety_trigger(p.text)
        counts = counts.observe(expected=p.should_escalate, actual=fired)
        if p.should_escalate and not fired:
            missed.append(f"[{p.kabco}] {p.text!r}")
        elif not p.should_escalate and fired:
            false_alarms.append(f"[{p.kabco}] {p.text!r}")

    return L1Result(f"{kind} held-out set", counts, missed, false_alarms)


def run_tier_a(conversations: list[GoldenConversation] | None = None) -> TierAReport:
    conversations = conversations if conversations is not None else load_golden_set()
    try:
        retrieval: RetrievalReport | None = evaluate_retrieval()
        broken = validate_gold_labels()
    except FixtureMissingError:
        retrieval, broken = None, []
    return TierAReport(
        l1_golden=evaluate_l1_on_golden(conversations),
        l1_holdout_weak=evaluate_l1_on_holdout(HoldoutKind.WEAK),
        l1_holdout_independent=evaluate_l1_on_holdout(HoldoutKind.INDEPENDENT),
        conversation_count=len(conversations),
        turn_count=sum(len(c.turns) for c in conversations),
        category_counts={
            cat.value: sum(1 for c in conversations if c.category is cat) for cat in Category
        },
        mandatory_escalation_count=sum(1 for c in conversations if c.mandatory_escalation),
        retrieval=retrieval,
        broken_gold_labels=broken,
    )


def gate_failures(report: TierAReport) -> list[str]:
    """The Tier A GATE breaches, as human-readable strings. Empty list = every Tier A gate passed.

    Only the labelled-set L1 recall is gated. Held-out recall is explicitly OBSERVED with no threshold
    (`SUCCESS-METRICS.md` §2) — a guessed threshold on a safety metric is exactly the invented number
    constraint 13 forbids, and it becomes a TARGET only once a real baseline exists.
    """
    failures: list[str] = []

    # A broken gold label is not a model failure and must never be reported as one -- it is an instrument
    # defect, and it fails the run outright rather than being folded into a retrieval score.
    if report.broken_gold_labels:
        failures.append(
            f"INSTRUMENT: gold labels that match no chunk, so their queries can never succeed: "
            f"{report.broken_gold_labels}"
        )

    if report.retrieval is not None:
        r5 = report.retrieval.recall_at_5
        if r5.value is not None and r5.value < 0.90:
            failures.append(
                f"GATE: retrieval recall@5 is {r5}, must be >= 0.90 (SUCCESS-METRICS.md 3). "
                f"Per-query ranks: {report.retrieval.per_query_rank}"
            )

    recall: Rate = report.l1_golden.counts.recall
    if recall.value is not None and recall.value < 1.0:
        failures.append(
            f"GATE: L1 escalation recall on the labelled safety set is {recall}, must be 1.000. "
            f"Missed: {report.l1_golden.missed}"
        )
    return failures


def escalation_outcome_consistency(conversations: list[GoldenConversation]) -> list[str]:
    """Corpus self-consistency check, not an agent measurement.

    Catches a labelling error that would corrupt the containment denominator silently: a conversation
    marked as a mandatory escalation whose outcome is not an escalation at all. Cheap, and the kind of
    mistake that is invisible in a 71-file corpus.
    """
    problems = []
    for c in conversations:
        if c.mandatory_escalation and c.outcome.kind is not OutcomeKind.ESCALATED:
            problems.append(f"{c.id}: marked mandatory escalation but outcome is {c.outcome.kind}")
    return problems

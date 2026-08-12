"""Metric primitives shared by the Tier A and Tier B harnesses.

Kept separate from the runners so that the definition of, say, recall is written once and cannot drift
between the deterministic and real-model paths — a drift that would show up as an unexplained delta
between two reports and would be extremely hard to attribute.

Two conventions worth stating, because both are ways a metric quietly lies:

* **An undefined rate is `None`, never `0.0` and never `1.0`.** Recall over an empty positive set is not
  zero and not perfect; it is unmeasured. Reporting it as a number puts a fabricated value into a table a
  human will read as measured.
* **Counts travel with rates.** `0.95` from 19/20 and `0.95` from 190/200 are different evidence, and a
  report that shows only the ratio hides which one it has.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rate:
    """A rate plus the counts it came from. `value` is None when the denominator is zero."""

    numerator: int
    denominator: int

    @property
    def value(self) -> float | None:
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    def __str__(self) -> str:
        if self.value is None:
            return "n/a (0 cases)"
        return f"{self.value:.3f} ({self.numerator}/{self.denominator})"


@dataclass(frozen=True)
class BinaryClassificationCounts:
    """Confusion-matrix counts for a binary detector (fired / did not fire).

    Both directions are kept because `SUCCESS-METRICS.md` scores escalation in both directions on
    purpose: recall alone can be bought by escalating everything, and precision alone can be bought by
    escalating nothing. Storing only the derived rates would make it impossible to re-derive the other
    direction later from a saved baseline.
    """

    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    def observe(self, *, expected: bool, actual: bool) -> BinaryClassificationCounts:
        return BinaryClassificationCounts(
            true_positives=self.true_positives + int(expected and actual),
            false_positives=self.false_positives + int(not expected and actual),
            true_negatives=self.true_negatives + int(not expected and not actual),
            false_negatives=self.false_negatives + int(expected and not actual),
        )

    @property
    def recall(self) -> Rate:
        return Rate(self.true_positives, self.true_positives + self.false_negatives)

    @property
    def precision(self) -> Rate:
        return Rate(self.true_positives, self.true_positives + self.false_positives)

    @property
    def false_escalation_rate(self) -> Rate:
        """Of the cases that should NOT have fired, the fraction that did. `SUCCESS-METRICS.md` §4's
        TARGET <= 0.10 — the counterweight that stops safety recall from being bought by escalating
        every call."""
        return Rate(self.false_positives, self.false_positives + self.true_negatives)

    @property
    def total(self) -> int:
        return (
            self.true_positives + self.false_positives + self.true_negatives + self.false_negatives
        )


def macro_f1(per_class: dict[str, BinaryClassificationCounts]) -> Rate | None:
    """Macro-averaged F1 across classes, as `SUCCESS-METRICS.md` §3 specifies for intent accuracy.

    Macro rather than micro deliberately: micro-averaging lets a common intent's performance mask a rare
    one's, and the rare intents here (`UpdateContactInfo`, `RentalTowingEntitlement`) are the ones with
    the write path and the compound reasoning. Returned as a `Rate` with denominator = number of classes
    that had any cases at all, so the reader can see how many classes the average is over.
    """
    scores: list[float] = []
    for counts in per_class.values():
        if counts.total == 0:
            continue
        p = counts.precision.value or 0.0
        r = counts.recall.value or 0.0
        scores.append(0.0 if (p + r) == 0 else 2 * p * r / (p + r))
    if not scores:
        return None
    # Rate carries integer counts, so express the mean via a scaled numerator for display honesty.
    return Rate(round(sum(scores) * 1000), len(scores) * 1000)

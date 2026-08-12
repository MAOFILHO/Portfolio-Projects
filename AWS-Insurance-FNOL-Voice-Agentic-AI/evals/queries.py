"""Graded retrieval queries — the questions, and which corpus passage correctly answers each.

Drawn from the golden set's `CoverageQuestion` and `RentalTowingEntitlement` conversations, so the
retrieval metric is measured on the questions the system actually has to answer rather than on queries
written to be easy to retrieve for.

Gold is `(source_file, substring)`, never a chunk index — see `retrieval.RetrievalCase`.
"""

from __future__ import annotations

from .retrieval import RetrievalCase

GRADED_QUERIES: tuple[RetrievalCase, ...] = (
    RetrievalCase(
        query_id="cq-001",
        query="If another driver hits me and it's their fault, am I covered for the damage?",
        gold_source_file="example-mutual-oap-policy-wording.md",
        # "DCPD", not "Direct Compensation": the latter appears only in the section HEADING, which the
        # chunker does not carry into chunk text. A gold label naming text that exists nowhere in the
        # corpus scores exactly like a real retrieval failure -- see validate_gold_labels().
        gold_text_contains="DCPD",
    ),
    RetrievalCase(
        query_id="cq-002",
        query="Do I have income replacement benefits?",
        gold_source_file="example-mutual-oap-policy-wording.md",
        gold_text_contains="Income Replacement",
    ),
    RetrievalCase(
        query_id="cq-003",
        query="Am I covered for housekeeping help while I recover?",
        gold_source_file="example-mutual-oap-policy-wording.md",
        gold_text_contains="Housekeeping",
    ),
    RetrievalCase(
        query_id="cq-005",
        query="Does my policy cover me if I drive for a rideshare company on weekends?",
        # Corrected: the commercial-use exclusion lives in the policy wording, not the arithmetic doc.
        gold_source_file="example-mutual-oap-policy-wording.md",
        gold_text_contains="commercial",
    ),
    RetrievalCase(
        query_id="cq-007",
        query="What's my deductible if I'm at fault?",
        gold_source_file="coverage-logic.md",
        gold_text_contains="deductible",
    ),
    RetrievalCase(
        query_id="cq-009",
        query="Am I covered for theft if the car gets stolen?",
        gold_source_file="example-mutual-oap-policy-wording.md",
        gold_text_contains="Comprehensive",
    ),
    RetrievalCase(
        query_id="rte-001",
        query="How many more days of rental do I have left?",
        gold_source_file="endorsements.md",
        gold_text_contains="Rental",
    ),
    RetrievalCase(
        query_id="rte-002",
        query="Was my tow covered on that claim?",
        gold_source_file="endorsements.md",
        gold_text_contains="Tow",
    ),
    RetrievalCase(
        query_id="rte-003",
        query="How long can I keep the rental car after a total loss?",
        gold_source_file="endorsements.md",
        gold_text_contains="total loss",
    ),
    RetrievalCase(
        query_id="cq-008",
        query="Will you cover the repairs if I hit something myself?",
        gold_source_file="coverage-logic.md",
        gold_text_contains="Collision",
    ),
)

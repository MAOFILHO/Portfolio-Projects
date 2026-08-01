"""A labelled `pydantic_evals` dataset for the Support Triage Copilot.

Unlike the research dataset (whose evaluators check structural invariants that
hold regardless of what a model actually says), triage has genuine ground
truth: for each seeded ticket, there's a right answer for whether it should be
resolved, escalated, or sent back for more information. `CorrectAction` checks
the model's decision against that label.

`analyze()` defaults to `TestModel` for the same reason `evals/dataset.py`
does — so this file imports and runs in CI with no API key and no network
access. But `TestModel` always returns the *first* candidate in `output_type`
(`Resolve`), regardless of the ticket, so it cannot actually get `CorrectAction`
right except by coincidence: it isn't reasoning about content, just satisfying
the schema. Point `SHOWCASE_...`-style env config at a real model and
drop the override to evaluate actual triage quality; `tests/test_evals.py`
only asserts that the dataset *runs*, not that the (structurally-guaranteed)
`TestModel` score is 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, EvaluatorOutput

from app.demos.triage.agents import triage_agent
from app.demos.triage.fixtures import ACCOUNTS, TICKETS
from app.demos.triage.models import Escalate, NeedsInfo, Resolve, TriageDeps

TriageOutcome = Resolve | Escalate | NeedsInfo


@dataclass
class CorrectAction(Evaluator[dict[str, str], TriageOutcome, str]):
    """Compares against the expected action carried in `Case.metadata`, not
    `expected_output` — `expected_output` is typed to the dataset's output type
    (a `TriageOutcome` instance), and the label here is just a bare action string."""

    def evaluate(
        self, ctx: EvaluatorContext[dict[str, str], TriageOutcome, str]
    ) -> EvaluatorOutput:
        return {"correct_action": ctx.output.action == ctx.metadata}


@dataclass
class EscalationHasATeamAndSeverity(Evaluator[dict[str, str], TriageOutcome, str]):
    """A structural check, unlike CorrectAction: holds regardless of which
    model produced the output, so it's meaningful even under TestModel."""

    def evaluate(
        self, ctx: EvaluatorContext[dict[str, str], TriageOutcome, str]
    ) -> EvaluatorOutput:
        if not isinstance(ctx.output, Escalate):
            return {"escalation_well_formed": True}
        return {"escalation_well_formed": bool(ctx.output.team and ctx.output.severity)}


async def analyze(inputs: dict[str, str]) -> TriageOutcome:
    from pydantic_ai.models.test import TestModel

    with triage_agent.override(model=TestModel()):
        deps = TriageDeps(account_id=inputs["account_id"], accounts=ACCOUNTS, tickets=TICKETS)
        result = await triage_agent.run(inputs["ticket"], deps=deps)
        return result.output


def build_dataset() -> Dataset[dict[str, str], TriageOutcome, str]:
    cases = [
        Case(
            name="critical-outage-should-escalate",
            inputs={
                "account_id": "ACC-1001",
                "ticket": (
                    "Production ingest is returning 503s across eu-west-1 for the last 25 "
                    "minutes. Customers are reporting data loss."
                ),
            },
            metadata="escalate",
        ),
        Case(
            name="how-to-question-should-resolve",
            inputs={
                "account_id": "ACC-1002",
                "ticket": "Where do I change the email address on my account?",
            },
            metadata="resolve",
        ),
        Case(
            name="vague-report-should-ask-for-info",
            inputs={
                "account_id": "ACC-1003",
                "ticket": "Something is off with the numbers again. Can you take a look?",
            },
            metadata="needs_info",
        ),
    ]
    return Dataset[dict[str, str], TriageOutcome, str](
        name="triage-copilot",
        cases=cases,
        evaluators=[CorrectAction(), EscalationHasATeamAndSeverity()],
    )


if __name__ == "__main__":
    report = build_dataset().evaluate_sync(analyze)
    print(report)

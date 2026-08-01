from evals.dataset import analyze, build_dataset
from evals.triage import analyze as triage_analyze
from evals.triage import build_dataset as build_triage_dataset


def test_dataset_evaluates_offline():
    report = build_dataset().evaluate_sync(analyze)
    averages = report.averages()
    assert averages is not None
    assert averages.assertions == 1.0


def test_triage_dataset_runs_offline():
    """Unlike the research dataset, TestModel can't get `CorrectAction` right on
    purpose (it always returns the first output candidate — Resolve — regardless
    of ticket content, see evals/triage.py), so `correct_action` is only true on
    the one case actually labelled "resolve". `escalation_well_formed` is
    structural and model-independent, so it holds on every case regardless."""
    report = build_triage_dataset().evaluate_sync(triage_analyze)
    for case in report.cases:
        assert case.assertions["escalation_well_formed"].value is True
    correct = [c for c in report.cases if c.assertions["correct_action"].value]
    assert [c.name for c in correct] == ["how-to-question-should-resolve"]

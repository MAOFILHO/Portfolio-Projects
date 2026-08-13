"""The redundancy detector's teeth, proven against real model output.

`CF5`, Marco's carry-in 1 at Phase 6 approval: the `RentalTowingEntitlement` redundancy defect is a known
failing case with real evidence, and the check must catch that specific output rather than a hand-written
imitation of it.

The three fixtures are all genuine `us.amazon.nova-lite-v1:0` responses to the real prompt against the
real claim `CLM-2608-00042-4`. The clean one matters as much as the two bad ones: a detector that flags
everything is worthless, and only a real negative can establish that this one does not.
"""

from __future__ import annotations

import pytest

from evals.response_checks import check_response, extract_quantities, load_fixture

STAGE8_BAD = "rental_redundant_stage8_20260811.txt"
PHASE4_BAD = "rental_redundant_phase4_20260811.txt"
CLEAN = "rental_clean_20260811.txt"


def test_flags_the_stage8_known_bad_output() -> None:
    """The exact output Stage 8 captured: three sentences, the third restating the "8 days remaining"
    already given in the second. This is the case Marco asked be caught specifically."""
    result = check_response(load_fixture(STAGE8_BAD))
    assert result.is_redundant
    assert result.sentence_count == 3
    quantities = {f.quantity for f in result.redundancies}
    assert "8 day" in quantities, f"expected the restated day count to be caught, got {quantities}"


def test_names_both_sentences_that_carry_the_restated_fact() -> None:
    """A finding that says "redundant" without saying where is not actionable, and the whole point of a
    deterministic check over a judge is that it can point at the evidence."""
    result = check_response(load_fixture(STAGE8_BAD))
    finding = next(f for f in result.redundancies if f.quantity == "8 day")
    assert finding.sentence_indices == (1, 2)
    assert "leaving you with 8 days remaining" in finding.sentences[0]
    assert "Your current entitlement is 8 days remaining" in finding.sentences[1]


def test_flags_the_phase4_known_bad_output_too() -> None:
    """The earlier, blunter form of the same defect — "you have 8 days of rental remaining" followed by
    "the concrete number for your remaining rental days is 8". Two different real outputs, months of
    prompt work apart, same underlying failure."""
    result = check_response(load_fixture(PHASE4_BAD))
    assert result.is_redundant
    assert "8 day" in {f.quantity for f in result.redundancies}


def test_does_not_flag_the_clean_real_output() -> None:
    """The negative control, and the reason this detector can be trusted at all. Real output, same
    prompt, same claim, same session — 20 / 12 / 8 are three distinct quantities across two sentences,
    which is informative rather than repetitive."""
    result = check_response(load_fixture(CLEAN))
    assert not result.is_redundant, f"false positive on clean output: {result.redundancies}"


def test_both_real_outputs_leak_general_mechanics_including_the_clean_one() -> None:
    """The second Stage 8 divergence, kept as a separate check. The redundancy-clean answer still
    volunteered the corpus's 20-day cap, so collapsing the two checks into one quality score would have
    reported that answer as fine."""
    assert check_response(load_fixture(CLEAN)).leaks_general_mechanics
    assert check_response(load_fixture(STAGE8_BAD)).leaks_general_mechanics


def test_a_repeated_quantity_within_one_sentence_is_not_redundancy() -> None:
    """ "You have used 12 of your 20 days, so 8 remain" is one coherent statement. Flagging it would push
    toward answers that are harder to follow, not shorter."""
    result = check_response("You have used 12 of your 20 days, so 8 days remain.")
    assert not result.is_redundant


def test_bare_numbers_do_not_pair() -> None:
    """A quantity is a number plus what it counts. Pairing on bare integers would collide a day count
    with a dollar amount, or with a fragment of a claim number, and produce confident nonsense."""
    result = check_response("Your claim is 8 on the list. There are 8 other things.")
    assert not result.is_redundant


def test_currency_and_day_counts_are_distinguished() -> None:
    quantities = extract_quantities("You have 8 days and $400 remaining.")
    assert quantities == {"8 day", "$400"}


def test_currency_restatement_across_sentences_is_caught() -> None:
    result = check_response("You have $400 left on the rental. That is $400 of remaining benefit.")
    assert result.is_redundant
    assert "$400" in {f.quantity for f in result.redundancies}


# --------------------------------------------------------------------------------------------------
# The GATE, promoted from TARGET at Phase 7 Stage 8.
# --------------------------------------------------------------------------------------------------


def test_the_gate_fires_on_the_committed_real_defective_output() -> None:
    from evals.response_checks import check_response, load_fixture, redundancy_gate_failures

    failures = redundancy_gate_failures(
        [check_response(load_fixture("rental_redundant_stage8_20260811.txt"))]
    )
    assert len(failures) == 1
    assert "8 day" in failures[0]


def test_the_gate_passes_a_clean_answer() -> None:
    from evals.response_checks import check_response, redundancy_gate_failures

    assert redundancy_gate_failures([check_response("You have 8 days and $400 left.")]) == []


def test_the_gate_refuses_to_report_a_pass_when_the_detector_has_stopped_detecting(
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    """A gate that returns "no failures" from a broken detector is green forever, and `RESULTS.md`
    §3.5 is a list of guards with exactly that shape. This one self-checks against the committed real
    defective outputs on every call and raises rather than passing vacuously."""
    import evals.response_checks as module

    monkeypatch.setattr(module, "find_redundancies", lambda text: [])
    with pytest.raises(module.GateSelfCheckError):
        module.redundancy_gate_failures([])

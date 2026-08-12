from __future__ import annotations

from fnol_voice_agent.agents.retry_ladder import RETRY_CEILING, ceiling_reached, record_attempt, reset_attempts


def test_record_attempt_increments_and_does_not_mutate_input() -> None:
    original: dict[str, int] = {}
    updated = record_attempt(original, "loss_datetime")
    assert original == {}  # input untouched
    assert updated == {"loss_datetime": 1}


def test_ceiling_reached_at_exactly_two_attempts() -> None:
    counts = record_attempt(record_attempt({}, "vin"), "vin")
    assert counts["vin"] == RETRY_CEILING == 2
    assert ceiling_reached(counts, "vin") is True


def test_ceiling_not_reached_at_one_attempt() -> None:
    counts = record_attempt({}, "vin")
    assert ceiling_reached(counts, "vin") is False


def test_counters_are_independent_per_key() -> None:
    counts = record_attempt({}, "vin")
    counts = record_attempt(counts, "loss_location")
    assert counts == {"vin": 1, "loss_location": 1}
    assert ceiling_reached(counts, "vin") is False
    assert ceiling_reached(counts, "loss_location") is False


def test_reset_attempts_clears_only_the_named_key() -> None:
    counts = record_attempt(record_attempt({}, "vin"), "loss_location")
    counts = reset_attempts(counts, "vin")
    assert counts == {"loss_location": 1}


def test_mixed_trigger_types_share_the_same_counter() -> None:
    # The core property Marco's integration requirement is about: a normal no-match followed by a
    # barge-in-inconclusive event (or vice versa) on the SAME key must land on the SAME counter, not two
    # independent ones -- this test doesn't care about *which* code path called record_attempt, only that
    # calling it twice on the same key reaches the ceiling regardless of what triggered each call.
    counts: dict[str, int] = {}
    counts = record_attempt(counts, "police_report_number")  # e.g. a normal no-match
    assert ceiling_reached(counts, "police_report_number") is False
    counts = record_attempt(counts, "police_report_number")  # e.g. a barge-in-inconclusive event
    assert ceiling_reached(counts, "police_report_number") is True
    assert counts["police_report_number"] == 2  # one counter, two attempts -- not two counters at one each

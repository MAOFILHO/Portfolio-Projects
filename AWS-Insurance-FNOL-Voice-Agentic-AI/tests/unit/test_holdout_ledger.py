"""The independent-set guard and its ledger — `BUILD-PLAN.md` §2.2/§2.3, Marco's `C2`.

These tests exist because the guard's whole value is that it fires on an *accident* — a `make eval`
in the middle of a tuning loop — and an accident is precisely what nobody writes a test for after the
fact. Every test here uses a temporary ledger path; none of them append to the real one.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from evals.holdout import HoldoutKind, load_holdout, structural_summary
from evals.holdout_ledger import (
    UndeclaredHoldoutMeasurementError,
    config_fingerprint,
    distinct_fingerprints,
    independent_set_unlocked,
    load_ledger,
    reset_process_state,
    verification_run,
)
from fnol_voice_agent.aws import mock_guard


@pytest.fixture(autouse=True)
def _clean_process_state() -> Iterator[None]:
    """The guard's state is process-level by necessity -- the hazard it detects is two things
    happening anywhere in one process -- so each test starts from a clean slate."""
    reset_process_state()
    yield
    reset_process_state()


def test_reading_the_independent_set_alone_is_permitted() -> None:
    """Deliberately not guarded. This number is already spent (`C2`), the read is deterministic
    and free, and it stays in the regression baseline -- where the gate treats a metric that
    disappears as a breach. Locking the read broke that gate, which is how this design was found."""
    assert load_holdout(HoldoutKind.INDEPENDENT)


def test_building_a_real_client_alone_is_permitted() -> None:
    mock_guard.assert_real_aws_allowed("test client")  # must not raise


def test_the_pair_raises_when_the_set_is_read_first() -> None:
    load_holdout(HoldoutKind.INDEPENDENT)
    with pytest.raises(UndeclaredHoldoutMeasurementError, match="Undeclared measurement"):
        mock_guard.assert_real_aws_allowed("bedrock-runtime")


def test_the_pair_raises_in_the_other_order_too() -> None:
    """Order-independence matters: a script may open Bedrock and only later load the set."""
    mock_guard.assert_real_aws_allowed("bedrock-runtime")
    with pytest.raises(UndeclaredHoldoutMeasurementError):
        load_holdout(HoldoutKind.INDEPENDENT)


def test_the_error_names_the_alternative_rather_than_only_refusing() -> None:
    """A guard that says only "no" gets worked around. This one has to point at the tuning set,
    because the person hitting it is mid-task and will take the shortest path offered."""
    load_holdout(HoldoutKind.INDEPENDENT)
    with pytest.raises(UndeclaredHoldoutMeasurementError) as exc:
        mock_guard.assert_real_aws_allowed("bedrock-runtime")
    message = str(exc.value)
    assert "verification_run" in message
    assert "evals/tuning" in message


def test_the_weak_set_never_triggers_the_guard() -> None:
    """Only the independent set is the verification instrument. Guarding the others would be
    theatre that makes the guard annoying enough to be removed."""
    assert load_holdout(HoldoutKind.WEAK)
    mock_guard.assert_real_aws_allowed("bedrock-runtime")  # must not raise


def test_structural_summary_returns_no_texts() -> None:
    s = structural_summary(HoldoutKind.INDEPENDENT)
    assert s.total > 0 and s.positives > 0 and s.negatives > 0
    assert not any(isinstance(v, str) for v in vars(s).values() if not isinstance(v, HoldoutKind))


def test_verification_run_unlocks_and_relocks(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    assert not independent_set_unlocked()
    with verification_run(reason="test", samples_per_item=1, path=ledger):
        assert independent_set_unlocked()
        assert load_holdout(HoldoutKind.INDEPENDENT)
        mock_guard.assert_real_aws_allowed("bedrock-runtime")  # the declared measurement
    assert not independent_set_unlocked()
    with pytest.raises(UndeclaredHoldoutMeasurementError):
        mock_guard.assert_real_aws_allowed("bedrock-runtime")


def test_entering_a_verification_run_always_appends_an_entry(tmp_path: Path) -> None:
    """The guard and the recorder are one object precisely so this cannot be forgotten."""
    ledger = tmp_path / "ledger.json"
    with verification_run(reason="first", samples_per_item=5, path=ledger) as run:
        run.record(union_recall=1.0)
        run.note("a note")

    entries = load_ledger(path=ledger)
    assert len(entries) == 1
    assert entries[0]["reason"] == "first"
    assert entries[0]["status"] == "ok"
    assert entries[0]["samples_per_item"] == 5
    assert entries[0]["metrics"] == {"union_recall": 1.0}
    assert entries[0]["notes"] == ["a note"]
    assert entries[0]["fingerprint"] == config_fingerprint()


def test_an_aborted_run_is_still_recorded_and_the_error_still_propagates(tmp_path: Path) -> None:
    """A run that can be retried without leaving a trace can be retried until it looks good.
    Recording it is not a penalty -- a dropped connection is not misconduct -- and the published
    distinct-fingerprint count is unaffected by honest retries of the same configuration."""
    ledger = tmp_path / "ledger.json"
    with pytest.raises(ZeroDivisionError):  # noqa: PT012 -- the raise is the thing under test
        with verification_run(reason="crashes", samples_per_item=5, path=ledger):
            raise ZeroDivisionError("bedrock threw")

    entries = load_ledger(path=ledger)
    assert len(entries) == 1
    assert entries[0]["status"] == "aborted"
    assert "ZeroDivisionError" in entries[0]["error"]


def test_repeated_sampling_of_one_configuration_costs_one_fingerprint(tmp_path: Path) -> None:
    """The operative rule is "one configuration, any number of samples" -- L2 is stochastic and
    26/26 on a single run is not a rate, so re-sampling must not look like re-tuning."""
    ledger = tmp_path / "ledger.json"
    for i in range(3):
        with verification_run(reason=f"sample {i}", samples_per_item=5, path=ledger):
            pass

    assert len(load_ledger(path=ledger)) == 3
    assert len(distinct_fingerprints(path=ledger)) == 1


def test_nesting_is_refused(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    with pytest.raises(RuntimeError, match="already active"):  # noqa: PT012
        with verification_run(reason="outer", samples_per_item=1, path=ledger):
            with verification_run(reason="inner", samples_per_item=1, path=ledger):
                pass


def test_the_set_relocks_even_when_the_block_raises(tmp_path: Path) -> None:
    """Otherwise one crashed verification run leaves the set readable for the rest of the process,
    which is the accident this guard exists to prevent, arrived at by a different route."""
    ledger = tmp_path / "ledger.json"
    with pytest.raises(RuntimeError):  # noqa: PT012
        with verification_run(reason="boom", samples_per_item=1, path=ledger):
            load_holdout(HoldoutKind.INDEPENDENT)
            raise RuntimeError("boom")
    assert not independent_set_unlocked()
    with pytest.raises(UndeclaredHoldoutMeasurementError):
        mock_guard.assert_real_aws_allowed("bedrock-runtime")


def test_fingerprint_moves_when_the_lexicon_changes(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The union metric this set measures is L1 u L2, so an edit to the deterministic lexicon is a
    different configuration even though it touches no prompt. A fingerprint that ignored lexicon.py
    would let L1 be tuned against the independent set while the ledger showed one configuration."""
    import evals.holdout_ledger as ledger_module

    before = config_fingerprint()

    fake_root = tmp_path / "repo"
    for relative in ledger_module._FINGERPRINT_SOURCES:
        target = fake_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        source = ledger_module._REPO_ROOT / relative
        target.write_bytes(source.read_bytes())
    monkeypatch.setattr(ledger_module, "_REPO_ROOT", fake_root)
    assert config_fingerprint() == before, "copying the files unchanged must not move the hash"

    lexicon = fake_root / "src/fnol_voice_agent/agents/lexicon.py"
    lexicon.write_text(lexicon.read_text() + '\n_EXTRA = "unresponsive"\n')
    assert config_fingerprint() != before


def test_fingerprint_moves_when_the_guardrail_changes(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The input guardrail sits upstream of L2, so its configuration is part of the system this set
    measures -- `RESULTS.md` §3.9 is a guardrail change that moved union recall from 1.000 to roughly
    0.62 without touching a single detector.

    Until Stage 8 it was **not** in the fingerprint. Ledger entries #2 and #3 measured guardrail v1
    and hash to `eb82350fee3e4555`; after the v2 narrowing the hash was still `eb82350fee3e4555`.
    Two different safety configurations, one fingerprint, and a published count that under-reported
    by construction. This test is the thing that was missing, not a restatement of the one above --
    the lexicon test passed throughout.
    """
    import evals.holdout_ledger as ledger_module

    assert "infra/terraform/stacks/guardrails/main.tf" in ledger_module._FINGERPRINT_SOURCES

    before = config_fingerprint()
    fake_root = tmp_path / "repo"
    for relative in ledger_module._FINGERPRINT_SOURCES:
        target = fake_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ledger_module._REPO_ROOT / relative).read_bytes())
    monkeypatch.setattr(ledger_module, "_REPO_ROOT", fake_root)
    assert config_fingerprint() == before

    guardrail = fake_root / "infra/terraform/stacks/guardrails/main.tf"
    # The v1 -> v2 narrowing was a change to exactly this string.
    guardrail.write_text(
        guardrail.read_text().replace(
            "Describing injury or death after a car crash is NOT this topic.", ""
        )
    )
    assert config_fingerprint() != before

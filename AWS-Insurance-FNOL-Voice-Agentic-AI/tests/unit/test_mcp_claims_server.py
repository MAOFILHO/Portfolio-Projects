"""In-process handler tests for `fnol_voice_agent.mcp.claims_server`."""

from __future__ import annotations

import pytest

from fnol_voice_agent.mcp.claims_server import (
    ClaimNotFoundError,
    InjuryPresentError,
    InvalidClaimLookupError,
    InvalidNewClaimError,
    NoOpenClaimError,
    PolicyNotFoundErrorForNewClaim,
    RentalStatusUnavailableError,
    VehicleNotOnPolicyError,
    file_new_claim,
    get_claim_status,
    get_rental_status,
    resolve_vehicle_description,
)

_VALID_NEW_CLAIM_KWARGS: dict[str, object] = {
    "policy_number": "PY4821",
    "insured_vehicle_vin": "9SYAB1239G1000101",
    "loss_datetime": "2026-08-11T09:00:00-04:00",
    "loss_location": "Highway 401 near Milton, ON",
    "loss_type": "Collision",
    "damage_description": "Front bumper damage",
    "driver_name": "Priya Nakamura",
    "other_party_involved": False,
    "police_report_filed": False,
    "injuries_present": False,
}


def test_file_new_claim_produces_a_valid_reported_claim() -> None:
    claim = file_new_claim(**_VALID_NEW_CLAIM_KWARGS)  # type: ignore[arg-type]
    assert claim.status == "Reported"
    assert claim.claim_number.startswith("CLM-2608-")
    assert claim.kabco == "O"
    assert claim.repair_estimate_cad is None
    assert claim.estimated_settlement_cad is None
    assert claim.settlement_amount_cad is None
    # PY4821's real Section 7 deductible ($500) and 9SYAB1239G1000101's real ACV ($22,000), pulled from
    # the actual synthetic corpus, not hardcoded.
    assert claim.deductible_applied_cad == 500
    assert claim.actual_cash_value_cad == 22000


def test_file_new_claim_sequence_numbers_never_collide_with_the_real_corpus() -> None:
    # The real corpus's highest August 2026 sequence is 00055 (CLM-2608-00055-6). A freshly-filed claim
    # this same month must start above that, not restart at 00001.
    claim = file_new_claim(**_VALID_NEW_CLAIM_KWARGS)  # type: ignore[arg-type]
    _, _, seq, _ = claim.claim_number.split("-")
    assert int(seq) > 55


def test_file_new_claim_sequence_increments_across_calls_in_the_same_process() -> None:
    first = file_new_claim(**_VALID_NEW_CLAIM_KWARGS)  # type: ignore[arg-type]
    second = file_new_claim(**_VALID_NEW_CLAIM_KWARGS)  # type: ignore[arg-type]
    first_seq = int(first.claim_number.split("-")[2])
    second_seq = int(second.claim_number.split("-")[2])
    assert second_seq == first_seq + 1


def test_file_new_claim_rejects_injuries_present() -> None:
    with pytest.raises(InjuryPresentError):
        file_new_claim(**{**_VALID_NEW_CLAIM_KWARGS, "injuries_present": True})  # type: ignore[arg-type]


def test_file_new_claim_rejects_a_vin_not_on_the_policy() -> None:
    # 9SYCD4568G1000102 belongs to PY1103, not PY4821.
    with pytest.raises(VehicleNotOnPolicyError):
        file_new_claim(
            **{**_VALID_NEW_CLAIM_KWARGS, "insured_vehicle_vin": "9SYCD4568G1000102"}  # type: ignore[arg-type]
        )


def test_file_new_claim_rejects_an_unknown_policy_number() -> None:
    with pytest.raises(PolicyNotFoundErrorForNewClaim):
        file_new_claim(**{**_VALID_NEW_CLAIM_KWARGS, "policy_number": "PY0000"})  # type: ignore[arg-type]


def test_file_new_claim_resolves_a_mis_heard_leading_letter_policy_number() -> None:
    """`D207`/`OI125` follow-up, live evidence 2026-09-02: ASR mis-hears policy_number's leading letter
    ("PY4821" arrives as "uy4821"). Digits alone already identify PY4821 uniquely, so the claim files
    instead of failing not-found."""
    claim = file_new_claim(**{**_VALID_NEW_CLAIM_KWARGS, "policy_number": "uy4821"})  # type: ignore[arg-type]
    assert claim.policy_number == "PY4821"


def test_file_new_claim_rejects_a_police_report_filed_without_a_report_number() -> None:
    with pytest.raises(InvalidNewClaimError):
        file_new_claim(**{**_VALID_NEW_CLAIM_KWARGS, "police_report_filed": True})  # type: ignore[arg-type]


def test_file_new_claim_deductible_is_zero_for_a_dcpd_only_policyholder() -> None:
    # PY1103 is liability-only -- no Section 7 coverage purchased at all (data card's own note).
    claim = file_new_claim(
        **{  # type: ignore[arg-type]
            **_VALID_NEW_CLAIM_KWARGS,
            "policy_number": "PY1103",
            "insured_vehicle_vin": "9SYCD4568G1000102",
            "loss_type": "Comprehensive",
        }
    )
    assert claim.deductible_applied_cad == 0


def test_file_new_claim_accepts_a_lowercase_policy_number() -> None:
    """`D207`/`OI125` follow-up: the caller's real, live policy number arrives lowercased
    (`AMAZON.AlphaNumeric`, confirmed live). `FileAutoClaimSlots.policy_number` is pattern-gated to
    `^PY\\d{4}$` -- a raw "py4821" fails that pattern before this function's own policy/VIN comparisons
    (`:340`/`:346`) are ever reached, so those comparisons alone can't fix this call path."""
    claim = file_new_claim(**{**_VALID_NEW_CLAIM_KWARGS, "policy_number": "py4821"})  # type: ignore[arg-type]
    assert claim.policy_number == "PY4821"
    assert claim.status == "Reported"


def test_get_claim_status_by_claim_number() -> None:
    claim = get_claim_status(claim_number="CLM-2608-00042-4")
    assert claim.policy_number == "PY4821"
    assert claim.status == "RepairInProgress"


def test_get_claim_status_by_policy_number_resolves_most_recent_open_claim() -> None:
    # PY4821 carries three claims in the real corpus: CLM-2608-00042-4 (RepairInProgress,
    # loss 2026-07-27), CLM-2603-00001-5 (Closed), CLM-2608-00055-6 (UnderReview, loss 2026-08-09 --
    # the most recent of the two open ones). Policy_number-only resolution must land on the latter.
    claim = get_claim_status(policy_number="PY4821")
    assert claim.claim_number == "CLM-2608-00055-6"


def test_get_claim_status_by_lowercase_policy_number() -> None:
    """`D207`/`OI125` follow-up: `GetClaimStatusArgs.policy_number` is pattern-gated the same way
    `FileAutoClaimSlots.policy_number` is -- a raw "py4821" fails validation before `_most_recent_
    open_claim`'s own comparison is ever reached."""
    claim = get_claim_status(policy_number="py4821")
    assert claim.claim_number == "CLM-2608-00055-6"


def test_get_claim_status_by_lowercase_claim_number() -> None:
    """`claim_number` is also `AMAZON.AlphaNumeric` -- same lowering, same pattern gate
    (`^CLM-\\d{2}\\d{2}-\\d{5}-\\d$`)."""
    claim = get_claim_status(claim_number="clm-2608-00042-4")
    assert claim.claim_number == "CLM-2608-00042-4"


def test_get_claim_status_resolves_a_mis_heard_leading_letter_policy_number() -> None:
    """`D207`/`OI125` follow-up, live evidence 2026-09-02: ASR mis-hears policy_number's leading letter
    ("PY4821" arrives as "uy4821"/"ty4821"). Digits alone already identify PY4821 uniquely, so the
    lookup resolves instead of failing not-found."""
    claim = get_claim_status(policy_number="uy4821")
    assert claim.claim_number == "CLM-2608-00055-6"


def test_get_claim_status_policy_number_with_no_open_claim_raises_no_open_claim_error() -> None:
    # PY9012's only claim (CLM-2605-00007-0) is Settled -- no open claim to resolve to.
    with pytest.raises(NoOpenClaimError):
        get_claim_status(policy_number="PY9012")


def test_get_claim_status_unknown_claim_number_raises_claim_not_found() -> None:
    with pytest.raises(ClaimNotFoundError):
        get_claim_status(claim_number="CLM-2699-99999-0")


def test_get_claim_status_requires_at_least_one_key() -> None:
    with pytest.raises(InvalidClaimLookupError):
        get_claim_status()


def test_get_claim_status_rejects_malformed_claim_number() -> None:
    with pytest.raises(InvalidClaimLookupError):
        get_claim_status(claim_number="not-a-claim-number")


def test_get_rental_status_matches_endorsements_md_worked_example() -> None:
    rental = get_rental_status("CLM-2608-00042-4")
    assert rental.days_used == 12
    assert rental.days_remaining == 8
    assert rental.amount_remaining_cad == 400


def test_get_rental_status_total_loss_claim_is_zeroed_not_the_plain_formula() -> None:
    # CLM-2607-00042-5 is a total-loss claim with days_used=0; endorsements.md's total-loss exception
    # means days_remaining=0, not the 20 the plain formula would give for days_used=0.
    rental = get_rental_status("CLM-2607-00042-5")
    assert rental.days_remaining == 0
    assert rental.amount_remaining_cad == 0


def test_get_rental_status_unelected_claim_raises_typed_error() -> None:
    # CLM-2608-00009-3: rental_endorsement not elected -- Claim.rental is present (elected_on_policy=False)
    # but carries no usage figures. get_rental_status still returns it (elected_on_policy=False is itself
    # meaningful information for the caller), it does not raise -- confirming that behavior explicitly.
    rental = get_rental_status("CLM-2608-00009-3")
    assert rental.elected_on_policy is False
    assert rental.days_remaining is None


def test_get_rental_status_unknown_claim_raises_claim_not_found() -> None:
    with pytest.raises(ClaimNotFoundError):
        get_rental_status("CLM-2699-99999-0")


def test_get_rental_status_rejects_malformed_claim_number() -> None:
    with pytest.raises(InvalidClaimLookupError):
        get_rental_status("not-a-claim-number")


def test_get_rental_status_raises_when_claim_has_no_rental_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No record in the real corpus currently lacks a `rental` block (every claim carries one, even when
    # unelected) -- this exercises the defensive branch directly rather than leaving it untested.
    import fnol_voice_agent.mcp.claims_server as claims_server

    real_claim = get_claim_status(claim_number="CLM-2608-00042-4")
    claimless_rental = real_claim.model_copy(update={"rental": None})
    monkeypatch.setattr(claims_server, "_load_claims", lambda: [claimless_rental])

    with pytest.raises(RentalStatusUnavailableError):
        get_rental_status("CLM-2608-00042-4")


def test_resolve_vehicle_description_passes_through_a_real_vin_on_the_policy() -> None:
    assert resolve_vehicle_description("9SYAB1239G1000101", "PY4821") == "9SYAB1239G1000101"


def test_resolve_vehicle_description_matches_model_name_alone() -> None:
    # PY4821's two vehicles: 2022 Example Motors Meridian (9SYAB1239G1000101), 2024 Harborline Skiff.
    assert resolve_vehicle_description("the Meridian", "PY4821") == "9SYAB1239G1000101"


def test_resolve_vehicle_description_matches_make_and_model() -> None:
    assert resolve_vehicle_description("my Harborline Skiff", "PY4821") == "9SYNP3452H2000501"


def test_resolve_vehicle_description_matches_year_make_and_model() -> None:
    assert (
        resolve_vehicle_description("the 2022 Example Motors Meridian", "PY4821")
        == "9SYAB1239G1000101"
    )


def test_resolve_vehicle_description_is_case_insensitive() -> None:
    assert resolve_vehicle_description("THE MERIDIAN", "PY4821") == "9SYAB1239G1000101"


def test_resolve_vehicle_description_matches_a_lowercase_policy_number() -> None:
    """`D207`/`OI125` follow-up, live root cause: `policy_number` is `AMAZON.AlphaNumeric`, and Lex
    lowercases it -- a real caller who said "PY4821" delivers `policy_number="py4821"` here, not the
    corpus's own canonical case. Confirmed live (`scripts/probe_d207_vin_delivery.py`'s own diagnostic
    run, 2026-09-01): every one of tonight's two escalating calls carried exactly this shape."""
    assert resolve_vehicle_description("the Meridian", "py4821") == "9SYAB1239G1000101"


def test_resolve_vehicle_description_resolves_a_mis_heard_leading_letter_policy_number() -> None:
    """`D207`/`OI125` follow-up, live evidence, contacts `07ec07e6`/`f5cd57b9` (19:05/19:06):
    ASR mis-hears policy_number's leading letter -- 'PY4821' arrived as 'uy4821'/'ty4821' -- and
    `vehicles_for_policy` returned zero vehicles for either, blocking everything downstream. Digits
    alone already identify PY4821 uniquely in this corpus."""
    assert resolve_vehicle_description("the Meridian", "uy4821") == "9SYAB1239G1000101"
    assert resolve_vehicle_description("the Meridian", "ty4821") == "9SYAB1239G1000101"


def test_resolve_vehicle_description_does_not_resolve_a_truncated_policy_number() -> None:
    """Same live evidence: 'py'/'py48' also arrived, truncated rather than mis-heard -- too few digits
    to be unambiguous (no real policy's digit string is a prefix match, only an exact one), so these
    stay unresolved rather than guessing."""
    assert resolve_vehicle_description("the Meridian", "py") is None
    assert resolve_vehicle_description("the Meridian", "py48") is None


def test_resolve_vehicle_description_returns_none_on_no_match() -> None:
    assert resolve_vehicle_description("my scooter", "PY4821") is None


def test_resolve_vehicle_description_returns_none_for_a_vin_not_on_this_policy() -> None:
    # 9SYCD4568G1000102 is real, but belongs to PY1103, not PY4821 -- a 17-char coincidence must not
    # pass through (this is D207's contact 33b36200-...'s own failure mode).
    assert resolve_vehicle_description("9SYCD4568G1000102", "PY4821") is None


def test_resolve_vehicle_description_matches_by_ordinal_position() -> None:
    """`D207`/`OI125` direction 3: telephony ASR cannot transcribe "Meridian" -- three live diagnostic
    rounds confirmed the model name never arrives. The prompt now reads the caller's own vehicles back
    (`file_auto_claim.py`'s `_vehicle_choices_prompt`, listed in policy order: Meridian first, Skiff
    second) and lets them answer by position instead."""
    assert resolve_vehicle_description("the first one", "PY4821") == "9SYAB1239G1000101"
    assert resolve_vehicle_description("the second one", "PY4821") == "9SYNP3452H2000501"
    assert resolve_vehicle_description("first", "PY4821") == "9SYAB1239G1000101"


def test_resolve_vehicle_description_matches_by_bare_year() -> None:
    """Year is the most ASR-robust signal (Marco): digits, not an uncommon proper noun. Only the digit
    form is parsed -- see the function's own docstring for why "twenty twenty two" is out of scope.
    """
    assert resolve_vehicle_description("2022", "PY4821") == "9SYAB1239G1000101"
    assert resolve_vehicle_description("the 2022 one", "PY4821") == "9SYAB1239G1000101"


def test_resolve_vehicle_description_matches_by_make_alone() -> None:
    assert resolve_vehicle_description("the Example Motors one", "PY4821") == "9SYAB1239G1000101"


def test_resolve_vehicle_description_does_not_parse_a_spelled_out_year() -> None:
    """`D207`/`OI125`'s original failure shape, still real: text with no model name, no ordinal, no
    digit year, and no make must return None rather than guess -- never silently resolve to the wrong
    vehicle just because a caller's answer sounded like it was trying to say something."""
    assert resolve_vehicle_description("twenty twenty two", "PY4821") is None


def test_resolve_vehicle_description_returns_none_when_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fnol_voice_agent.mcp.claims_server as claims_server
    from fnol_voice_agent.models import Vehicle

    same_model_twice = [
        Vehicle(
            vin="9SYAB1239G1000101",
            vin_check_digit_note="n/a",
            policy_number="PY4821",
            year=2022,
            make="Example Motors",
            model="Meridian",
            plate="KJH-4523",
            actual_cash_value_cad=22000,
        ),
        Vehicle(
            vin="9SYNP3452H2000501",
            vin_check_digit_note="n/a",
            policy_number="PY4821",
            year=2024,
            make="Harborline",
            model="Meridian",
            plate="TVN-2258",
            actual_cash_value_cad=27500,
        ),
    ]
    monkeypatch.setattr(claims_server, "_load_vehicles", lambda: same_model_twice)

    assert resolve_vehicle_description("the Meridian", "PY4821") is None


def test_importing_this_module_does_not_import_the_mcp_transport_package() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import fnol_voice_agent.mcp.claims_server; print('mcp' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"

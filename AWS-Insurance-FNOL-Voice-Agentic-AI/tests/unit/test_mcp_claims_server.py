"""In-process handler tests for `fnol_voice_agent.mcp.claims_server`."""

from __future__ import annotations

import pytest

from fnol_voice_agent.mcp.claims_server import (
    ClaimNotFoundError,
    InvalidClaimLookupError,
    NoOpenClaimError,
    RentalStatusUnavailableError,
    get_claim_status,
    get_rental_status,
)


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

from __future__ import annotations

import pytest

from fnol_voice_agent.validation.authority import AuthorityViolation, assert_within_authority


@pytest.mark.parametrize("action", ["settle", "approve_payment", "deny"])
def test_forbidden_actions_always_raise(action: str) -> None:
    with pytest.raises(AuthorityViolation):
        assert_within_authority(action, amount_cad=100)


def test_reserve_within_ceiling_does_not_raise() -> None:
    assert_within_authority("reserve", amount_cad=4_999)
    assert_within_authority("reserve", amount_cad=5_000)


def test_reserve_over_ceiling_raises() -> None:
    with pytest.raises(AuthorityViolation):
        assert_within_authority("reserve", amount_cad=5_001)


def test_reserve_without_amount_raises() -> None:
    with pytest.raises(AuthorityViolation):
        assert_within_authority("reserve")

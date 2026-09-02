"""In-process handler tests for `fnol_voice_agent.mcp.policy_server` -- exercised the same way Stage 6's
LangGraph nodes will call it: a plain function call, no MCP transport involved. The wire-protocol proof
that the *same* handler is also servable over stdio lives in `test_mcp_wire_protocol.py`.
"""

from __future__ import annotations

import pytest

from fnol_voice_agent.mcp.policy_server import (
    InvalidPolicyNumberError,
    PolicyNotFoundError,
    get_policyholder_elections,
)


def test_get_policyholder_elections_returns_the_real_record() -> None:
    result = get_policyholder_elections("PY4821")
    assert result.policy_number == "PY4821"
    assert result.first_name == "Priya"
    assert result.rental_endorsement.elected is True
    assert result.dcpd.opted_out is False


def test_get_policyholder_elections_covers_a_liability_only_policyholder() -> None:
    # PY1103 (Marc-Andre Tremblay) has no Section 7 selection -- the real corpus's liability-only case.
    result = get_policyholder_elections("PY1103")
    assert result.loss_or_damage_coverage.type is None
    assert result.rental_endorsement.elected is False


def test_get_policyholder_elections_accepts_a_lowercase_policy_number() -> None:
    """`D207`/`OI125` follow-up: `policy_number` is `AMAZON.AlphaNumeric` and Lex lowercases its
    interpretedValue (confirmed live) -- a real caller's "PY4821" arrives here as "py4821"."""
    result = get_policyholder_elections("py4821")
    assert result.policy_number == "PY4821"


def test_get_policyholder_elections_resolves_a_mis_heard_leading_letter() -> None:
    """`D207`/`OI125` follow-up, live evidence 2026-09-02: ASR mis-hears policy_number's leading letter
    ("PY4821" arrives as "uy4821"/"ty4821"). Digits alone already identify PY4821 uniquely in this
    corpus, so the lookup resolves instead of failing not-found."""
    result = get_policyholder_elections("uy4821")
    assert result.policy_number == "PY4821"


def test_get_policyholder_elections_raises_typed_error_on_unknown_policy() -> None:
    with pytest.raises(PolicyNotFoundError):
        get_policyholder_elections("PY9999")


def test_get_policyholder_elections_raises_typed_error_on_malformed_policy_number() -> None:
    with pytest.raises(InvalidPolicyNumberError):
        get_policyholder_elections("not-a-policy-number")


def test_importing_this_module_does_not_import_the_mcp_transport_package() -> None:
    """ADR-012's falsifiable property, checked directly: the handler module's own import graph must
    never pull in the `mcp` SDK. Run in a clean subprocess -- checking `sys.modules` in-process would
    be contaminated by `test_mcp_wire_protocol.py` (or pytest collection order generally) having already
    imported `mcp` for its own client-side use.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import fnol_voice_agent.mcp.policy_server; print('mcp' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert (
        result.stdout.strip() == "False"
    ), f"importing policy_server pulled in the mcp package; stdout={result.stdout!r} stderr={result.stderr!r}"

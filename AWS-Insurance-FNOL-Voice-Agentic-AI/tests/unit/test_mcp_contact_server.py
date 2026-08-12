"""In-process handler tests for `fnol_voice_agent.mcp.contact_server`.

Each test gets a fresh in-process store by resetting the module-level `_store` singleton -- otherwise
tests would observe each other's writes (the store is seeded once per process, per the module's own
docstring), which would make test order matter.
"""

from __future__ import annotations

import pytest

import fnol_voice_agent.mcp.contact_server as contact_server
from fnol_voice_agent.models import ContactField
from fnol_voice_agent.mcp.contact_server import (
    InvalidUpdateContactInfoError,
    PolicyNotFoundError,
    update_contact_info,
)


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    contact_server._store = None


def test_update_contact_info_writes_the_new_value_and_reports_the_old_one() -> None:
    result = update_contact_info("PY4821", ContactField.PHONE, "555-7777")
    assert result.previous_value == "555-0142"
    assert result.new_value == "555-7777"
    assert result.updated is True


def test_update_contact_info_mailing_address_maps_to_the_record_address_field() -> None:
    # ContactField.MAILING_ADDRESS's string value is "mailing_address"; Policyholder's own field is
    # "address" -- confirms the explicit mapping resolves this mismatch rather than KeyError-ing.
    result = update_contact_info("PY4821", ContactField.MAILING_ADDRESS, "1 New St, Toronto, ON")
    assert result.previous_value == "48 Birchwood Crescent, Mississauga, ON"
    assert result.new_value == "1 New St, Toronto, ON"


def test_update_contact_info_write_is_visible_on_a_subsequent_call_same_process() -> None:
    update_contact_info("PY4821", ContactField.EMAIL, "new@example.com")
    second = update_contact_info("PY4821", ContactField.EMAIL, "second@example.com")
    assert second.previous_value == "new@example.com"


def test_update_contact_info_unknown_policy_raises_typed_error() -> None:
    with pytest.raises(PolicyNotFoundError):
        update_contact_info("PY9999", ContactField.PHONE, "555-1234")


def test_update_contact_info_rejects_malformed_policy_number() -> None:
    with pytest.raises(InvalidUpdateContactInfoError):
        update_contact_info("not-a-policy", ContactField.PHONE, "555-1234")


def test_update_contact_info_rejects_blank_new_value() -> None:
    with pytest.raises(InvalidUpdateContactInfoError):
        update_contact_info("PY4821", ContactField.PHONE, "   ")


def test_update_contact_info_does_not_partially_apply_on_validation_failure() -> None:
    # A rejected write must leave the record completely untouched -- no partial write.
    before = update_contact_info(
        "PY4821", ContactField.PHONE, "555-0142"
    )  # no-op re-write, read-back
    assert before.previous_value == "555-0142"
    with pytest.raises(InvalidUpdateContactInfoError):
        update_contact_info("PY4821", ContactField.PHONE, "")
    after = update_contact_info("PY4821", ContactField.PHONE, "555-0142")
    assert after.previous_value == "555-0142"  # unchanged by the failed attempt in between


def test_importing_this_module_does_not_import_the_mcp_transport_package() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import fnol_voice_agent.mcp.contact_server; print('mcp' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"

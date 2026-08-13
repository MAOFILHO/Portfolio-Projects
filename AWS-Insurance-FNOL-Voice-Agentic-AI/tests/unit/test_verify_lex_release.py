"""Negative controls for the post-apply Lex verifier.

Phase 8 Stage 3. The verifier's job is to catch a deployment that disagrees with its own declaration, so
these tests are constructed the same way as `test_lexpoc_gate.py`'s and `test_check_flows.py`'s: build
one deployment that agrees, then mutate it into each specific disagreement.

The mutation that matters most is `test_a_stale_served_version_is_caught` — that is `RESULTS.md` §3.5.1
rule 2, and it is the exact failure `AWS::Lex::BotVersion` produces by default when the DRAFT it was
published from has not changed.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from scripts.verify_lex_release import verify

CODEHOOK_ARN = "arn:aws:lambda:us-west-2:759316130780:function:fnol-codehook"

OUTPUTS: dict[str, Any] = {
    "bot_id": "ABCDEFGHIJ",
    "bot_alias_id": "KLMNOPQRST",
    "bot_version": "3",
    "codehook_function_arn": CODEHOOK_ARN,
    "declared_policy_number_prompt": "Okay. What is your policy number? It starts with P Y.",
    "declared_dtmf_end_timeout_ms": 3000,
    "declared_obfuscated_slots": ["policy_number"],
}


def _slot_detail(
    name: str, *, prompt: str, timeout: int | None, obfuscated: bool
) -> dict[str, Any]:
    dtmf: dict[str, Any] = {}
    if timeout is not None:
        dtmf = {"dtmfSpecification": {"endTimeoutMs": timeout}}

    return {
        "slotName": name,
        "obfuscationSetting": {
            "obfuscationSettingType": "DefaultObfuscation" if obfuscated else "None"
        },
        "valueElicitationSetting": {
            "promptSpecification": {
                "messageGroupsList": [{"message": {"plainTextMessage": {"value": prompt}}}],
                "promptAttemptsSpecification": {
                    "Retry1": {"audioAndDTMFInputSpecification": dtmf},
                },
            }
        },
    }


class FakeLexModels:
    """A deployment that agrees with `OUTPUTS`, until a test reaches in and changes something."""

    def __init__(self) -> None:
        self.served_version = "3"
        self.alias_status = "Available"
        self.locale_status = "Built"
        self.locale_enabled = True
        self.code_hook_arn: str | None = CODEHOOK_ARN
        self.intents = {"FileAutoClaim": "INTENT0001"}
        self.slots: dict[str, dict[str, Any]] = {
            "policy_number": _slot_detail(
                "policy_number",
                prompt=OUTPUTS["declared_policy_number_prompt"],
                timeout=3000,
                obfuscated=True,
            ),
            "loss_datetime": _slot_detail(
                "loss_datetime", prompt="When did this happen?", timeout=None, obfuscated=False
            ),
        }
        self.page_sizes: list[int] = []

    # -- API surface -------------------------------------------------------------------------------

    def describe_bot_alias(self, **kwargs: Any) -> dict[str, Any]:
        locale: dict[str, Any] = {"enabled": self.locale_enabled}
        if self.code_hook_arn is not None:
            locale["codeHookSpecification"] = {
                "lambdaCodeHook": {
                    "lambdaARN": self.code_hook_arn,
                    "codeHookInterfaceVersion": "1.0",
                }
            }
        return {
            "botAliasId": kwargs["botAliasId"],
            "botVersion": self.served_version,
            "botAliasStatus": self.alias_status,
            "botAliasLocaleSettings": {"en_US": locale},
        }

    def describe_bot_locale(self, **kwargs: Any) -> dict[str, Any]:
        return {"botLocaleStatus": self.locale_status}

    def list_intents(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "intentSummaries": [
                {"intentName": name, "intentId": ident} for name, ident in self.intents.items()
            ]
        }

    def list_slots(self, **kwargs: Any) -> dict[str, Any]:
        self.page_sizes.append(kwargs.get("maxResults", 10))
        return {
            "slotSummaries": [
                {"slotName": name, "slotId": f"SLOT{i:06d}"} for i, name in enumerate(self.slots)
            ]
        }

    def describe_slot(self, **kwargs: Any) -> dict[str, Any]:
        index = int(kwargs["slotId"].removeprefix("SLOT"))
        return copy.deepcopy(list(self.slots.values())[index])


@pytest.fixture
def client() -> FakeLexModels:
    return FakeLexModels()


def test_a_matching_deployment_passes(client: FakeLexModels) -> None:
    assert verify(client, OUTPUTS) == []


# ---------------------------------------------------------------------------------------------------
# §3.5.1 rule 2 — the served version
# ---------------------------------------------------------------------------------------------------


def test_a_stale_served_version_is_caught(client: FakeLexModels) -> None:
    """The default behaviour of `AWS::Lex::BotVersion` when DRAFT has not changed: the apply reports a
    new version and the alias keeps serving the old one. Every artifact agrees; only this read does not.
    """
    client.served_version = "2"

    failures = verify(client, OUTPUTS)

    assert any("serves version '2'" in f for f in failures)


def test_an_alias_pointing_at_draft_is_caught(client: FakeLexModels) -> None:
    """DRAFT moves whenever the resource is edited, so a measurement against it is attributable to
    nothing. Same reasoning as the guardrail version pin in `stacks/guardrails/main.tf`."""
    client.served_version = "DRAFT"

    assert any("DRAFT" in f for f in verify(client, {**OUTPUTS, "bot_version": "DRAFT"}))


def test_an_unavailable_alias_is_caught(client: FakeLexModels) -> None:
    client.alias_status = "Creating"

    assert any("Available" in f for f in verify(client, OUTPUTS))


def test_an_unbuilt_locale_on_the_served_version_is_caught(client: FakeLexModels) -> None:
    """Stage 2 finding 4.1's shape, checked on the version rather than on DRAFT."""
    client.locale_status = "Building"

    assert any("Built" in f for f in verify(client, OUTPUTS))


# ---------------------------------------------------------------------------------------------------
# The code hook
# ---------------------------------------------------------------------------------------------------


def test_a_missing_code_hook_is_caught(client: FakeLexModels) -> None:
    """The most expensive silent failure available here: the bot runs its own slot filling, answers the
    phone, sounds fine, and no part of the agent — including L1 — ever executes."""
    client.code_hook_arn = None

    assert any("code hook" in f for f in verify(client, OUTPUTS))


def test_a_code_hook_pointing_at_a_different_function_is_caught(client: FakeLexModels) -> None:
    client.code_hook_arn = "arn:aws:lambda:us-west-2:759316130780:function:some-other-function"

    assert verify(client, OUTPUTS) != []


def test_a_disabled_locale_on_the_alias_is_caught(client: FakeLexModels) -> None:
    """Stage 2 finding 4.2 — the bot builds cleanly, every control-plane read reports health, and it
    cannot be spoken to."""
    client.locale_enabled = False

    assert any("enabled" in f for f in verify(client, OUTPUTS))


# ---------------------------------------------------------------------------------------------------
# Declared values, on the served version
# ---------------------------------------------------------------------------------------------------


def test_a_drifted_prompt_is_caught(client: FakeLexModels) -> None:
    """Provider issue #42147's signature: the definition says one thing, the deployment serves another."""
    client.slots["policy_number"]["valueElicitationSetting"]["promptSpecification"][
        "messageGroupsList"
    ][0]["message"]["plainTextMessage"]["value"] = "What's your policy number?"

    assert any("prompt served" in f for f in verify(client, OUTPUTS))


def test_a_drifted_dtmf_timeout_is_caught(client: FakeLexModels) -> None:
    """#36845's family — a nested integer rather than a string, tested separately because a mechanism
    could plausibly get one right and the other wrong."""
    client.slots["policy_number"]["valueElicitationSetting"]["promptSpecification"][
        "promptAttemptsSpecification"
    ]["Retry1"]["audioAndDTMFInputSpecification"]["dtmfSpecification"]["endTimeoutMs"] = 5000

    assert any("endTimeoutMs" in f for f in verify(client, OUTPUTS))


def test_an_absent_dtmf_specification_is_not_read_as_the_declared_value(
    client: FakeLexModels,
) -> None:
    """`_dtmf_end_timeout` returns `None` rather than a default. With a default, "the whole DTMF block
    vanished" and "the timeout is 3000" would produce the same answer — and the first is the one that
    silently removes the keypad from a digit-only slot."""
    client.slots["policy_number"]["valueElicitationSetting"]["promptSpecification"][
        "promptAttemptsSpecification"
    ]["Retry1"]["audioAndDTMFInputSpecification"] = {}

    assert any("endTimeoutMs" in f for f in verify(client, OUTPUTS))


# ---------------------------------------------------------------------------------------------------
# `D70`
# ---------------------------------------------------------------------------------------------------


def test_a_slot_that_lost_its_obfuscation_is_caught(client: FakeLexModels) -> None:
    client.slots["policy_number"]["obfuscationSetting"]["obfuscationSettingType"] = "None"

    assert any("Declared but not served" in f for f in verify(client, OUTPUTS))


def test_an_undeclared_obfuscated_slot_is_caught(client: FakeLexModels) -> None:
    """Both directions. An unexpected extra is a value someone hid without deciding it in the schema —
    and `loss_datetime` is the specific slot `DOMAIN-ARTIFACTS.md` says must not be redacted."""
    client.slots["loss_datetime"]["obfuscationSetting"][
        "obfuscationSettingType"
    ] = "DefaultObfuscation"

    failures = verify(client, OUTPUTS)

    assert any("loss_datetime" in f for f in failures)


# ---------------------------------------------------------------------------------------------------
# The verifier's own reach
# ---------------------------------------------------------------------------------------------------


def test_slots_are_requested_a_page_at_a_time_larger_than_ten(client: FakeLexModels) -> None:
    """Stage 2 finding 4.4: `ListSlots` defaults to 10 and `FileAutoClaim` has 11. An unpaginated read
    drops `driver_name` and reports a clean, wrong answer."""
    verify(client, OUTPUTS)

    assert client.page_sizes
    assert all(size > 11 for size in client.page_sizes)

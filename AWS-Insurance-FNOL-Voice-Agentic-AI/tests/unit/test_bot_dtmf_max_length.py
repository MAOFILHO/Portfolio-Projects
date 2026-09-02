"""`bot.yaml.tftpl`'s DTMF `MaxLength` values, checked against the real identifier each slot elicits.

Live evidence, 2026-09-02 (contacts `07ec07e6`/`f5cd57b9`, 19:05/19:06): callers cannot get their own
policy number past Lex at all -- `policy_number='py'`, `policy_number='py48'` arrive truncated.
`FileAutoClaim.policy_number`'s `Retry1`/`Retry2` `DTMFSpecification.MaxLength` is 4; a PY4821-shaped
identifier needs 6 keypad presses (2 letters via T9 + 4 digits), so keypad entry was cut short 2 presses
before the caller finished dialing. `police_report_number` (11 digit presses) and `claim_number` (13:
3 letters + 10 digits) already match their own identifiers' keypad-press count -- asserted here too, as
a regression guard, not because either was in question.

DEFERRED, Marco-decided 2026-09-02: the fix for the first test below is NOT applied. Editing
`bot.yaml.tftpl` at all forces a bot rebuild -- CloudFormation stack replacement -> new Lex build ->
Connect contact-flow and phone-number-association replacement on the live demo line -- the exact blast
radius a comment-only edit to this same file was reverted to avoid one day earlier. Fix 2 (digits-only
policy-number resolution, `validation/identifiers.py`) may make DTMF entry unnecessary here entirely, so
this MaxLength fix waits for that question to be settled, not for lack of a diagnosis -- see
`PROJECT_STATE.md`'s deferred-findings table. Marked `xfail`, not deleted or skipped, so the finding
stays visible in every test run rather than silently disappearing from the suite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_BOT_TFTPL = Path("infra/terraform/stacks/main/bot.yaml.tftpl")


# Same technique as `scripts/verify_slot_legality_mapping.py`'s own `_CfnSafeLoader` -- this file is
# CloudFormation YAML, and plain `yaml.safe_load` has no constructor for CloudFormation's short-form
# intrinsic tags (`!Ref`, `!GetAtt`). Resolved to an inert placeholder, never evaluated: this test only
# reads `DTMFSpecification.MaxLength` values, never a `!Ref`/`!GetAtt` value. Not imported from that
# script (its own docstring calls itself standalone, scoped to the legal-slot-name mapping) -- duplicated
# here at ~10 lines rather than widening that module's stated scope.
class _CfnSafeLoader(yaml.SafeLoader):
    pass


_CfnSafeLoader.add_multi_constructor(  # type: ignore[no-untyped-call]
    "!", lambda _loader, tag_suffix, _node: f"<{tag_suffix} unresolved>"
)


def _dtmf_max_lengths(intent_name: str, slot_name: str) -> list[int]:
    """Every `DTMFSpecification.MaxLength` declared for `slot_name` under `intent_name`, in
    `PromptAttemptsSpecification` retry order (`Retry1` then `Retry2`) -- empty if the slot has no
    `PromptAttemptsSpecification` at all, meaning DTMF isn't offered on it, a different situation from a
    wrong length."""
    document: dict[str, Any] = yaml.load(_BOT_TFTPL.read_text(), Loader=_CfnSafeLoader)
    intents = document["Resources"]["FnolBot"]["Properties"]["BotLocales"][0]["Intents"]
    intent = next(i for i in intents if i["Name"] == intent_name)
    slot = next(s for s in intent["Slots"] if s["Name"] == slot_name)
    attempts = slot["ValueElicitationSetting"]["PromptSpecification"].get(
        "PromptAttemptsSpecification", {}
    )
    lengths = []
    for retry in ("Retry1", "Retry2"):
        dtmf = (
            attempts.get(retry, {})
            .get("AudioAndDTMFInputSpecification", {})
            .get("DTMFSpecification")
        )
        if dtmf is not None:
            lengths.append(dtmf["MaxLength"])
    return lengths


@pytest.mark.xfail(
    reason=(
        "Deferred, Marco-decided 2026-09-02: fixing bot.yaml.tftpl's policy_number MaxLength forces a "
        "bot rebuild (Connect contact-flow + phone-number-association replacement on the live demo "
        "line), the same blast radius a comment-only edit to this file was reverted to avoid one day "
        "earlier. Waits on whether Fix 2's digits-only resolution makes DTMF entry unnecessary here at "
        "all -- see PROJECT_STATE.md's deferred-findings table."
    ),
    strict=True,
)
def test_policy_number_dtmf_max_length_fits_the_real_six_press_identifier() -> None:
    """PY4821-shaped: P, Y (T9 letter presses) + 4, 8, 2, 1 (digit presses) = 6 keypad presses."""
    assert _dtmf_max_lengths("FileAutoClaim", "policy_number") == [6, 6]


def test_police_report_number_dtmf_max_length_is_unchanged() -> None:
    """Regression guard, not part of this fix -- `####-####-###` is 11 digit presses, and 11 was
    already correct."""
    assert _dtmf_max_lengths("FileAutoClaim", "police_report_number") == [11, 11]


def test_claim_number_dtmf_max_length_is_unchanged() -> None:
    """Regression guard, not part of this fix -- `CLM-YYMM-NNNNN-C` is 3 letter presses (CLM) + 10
    digit presses = 13, and 13 was already correct."""
    assert _dtmf_max_lengths("CheckClaimStatus", "claim_number") == [13, 13]

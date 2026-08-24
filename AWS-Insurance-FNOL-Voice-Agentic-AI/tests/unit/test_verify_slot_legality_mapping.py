"""`D162`/`OI80` fix, exit-criteria table row 3 (`PROJECT_STATE.md`) -- the derived `bot.yaml.tftpl`
legal-slot-name mapping. Standalone here: nothing in this file touches `api/lex_codehook.py`. Rows 1/2
(the `_elicit_slot` guard itself) consume `legal_slots_by_intent` in a later cycle; this file only
proves the parser itself is correct and fails loudly, not silently, on a broken source.

Two properties under test, matching the exit-criteria table's own wording for this row:
  (a) the parser extracts the correct `{intent: {slot names}}` map for every intent that declares
      slots -- asserted against slot names read from `bot.yaml.tftpl` BY HAND, for this test only, not
      derived from the parser itself (a tautological assertion would prove nothing).
  (b) a malformed or missing `Slots:` block raises `SlotLegalityParseError` rather than silently
      returning an empty set for that intent -- an empty set would make every future legality check
      against that intent vacuously pass, the exact `D126` shape (a check that exists, finds nothing,
      and reads as clean) this project has already filed once.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_slot_legality_mapping import (
    SlotLegalityDriftError,
    SlotLegalityParseError,
    assert_matches_src_constant,
    legal_slots_by_intent,
)

_BOT_TFTPL = Path("infra/terraform/stacks/main/bot.yaml.tftpl")


def test_extracts_the_slot_map_for_every_intent_that_declares_slots() -> None:
    text = _BOT_TFTPL.read_text()

    result = legal_slots_by_intent(text)

    # Hand-transcribed directly from bot.yaml.tftpl (infra/terraform/stacks/main/bot.yaml.tftpl:187-805),
    # for this test only -- an independent source of truth, not the parser's own output and not
    # _elicit_slot's (not-yet-written) mapping.
    expected = {
        "FileAutoClaim": frozenset(
            {
                "injuries_present",
                "policy_number",
                "insured_vehicle_vin",
                "loss_datetime",
                "loss_location",
                "loss_type",
                "damage_description",
                "other_party_involved",
                "police_report_filed",
                "police_report_number",
                "driver_name",
                "confirm_file_claim",
            }
        ),
        "CheckClaimStatus": frozenset({"claim_number"}),
        "CoverageQuestion": frozenset({"coverage_topic"}),
        "RentalTowingEntitlement": frozenset({"entitlement_type", "claim_number"}),
        "UpdateContactInfo": frozenset(
            {"policy_number", "field", "new_value", "confirm_update_contact_info"}
        ),
    }
    assert result == expected


def test_a_zero_slot_intent_is_absent_from_the_map_not_present_with_an_empty_set() -> None:
    """`InjuryEscalation`/`FallbackIntent` declare no `Slots:` key at all -- legitimately zero-slot, and
    distinct from the malformed case below, which DOES have a `Slots:` key. Conflating the two would
    make the malformed-block guard (below) untestable: an intent with no key and an intent with a broken
    key would both come out as "absent," and the raise this row exists to prove would have nothing to
    fire on.
    """
    result = legal_slots_by_intent(_BOT_TFTPL.read_text())

    assert "InjuryEscalation" not in result
    assert "FallbackIntent" not in result


def test_an_empty_slots_list_raises_rather_than_returning_an_empty_set() -> None:
    template = """
Resources:
  FnolBot:
    Type: AWS::Lex::Bot
    Properties:
      BotLocales:
        - LocaleId: en_US
          Intents:
            - Name: "FileAutoClaim"
              Slots: []
"""
    with pytest.raises(SlotLegalityParseError):
        legal_slots_by_intent(template)


def test_a_non_list_slots_block_raises() -> None:
    template = """
Resources:
  FnolBot:
    Type: AWS::Lex::Bot
    Properties:
      BotLocales:
        - LocaleId: en_US
          Intents:
            - Name: "CheckClaimStatus"
              Slots: "not a list"
"""
    with pytest.raises(SlotLegalityParseError):
        legal_slots_by_intent(template)


def test_a_slot_entry_missing_its_own_name_raises() -> None:
    template = """
Resources:
  FnolBot:
    Type: AWS::Lex::Bot
    Properties:
      BotLocales:
        - LocaleId: en_US
          Intents:
            - Name: "CoverageQuestion"
              Slots:
                - Description: "no Name key at all"
"""
    with pytest.raises(SlotLegalityParseError):
        legal_slots_by_intent(template)


def test_a_missing_intents_block_raises_rather_than_returning_an_empty_map() -> None:
    template = """
Resources:
  FnolBot:
    Type: AWS::Lex::Bot
    Properties:
      BotLocales:
        - LocaleId: en_US
"""
    with pytest.raises(SlotLegalityParseError):
        legal_slots_by_intent(template)


def test_cloudformation_short_form_tags_outside_intents_do_not_break_parsing() -> None:
    """The real file's own blocker for plain `yaml.safe_load` -- `!Ref`/`!GetAtt` elsewhere in the
    document (bot.yaml.tftpl:66-67,88,849,852) -- reproduced in miniature, structurally separate from
    the `Intents:` block this parser reads."""
    template = """
Resources:
  FnolBot:
    Type: AWS::Lex::Bot
    Properties:
      Name: !Ref BotName
      BotLocales:
        - LocaleId: en_US
          Intents:
            - Name: "CheckClaimStatus"
              Slots:
                - Name: "claim_number"
Outputs:
  BotId:
    Value: !Ref FnolBot
  BotArn:
    Value: !GetAtt FnolBot.Arn
"""
    result = legal_slots_by_intent(template)

    assert result == {"CheckClaimStatus": frozenset({"claim_number"})}


# ---------------------------------------------------------------------------------------------------
# `D162`/`OI80` criterion 3's equality assert -- `assert_matches_src_constant` compares the
# tftpl-derived mapping above against `_LEGAL_SLOTS_BY_INTENT` (`src/fnol_voice_agent/api/
# lex_codehook.py`, rows 1/2's own hand-maintained constant). Equality, not subset: a subset assert
# over a partial constant would pass vacuously -- the exact `D126` shape `legal_slots_by_intent`'s own
# raise-on-malformed already guards against one level up. RED-first, standalone: this test exercises
# the comparison function directly, on two small hand-built mappings, not the real files -- the real
# `bot.yaml.tftpl` vs. the real `_LEGAL_SLOTS_BY_INTENT` is a separate, standalone script run (this
# row's own step 3), not a unit test assertion.
# ---------------------------------------------------------------------------------------------------


def test_assert_matches_src_constant_raises_on_a_mismatched_mapping() -> None:
    """One missing slot name (`"claim_number"`, declared by the tftpl-shaped mapping but absent from
    the src-constant-shaped one) and one extra slot name (`"claim_id"`, present in the src-constant-
    shaped mapping but never declared by the tftpl-shaped one) -- both directions of drift, in the same
    intent, so this proves the check catches either, not only one.
    """
    tftpl_mapping = {
        "CheckClaimStatus": frozenset({"claim_number"}),
        "CoverageQuestion": frozenset({"coverage_topic"}),
    }
    mismatched_src_constant = {
        "CheckClaimStatus": frozenset({"claim_id"}),  # missing "claim_number", extra "claim_id"
        "CoverageQuestion": frozenset({"coverage_topic"}),
    }

    with pytest.raises(SlotLegalityDriftError):
        assert_matches_src_constant(tftpl_mapping, mismatched_src_constant)

from __future__ import annotations

import json
import re
from pathlib import Path

from fnol_voice_agent.guardrails.pii import PHONE_RE, redact_for_transcript

DATA_DIR = Path(__file__).resolve().parents[2] / "src" / "fnol_voice_agent" / "data" / "synthetic"


def _first_policyholder() -> dict[str, object]:
    data = json.loads((DATA_DIR / "policyholders" / "policyholders.json").read_text())
    holder: dict[str, object] = data["policyholders"][0]
    assert holder["policy_number"] == "PY4821"  # pin the fixture this test suite depends on
    return holder


def _first_claim() -> dict[str, object]:
    data = json.loads((DATA_DIR / "claims" / "claims.json").read_text())
    claim: dict[str, object] = data["claims"][0]
    assert claim["claim_number"] == "CLM-2608-00042-4"
    return claim


def _first_vehicle() -> dict[str, object]:
    data = json.loads((DATA_DIR / "vehicles" / "vehicles.json").read_text())
    vehicle: dict[str, object] = data["vehicles"][0]
    assert vehicle["plate"] == "KJH-4523"
    return vehicle


# --- Individual detector categories, each against a real-shaped synthetic value ----------------------------


def test_phone_redacted() -> None:
    holder = _first_policyholder()
    phone = str(holder["phone"])
    text = f"You can reach me at {phone} if you need anything."
    redacted = redact_for_transcript(text)
    assert phone not in redacted
    assert "[REDACTED:PHONE]" in redacted


def test_real_shaped_non_555_phone_redacted() -> None:
    """`D124`/`OI46`: the fixture above (`holder['phone']`) is this project's own synthetic `555`-exchange
    convention (`docs/phase0`), which `PHONE_RE` was scoped to for its entire history until this test was
    written -- a real caller's real phone number was never redacted, in any layer, ever. This is the
    executable proof, not the grep-derived argument for it. Reuses `redteam/readback_probe.py`'s own
    real-shaped fixture (`_PII_PHONE`, line 80) rather than minting a fourth phone constant."""
    real_shaped_phone = "416-987-1547"  # readback_probe.py's _PII_PHONE, reused
    text = f"You can reach me at {real_shaped_phone} if you need anything."
    redacted = redact_for_transcript(text)
    assert real_shaped_phone not in redacted
    assert "[REDACTED:PHONE]" in redacted


def test_phone_re_fix_is_a_strict_superset_of_the_old_555_only_pattern() -> None:
    """`D124`'s fix (gating both digit groups' first digit to `2-9`, not the old literal `555`) must not
    silently stop redacting anything the old pattern caught. Verified explicitly against every 555-shaped
    phone value this repo's own fixtures actually use -- not reasoned from "555 is in \\d{3} so it falls out
    for free." The old pattern is kept here, inert, as the comparison baseline; it is not imported from
    anywhere else in the codebase."""
    old_555_only_pattern = re.compile(r"\b(?:\d{3}[-.\s])?555[-.\s]?\d{4}\b")

    # Every 555-shaped value this repo's own fixtures use, swept from data/synthetic, tests/, and pii.py's
    # own docstring example -- not invented for this test.
    fixture_values = (
        "555-0142",  # policyholders.json (PY4821)
        "555-0187",
        "555-0219",
        "555-0334",
        "555-0456",
        "555-0578",  # policyholders.json, remaining five records
        "555-0199",  # evals/golden/claim_status_and_contact.yaml
        "555-0177",
        "555-0143",
        "555-0188",
        "555-0189",  # evals/golden/claim_status_and_contact.yaml, remaining turns
        "555-4242",  # tests/unit/test_mcp_wire_protocol.py
        "555-7777",  # tests/unit/test_mcp_contact_server.py
        "555-1234",  # tests/unit/test_mcp_contact_server.py
        "5550142",  # evals/golden/file_auto_claim.yaml -- no separator at all
        "416-555-0142",  # pii.py's own docstring worked example -- area-code-prefixed form
    )

    for value in fixture_values:
        assert old_555_only_pattern.search(
            value
        ), f"{value!r} is not actually 555-shaped -- fixture list is wrong, not the regex"
        assert PHONE_RE.search(
            value
        ), f"{value!r} matched the old pattern but not the fixed one -- regression"


def test_phone_re_does_not_match_dates_ids_and_claim_numbers() -> None:
    """`D124`'s fix reason, recorded as false-positive bounding, not NANP fidelity: a loose `\\d{3}` exchange
    with an optional area code and optional separators would match digit runs inside claim numbers,
    timestamps, and IDs -- and `REDACTION_PASSES` ordering only protects patterns that run *before* PHONE
    (`POLICY_NUMBER`/`CLAIM_NUMBER`/`VIN`/`PLATE`/`DRIVERS_LICENCE`/`POLICE_REPORT_NUMBER`). `DATE_TIME`,
    `LOCATION`, and free-text amounts run *after* PHONE and get no such protection -- a false positive there
    is not cosmetic: `redact_for_transcript` feeds caller-facing paths, and a spoken `[REDACTED:PHONE]`
    stitched into the middle of a date or an address is exactly the failure the guardrail runbook already
    flagged for OUTPUT-side masking. Every value below is a real shape this project's own code or fixtures
    actually produce -- not a hypothetical."""
    non_phone_values = (
        "2026-08-11T09:00:00-04:00",  # loss_datetime slot value (redteam/readback_probe.py)
        "2026-07-27",  # ISO date, DATE_TIME_RE's own worked example
        "2026-0727-014",  # claims.json's police_report_number shape
        "CLM-2608-00042-4",  # claim_number shape
        "PY4821",  # policy_number shape
        "9SYAB1239G1000101",  # VIN shape
        "8f14e45f-ceea-4b57-9b5e-3c6c6c6c6c6c",  # contact_id UUID, verify_log_redaction.py's negative case
        "Highway 403 near Oakville, ON",  # claims.json's own loss_location
        "48 Birchwood Crescent, Mississauga, ON",  # ADDRESS_RE's own worked example
        "amount_remaining_cad=400",
    )
    for value in non_phone_values:
        assert not PHONE_RE.search(value), f"{value!r} false-positive matched as a phone number: {PHONE_RE.search(value).group()!r}"  # type: ignore[union-attr]


# --- `/code-review` follow-up: common real written forms `D124`'s own fix left uncovered --------------------
#
# Four tests, one per shape, per this project's "one seam, one test" TDD discipline -- each independently
# reports RED/GREEN rather than one loop stopping at its first failure. Two of these were genuinely broken
# by D124's fix (no separator at all; a parenthesized area code); two already worked but had never been
# exercised by any test in this file until now.


def test_phone_re_matches_ten_digits_with_no_separator_at_all() -> None:
    """Was a total miss before this fix: `PHONE_RE`'s area-code group required a mandatory separator
    character, so a fully contiguous 10-digit number (area code run straight into the rest -- a plausible
    ASR/transcript rendering) matched NOTHING, not even partially. Directly contradicted the pattern's own
    comment, which claimed "no separator at all between groups" was supported -- true for the 7-digit
    no-area-code case, false for this one."""
    text = "You can reach me at 4169871547 if you need anything."
    redacted = redact_for_transcript(text)
    assert "416" not in redacted, f"area code leaked into {redacted!r}"
    assert "987" not in redacted, f"exchange leaked into {redacted!r}"
    assert "1547" not in redacted, f"subscriber number leaked into {redacted!r}"
    assert "[REDACTED:PHONE]" in redacted, f"never redacted at all: {redacted!r}"


def test_phone_re_matches_parenthesized_area_code() -> None:
    """Was a partial leak before this fix: `"(416) 987-1547"` only redacted `"987-1547"` -- the mandatory
    separator after the area code meant the `(416)` branch never matched at that starting position, and the
    regex engine fell back to matching starting at `"987"` instead, leaving the real area code `"416"` in
    plaintext. Parenthesized area codes are a common written form; decided to fix rather than accept as a
    documented gap (`docs/RESULTS.md` §95)."""
    text = "You can reach me at (416) 987-1547 if you need anything."
    redacted = redact_for_transcript(text)
    assert "416" not in redacted, f"area code leaked into {redacted!r}"
    assert "987" not in redacted, f"exchange leaked into {redacted!r}"
    assert "1547" not in redacted, f"subscriber number leaked into {redacted!r}"
    assert "[REDACTED:PHONE]" in redacted, f"never redacted at all: {redacted!r}"


def test_phone_re_matches_dot_separated() -> None:
    """Already worked before this fix -- `PHONE_RE`'s own comment claimed dot separators were supported,
    but nothing in this file ever exercised `"416.987.1547"` to confirm it. Added for coverage, not because
    it was broken."""
    text = "You can reach me at 416.987.1547 if you need anything."
    redacted = redact_for_transcript(text)
    assert "416" not in redacted, f"area code leaked into {redacted!r}"
    assert "987" not in redacted, f"exchange leaked into {redacted!r}"
    assert "1547" not in redacted, f"subscriber number leaked into {redacted!r}"
    assert "[REDACTED:PHONE]" in redacted, f"never redacted at all: {redacted!r}"


def test_phone_re_matches_space_separated() -> None:
    """Already worked before this fix -- same reasoning as the dot-separated case above, for
    `"416 987 1547"`."""
    text = "You can reach me at 416 987 1547 if you need anything."
    redacted = redact_for_transcript(text)
    assert "416" not in redacted, f"area code leaked into {redacted!r}"
    assert "987" not in redacted, f"exchange leaked into {redacted!r}"
    assert "1547" not in redacted, f"subscriber number leaked into {redacted!r}"
    assert "[REDACTED:PHONE]" in redacted, f"never redacted at all: {redacted!r}"


def test_email_redacted() -> None:
    holder = _first_policyholder()
    email = str(holder["email"])
    text = f"My email on file is {email}, please use that."
    redacted = redact_for_transcript(text)
    assert email not in redacted
    assert "[REDACTED:EMAIL]" in redacted


def test_address_redacted() -> None:
    holder = _first_policyholder()
    address = str(holder["address"])
    text = f"I live at {address}, that's where the car is parked."
    redacted = redact_for_transcript(text)
    assert address not in redacted
    assert "[REDACTED:ADDRESS]" in redacted


def test_french_rue_address_redacted() -> None:
    # PY1103's own synthetic address -- the French "Rue <name>" construction, distinct code path from
    # the English-suffix branch of ADDRESS_RE exercised by test_address_redacted.
    text = "My address is 12 Rue des Erables, Ottawa, ON."
    redacted = redact_for_transcript(text)
    assert "Rue des Erables" not in redacted
    assert "[REDACTED:ADDRESS]" in redacted


def test_policy_number_redacted() -> None:
    holder = _first_policyholder()
    policy_number = str(holder["policy_number"])
    text = f"It's regarding policy {policy_number}, filed last week."
    redacted = redact_for_transcript(text)
    assert policy_number not in redacted
    assert "[REDACTED:POLICY_NUMBER]" in redacted


def test_claim_number_redacted() -> None:
    claim = _first_claim()
    claim_number = str(claim["claim_number"])
    text = f"I'm calling to check on claim {claim_number}."
    redacted = redact_for_transcript(text)
    assert claim_number not in redacted
    assert "[REDACTED:CLAIM_NUMBER]" in redacted


def test_vin_redacted() -> None:
    claim = _first_claim()
    vin = str(claim["vin"])
    text = f"The VIN is {vin}, confirmed against the title."
    redacted = redact_for_transcript(text)
    assert vin not in redacted
    assert "[REDACTED:VIN]" in redacted


def test_plate_redacted() -> None:
    vehicle = _first_vehicle()
    plate = str(vehicle["plate"])
    text = f"Licence plate on the vehicle is {plate}."
    redacted = redact_for_transcript(text)
    assert plate not in redacted
    assert "[REDACTED:PLATE]" in redacted


def test_drivers_licence_redacted() -> None:
    holder = _first_policyholder()
    licence = str(holder["drivers_license"])
    text = f"My driver's licence number is {licence}."
    redacted = redact_for_transcript(text)
    assert licence not in redacted
    assert "[REDACTED:DRIVERS_LICENCE]" in redacted


def test_police_report_number_redacted() -> None:
    claim = _first_claim()
    report_number = str(claim["police_report_number"])
    text = f"The officer's report number is {report_number}."
    redacted = redact_for_transcript(text)
    assert report_number not in redacted
    assert "[REDACTED:POLICE_REPORT_NUMBER]" in redacted


def test_iso_date_redacted() -> None:
    text = "The loss occurred on 2026-07-27, in the morning."
    redacted = redact_for_transcript(text)
    assert "2026-07-27" not in redacted
    assert "[REDACTED:DATE_TIME]" in redacted


def test_relative_day_and_clock_time_redacted() -> None:
    text = "It happened yesterday around 5:30 in the afternoon."
    redacted = redact_for_transcript(text)
    assert "yesterday" not in redacted
    assert "5:30" not in redacted
    assert (
        redacted.count("[REDACTED:DATE_TIME]") == 2
    )  # "yesterday" and "5:30" each redacted separately


def test_highway_location_redacted() -> None:
    # PY4821's own flagship claim's real loss_location.
    claim = _first_claim()
    location = str(claim["loss_location"])
    assert location == "Highway 403 near Oakville, ON"
    text = f"The collision happened on {location}."
    redacted = redact_for_transcript(text)
    assert "Highway 403" not in redacted
    assert "[REDACTED:LOCATION]" in redacted


def test_street_intersection_location_redacted() -> None:
    text = "It happened at the corner of King Street and Main Street."
    redacted = redact_for_transcript(text)
    assert "King Street and Main Street" not in redacted
    assert "[REDACTED:LOCATION]" in redacted


# --- Combined, multi-sentence, multi-category transcript ---------------------------------------------------


def test_combined_transcript_catches_every_category_not_just_the_first_match() -> None:
    holder = _first_policyholder()
    claim = _first_claim()
    vehicle = _first_vehicle()

    transcript_turn = (
        f"Hi, I'm calling about policy {holder['policy_number']}. "
        f"My phone is {holder['phone']} and my email is {holder['email']}. "
        f"The accident happened yesterday around 5:30 near {claim['loss_location']}. "
        f"My VIN is {claim['vin']} and the plate is {vehicle['plate']}. "
        f"Police report number is {claim['police_report_number']}, "
        f"and my claim number is {claim['claim_number']}. "
        f"I live at {holder['address']}. "
        f"My driver's licence is {holder['drivers_license']}."
    )

    redacted = redact_for_transcript(transcript_turn)

    # None of the raw sensitive values survive.
    for raw_value in (
        holder["policy_number"],
        holder["phone"],
        holder["email"],
        claim["vin"],
        vehicle["plate"],
        claim["police_report_number"],
        claim["claim_number"],
        holder["address"],
        holder["drivers_license"],
    ):
        assert str(raw_value) not in redacted, f"{raw_value!r} leaked into the redacted transcript"

    # Every category actually fired at least once -- proves this isn't stopping at the first match.
    for expected_type in (
        "POLICY_NUMBER",
        "PHONE",
        "EMAIL",
        "DATE_TIME",
        "LOCATION",
        "VIN",
        "PLATE",
        "POLICE_REPORT_NUMBER",
        "CLAIM_NUMBER",
        "ADDRESS",
        "DRIVERS_LICENCE",
    ):
        assert f"[REDACTED:{expected_type}]" in redacted, f"{expected_type} never fired"


def test_documented_limitation_names_are_not_redacted_by_this_module() -> None:
    """Honesty check, not a desired behavior: per the module docstring, this deterministic module does
    not attempt name detection at all (that's Bedrock Guardrails' job, per ADR-011's Layer 1 design). A
    caller's name passing through unredacted here is expected, not a bug -- this test exists so a future
    change that silently starts stripping names (or a reader who assumes it already does) has something
    concrete to check against."""
    holder = _first_policyholder()
    text = f"My name is {holder['first_name']} {holder['last_name']}, calling about my claim."
    redacted = redact_for_transcript(text)
    assert str(holder["first_name"]) in redacted
    assert str(holder["last_name"]) in redacted


# --- No over-redaction ---------------------------------------------------------------------------------


def test_clean_text_with_none_of_the_categories_passes_through_unchanged() -> None:
    text = "The weather is nice and my car is blue. Thanks for calling Example Mutual."
    assert redact_for_transcript(text) == text


def test_empty_string_passes_through_unchanged() -> None:
    assert redact_for_transcript("") == ""

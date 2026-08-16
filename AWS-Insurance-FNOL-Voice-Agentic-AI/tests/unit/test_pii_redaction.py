from __future__ import annotations

import json
from pathlib import Path

from fnol_voice_agent.guardrails.pii import redact_for_transcript

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

"""Unit tests for JSONL training-record validation (app.schemas.training)."""

from __future__ import annotations

import json

from app.schemas.training import validate_jsonl_text

VALID_ROW = json.dumps(
    {
        "messages": [
            {"role": "system", "content": "You are a travel assistant."},
            {"role": "user", "content": "Where should I stay in Rome?"},
            {"role": "assistant", "content": "Location, location, location!"},
        ]
    }
)


def test_all_valid_rows_pass():
    text = "\n".join([VALID_ROW] * 3)
    report = validate_jsonl_text(text, "sample.jsonl")
    assert report.is_valid
    assert report.valid_rows == 3
    assert report.total_lines == 3
    assert report.errors == []
    assert report.has_consistent_system_prompt


def test_malformed_json_is_collected_not_raised():
    text = VALID_ROW + "\nnot json at all\n" + VALID_ROW
    report = validate_jsonl_text(text, "sample.jsonl")
    assert not report.is_valid
    assert report.valid_rows == 2
    assert report.total_lines == 3
    assert len(report.errors) == 1
    assert report.errors[0].line_number == 2


def test_wrong_message_order_is_rejected():
    bad = json.dumps(
        {
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "system", "content": "sys"},
                {"role": "assistant", "content": "hello"},
            ]
        }
    )
    report = validate_jsonl_text(bad, "sample.jsonl")
    assert not report.is_valid
    assert report.valid_rows == 0
    assert len(report.errors) == 1


def test_wrong_message_count_is_rejected():
    bad = json.dumps({"messages": [{"role": "system", "content": "sys"}]})
    report = validate_jsonl_text(bad, "sample.jsonl")
    assert not report.is_valid


def test_inconsistent_system_prompt_flagged_but_still_valid():
    row_a = VALID_ROW
    row_b = json.dumps(
        {
            "messages": [
                {"role": "system", "content": "A different system prompt."},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ]
        }
    )
    report = validate_jsonl_text(f"{row_a}\n{row_b}", "sample.jsonl")
    assert report.is_valid  # both rows are individually well-formed
    assert not report.has_consistent_system_prompt
    assert report.distinct_system_prompts == 2


def test_empty_lines_are_skipped():
    text = f"{VALID_ROW}\n\n\n{VALID_ROW}\n"
    report = validate_jsonl_text(text, "sample.jsonl")
    assert report.total_lines == 2
    assert report.valid_rows == 2

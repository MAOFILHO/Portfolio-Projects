"""Phase 11 Stage B1 -- `observability/guardrail_metrics.py`."""

from __future__ import annotations

import json
import logging

import pytest

from fnol_voice_agent.observability.guardrail_metrics import emit_guardrail_usage


def _last_payload(caplog: pytest.LogCaptureFixture) -> dict:
    records = [
        r for r in caplog.records if r.name == "fnol_voice_agent.observability.guardrail_metrics"
    ]
    assert records, "expected at least one guardrail_metrics log record"
    line = records[-1].getMessage()
    assert line.startswith("guardrail_usage ")
    return json.loads(line.removeprefix("guardrail_usage "))


def test_real_usage_is_reported_verbatim(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="fnol_voice_agent.observability.guardrail_metrics")

    emit_guardrail_usage(
        "OUTPUT",
        {"topicPolicyUnits": 1, "contentPolicyUnits": 2, "sensitiveInformationPolicyUnits": 0},
        blocked=False,
        masked=True,
    )

    payload = _last_payload(caplog)
    assert payload == {
        "metric": "guardrail_usage",
        "source": "OUTPUT",
        "blocked": False,
        "masked": True,
        "units": {
            "topicPolicyUnits": 1,
            "contentPolicyUnits": 2,
            "sensitiveInformationPolicyUnits": 0,
        },
    }


def test_empty_usage_is_reported_not_skipped(caplog: pytest.LogCaptureFixture) -> None:
    """The `MockGuardrailClient` case -- every local/test run. A missing line and a `units: {}` line mean
    different things (no call happened vs. a real call that accrued nothing); collapsing them would be
    the exact "zero errors vs. emitter dead" gap criterion 3's liveness requirement names."""
    caplog.set_level(logging.INFO, logger="fnol_voice_agent.observability.guardrail_metrics")

    emit_guardrail_usage("INPUT", {}, blocked=False)

    payload = _last_payload(caplog)
    assert payload["units"] == {}
    assert payload["source"] == "INPUT"
    assert payload["blocked"] is False
    assert payload["masked"] is False  # default


def test_masked_defaults_false_when_not_passed(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="fnol_voice_agent.observability.guardrail_metrics")

    emit_guardrail_usage("OUTPUT", {}, blocked=True)

    payload = _last_payload(caplog)
    assert payload["blocked"] is True
    assert payload["masked"] is False


def test_payload_keys_are_sorted_for_stable_line_shape(caplog: pytest.LogCaptureFixture) -> None:
    """`sort_keys=True` -- so a Logs Insights read of this line looks the same call to call, and an
    exact-string proof (Stage B1's liveness check, run against the real deployed Lambda) has a fixed
    shape to match against rather than a dict whose key order happens to vary by Python version."""
    caplog.set_level(logging.INFO, logger="fnol_voice_agent.observability.guardrail_metrics")

    emit_guardrail_usage("OUTPUT", {"b": 1, "a": 2}, blocked=False)

    records = [
        r for r in caplog.records if r.name == "fnol_voice_agent.observability.guardrail_metrics"
    ]
    line = records[-1].getMessage()
    assert line == (
        'guardrail_usage {"blocked": false, "masked": false, "metric": "guardrail_usage", '
        '"source": "OUTPUT", "units": {"a": 2, "b": 1}}'
    )

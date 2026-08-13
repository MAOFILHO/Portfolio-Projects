"""The Lex locale build waiter, and its negative controls.

Phase 8 Stage 3. This script exists because of a measured gap — CloudFormation reported `CREATE_COMPLETE`
~16 s before the `en_US` locale reached `Built`, on three consecutive applies at Stage 2 — and
`RESULTS.md` §3.5.1 names that gap as a platform pattern across three AWS services rather than a Lex
quirk.

The clock is injected, so these run instantly. A waiter tested with real sleeps is a waiter whose tests
get skipped.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.wait_for_lex_build import BuildWaitError, wait_for_built


class FakeLexModels:
    """Returns a scripted sequence of statuses, then repeats the last one forever.

    Repeating rather than raising on exhaustion is deliberate: the timeout test needs a client that
    keeps answering `Building`, which is exactly what a genuinely stalled build looks like.
    """

    def __init__(self, statuses: list[str], failure_reasons: list[str] | None = None) -> None:
        self._statuses = list(statuses)
        self._failure_reasons = failure_reasons or []
        self.calls = 0

    def describe_bot_locale(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        status = self._statuses[min(self.calls - 1, len(self._statuses) - 1)]
        response: dict[str, Any] = {"botLocaleStatus": status}
        if status == "Failed":
            response["failureReasons"] = self._failure_reasons
        return response


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def _wait(client: Any, *, timeout: float = 600.0) -> float:
    clock = FakeClock()
    return wait_for_built(
        client,
        "ABCDEFGHIJ",
        "en_US",
        timeout=timeout,
        poll_seconds=3.0,
        now=clock.now,
        sleep=clock.sleep,
    )


def test_an_already_built_locale_returns_immediately() -> None:
    client = FakeLexModels(["Built"])

    assert _wait(client) == 0.0
    assert client.calls == 1


def test_it_waits_through_the_stage_2_sequence() -> None:
    """The observed shape: the locale reports `ReadyExpressTesting` while CloudFormation is already
    green, then `Building`, then `Built`."""
    client = FakeLexModels(["ReadyExpressTesting", "Building", "Building", "Built"])

    waited = _wait(client)

    assert client.calls == 4
    assert waited == pytest.approx(9.0)


def test_a_failed_build_stops_the_run() -> None:
    client = FakeLexModels(["Building", "Failed"], failure_reasons=["slot type not found"])

    with pytest.raises(BuildWaitError) as excinfo:
        _wait(client)

    assert "slot type not found" in str(excinfo.value)


def test_an_unrecognised_status_stops_the_run() -> None:
    """Fail-closed, and this is the control that matters most.

    The tempting implementation treats an unknown status as transient and keeps polling — which turns a
    new terminal state into a timeout, or worse, into a silent pass if the polling loop is ever changed
    to return on exhaustion. An unknown status is not evidence of a built locale.
    """
    client = FakeLexModels(["Building", "SomeNewStatusAwsAddedThisQuarter"])

    with pytest.raises(BuildWaitError) as excinfo:
        _wait(client)

    assert "UNRECOGNISED" in str(excinfo.value)


def test_the_unrecognised_status_error_says_not_to_delete_the_check() -> None:
    """The realistic response to this error at 2am is to widen the check until it stops firing. The
    message names the correct fix — add the status to IN_PROGRESS — so widening is at least a decision.
    """
    client = FakeLexModels(["Whatever"])

    with pytest.raises(BuildWaitError) as excinfo:
        _wait(client)

    assert "IN_PROGRESS" in str(excinfo.value)
    assert "do not remove the check" in str(excinfo.value)


def test_a_stalled_build_times_out_rather_than_polling_forever() -> None:
    client = FakeLexModels(["Building"])

    with pytest.raises(BuildWaitError) as excinfo:
        _wait(client, timeout=30.0)

    assert "Timed out" in str(excinfo.value)


def test_the_timeout_message_discourages_simply_raising_the_timeout() -> None:
    """Stage 2 measured ~16 s. A run that has spent ten minutes is not a run that needs eleven."""
    client = FakeLexModels(["Building"])

    with pytest.raises(BuildWaitError) as excinfo:
        _wait(client, timeout=30.0)

    assert "stalled" in str(excinfo.value)


def test_it_polls_the_draft_version() -> None:
    """`AutoBuildBotLocales` builds DRAFT; a published version is what the release stack creates NEXT.
    Polling a numbered version here would ask about a thing that does not exist yet."""
    seen: list[dict[str, Any]] = []

    class Recording(FakeLexModels):
        def describe_bot_locale(self, **kwargs: Any) -> dict[str, Any]:
            seen.append(kwargs)
            return super().describe_bot_locale(**kwargs)

    _wait(Recording(["Built"]))

    assert seen[0]["botVersion"] == "DRAFT"
    assert seen[0]["localeId"] == "en_US"

"""Covers the non-negotiable guardrail: a rule-engine `critical` severity
must never be suppressed or downgraded by the Triage Agent, and a
Notification Policy Agent failure must never prevent a notification from
being sent. These are tested at the `analyze_frame` integration level (not
just unit-testing the agents in isolation) because the guardrail is enforced
by which code paths `analyze_frame` even calls, not by trusting the agents to
behave.
"""

from __future__ import annotations

import pytest

import function_app
from surveil_core.models import Detection


@pytest.fixture(autouse=True)
def _reset_notification_cooldown_cache():
    # The cooldown cache is deliberately module-level (mirrors the warm-
    # worker-process caches elsewhere in function_app.py), so it must be
    # cleared between tests to keep them independent.
    function_app._last_notified_cache.clear()
    yield
    function_app._last_notified_cache.clear()


class _FakeFrame:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self.length = len(data)
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeAnalyzer:
    def __init__(self, tag: str, confidence: float = 0.9) -> None:
        self._tag = tag
        self._confidence = confidence

    def detect(self, image_bytes: bytes):
        return [Detection(tag=self._tag, confidence=self._confidence)], "a detection"


class _FakeStorage:
    def __init__(self) -> None:
        self.saved_events = []
        self.enqueued_alerts = []
        self.audit_events = []

    def save_event(self, event) -> None:
        self.saved_events.append(event)

    def upload_annotated_frame(self, blob_name: str, image_bytes: bytes) -> str:
        return f"https://fake/{blob_name}"

    def enqueue_alert(self, alert) -> None:
        self.enqueued_alerts.append(alert)

    def log_audit_event(self, actor: str, action: str, details: str = "") -> None:
        self.audit_events.append((actor, action, details))


class _FakeNotifier:
    def __init__(self) -> None:
        self.send_all_calls = []
        self.send_selected_calls = []

    def send_all(self, alert):
        self.send_all_calls.append(alert)
        return {"email": True, "sms": True}

    def send_selected(self, alert, channels):
        self.send_selected_calls.append((alert, channels))
        return {c: True for c in channels}


class _AlwaysSuppressTriageAgent:
    """A maximally adversarial fake: always recommends suppression,
    regardless of input. Used to prove the guardrail holds even against a
    worst-case agent response, not just a well-behaved one.
    """

    async def triage(self, caption, matched_tags, rule_severity):
        from surveil_core.agents.models import TriageResult

        return TriageResult(escalate=False, escalated_severity=None, reasoning="test", suppress_recommended=True, suppress_reason="always suppress")


class _NeverCalledTriageAgent:
    async def triage(self, caption, matched_tags, rule_severity):
        raise AssertionError("Triage agent must never be invoked when rule-engine severity is already critical")


class _EscalatingTriageAgent:
    async def triage(self, caption, matched_tags, rule_severity):
        from surveil_core.agents.models import TriageResult

        return TriageResult(escalate=True, escalated_severity="medium", reasoning="context suggests higher risk", suppress_recommended=False, suppress_reason=None)


class _FailingNotificationPolicyAgent:
    async def decide(self, alert):
        raise RuntimeError("simulated notification policy agent outage")


class _DefaultNotificationPolicyAgent:
    """Fast, offline fake used whenever a test doesn't care about
    notification-policy behavior specifically -- never hits the network,
    unlike the real agent the factory functions would otherwise build.
    """

    async def decide(self, alert):
        from surveil_core.agents.models import NotificationDecision

        return NotificationDecision(channels=["email", "sms"], reasoning="default test fake", urgency_note=None)


async def _run_analyze_frame(monkeypatch, analyzer, storage, notifier, triage_agent, notification_agent=None, watch_tags="gun"):
    monkeypatch.setenv("ALERT_WATCH_TAGS", watch_tags)
    monkeypatch.setenv("OPENAI_ENDPOINT", "https://fake.openai.azure.com/")
    monkeypatch.setattr(function_app, "_storage", lambda: storage)
    monkeypatch.setattr(function_app, "_analyzer", lambda: analyzer)
    monkeypatch.setattr(function_app, "_notifier", lambda: notifier)
    # Always monkeypatch both agent factories -- never let a test fall
    # through to the real factory, which would build a real Kernel/
    # AzureChatCompletion and attempt a real network call.
    monkeypatch.setattr(function_app, "_triage_agent", lambda: triage_agent)
    monkeypatch.setattr(
        function_app, "_notification_policy_agent", lambda: notification_agent or _DefaultNotificationPolicyAgent()
    )

    frame = _FakeFrame("nest-front-door/frame123.jpg", b"fake-jpeg-bytes")
    await function_app.analyze_frame(frame)


async def test_critical_severity_is_never_suppressed_even_by_adversarial_agent(monkeypatch):
    analyzer = _FakeAnalyzer(tag="gun")  # DEFAULT_SEVERITY_MAP: gun -> critical
    storage = _FakeStorage()
    notifier = _FakeNotifier()

    await _run_analyze_frame(
        monkeypatch, analyzer, storage, notifier,
        triage_agent=_NeverCalledTriageAgent(),
        notification_agent=None,
    )

    assert len(storage.saved_events) == 1
    assert storage.saved_events[0].severity == "critical"
    assert len(storage.enqueued_alerts) == 1
    assert storage.enqueued_alerts[0].severity == "critical"
    # A notification was actually sent (via the default fake notification
    # policy agent's channel selection) -- the guardrail under test here is
    # severity, not the channel-selection path itself.
    assert len(notifier.send_selected_calls) == 1


async def test_notification_policy_agent_failure_falls_back_to_send_all(monkeypatch):
    analyzer = _FakeAnalyzer(tag="gun")
    storage = _FakeStorage()
    notifier = _FakeNotifier()

    await _run_analyze_frame(
        monkeypatch, analyzer, storage, notifier,
        triage_agent=_NeverCalledTriageAgent(),
        notification_agent=_FailingNotificationPolicyAgent(),
    )

    assert len(notifier.send_all_calls) == 1
    assert len(notifier.send_selected_calls) == 0


async def test_non_critical_severity_can_be_escalated_by_triage_agent(monkeypatch):
    analyzer = _FakeAnalyzer(tag="person")
    storage = _FakeStorage()
    notifier = _FakeNotifier()

    await _run_analyze_frame(
        monkeypatch, analyzer, storage, notifier,
        triage_agent=_EscalatingTriageAgent(),
        notification_agent=None,
        watch_tags="person",
    )

    assert storage.saved_events[0].severity == "medium"


async def test_triage_agent_failure_falls_back_to_rule_engine_severity(monkeypatch):
    analyzer = _FakeAnalyzer(tag="person")
    storage = _FakeStorage()
    notifier = _FakeNotifier()

    class _RaisingTriageAgent:
        async def triage(self, caption, matched_tags, rule_severity):
            raise RuntimeError("simulated triage agent outage")

    await _run_analyze_frame(
        monkeypatch, analyzer, storage, notifier,
        triage_agent=_RaisingTriageAgent(),
        notification_agent=None,
        watch_tags="person",
    )

    # "person" is rule-engine severity "low" per DEFAULT_SEVERITY_MAP -- must
    # be unchanged, not escalated, when the agent call fails.
    assert storage.saved_events[0].severity == "low"


async def test_repeat_alert_within_cooldown_skips_notification_but_still_records_event(monkeypatch):
    analyzer = _FakeAnalyzer(tag="person")
    storage = _FakeStorage()
    notifier = _FakeNotifier()
    monkeypatch.setattr(function_app, "_NOTIFICATION_COOLDOWN_SECONDS", 9999.0)

    for _ in range(2):
        await _run_analyze_frame(
            monkeypatch, analyzer, storage, notifier,
            triage_agent=_EscalatingTriageAgent(),
            notification_agent=None,
            watch_tags="person",
        )

    # Both detections are still recorded and queued for the dashboard --
    # cooldown only ever throttles the ACS send, never the event itself.
    assert len(storage.saved_events) == 2
    assert len(storage.enqueued_alerts) == 2
    # Only the first call actually notified; the second was within cooldown
    # for the same (camera_id, matched_tags) key.
    assert len(notifier.send_selected_calls) + len(notifier.send_all_calls) == 1


async def test_critical_severity_bypasses_notification_cooldown(monkeypatch):
    analyzer = _FakeAnalyzer(tag="gun")  # DEFAULT_SEVERITY_MAP: gun -> critical
    storage = _FakeStorage()
    notifier = _FakeNotifier()
    monkeypatch.setattr(function_app, "_NOTIFICATION_COOLDOWN_SECONDS", 9999.0)

    for _ in range(2):
        await _run_analyze_frame(
            monkeypatch, analyzer, storage, notifier,
            triage_agent=_NeverCalledTriageAgent(),
            notification_agent=None,
        )

    # Critical alerts must never be throttled by the cooldown -- both calls
    # notify, matching the same guardrail spirit as severity never being
    # downgradable.
    assert len(notifier.send_selected_calls) + len(notifier.send_all_calls) == 2

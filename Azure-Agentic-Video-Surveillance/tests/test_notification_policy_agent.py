from __future__ import annotations

from surveil_core.agents.notification_policy_agent import NotificationPolicyAgent
from surveil_core.models import AlertMessage

from fake_kernel import FakeKernel


def _alert(severity: str = "high") -> AlertMessage:
    return AlertMessage(
        event_id="e1",
        camera_id="cam1",
        frame_blob_name="cam1/frame.jpg",
        matched_tags=["person"],
        severity=severity,
        detections=[],
    )


async def test_decide_returns_agent_selected_channels():
    kernel = FakeKernel('{"channels": ["email"], "reasoning": "low urgency, no need to text", "urgency_note": null}')
    agent = NotificationPolicyAgent(kernel)

    decision = await agent.decide(_alert(severity="low"))

    assert decision.channels == ["email"]


async def test_decide_falls_back_to_all_channels_if_agent_returns_none():
    kernel = FakeKernel('{"channels": [], "reasoning": "oops", "urgency_note": null}')
    agent = NotificationPolicyAgent(kernel)

    decision = await agent.decide(_alert())

    assert decision.channels == ["email", "sms"]

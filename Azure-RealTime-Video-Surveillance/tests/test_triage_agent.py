from __future__ import annotations

from surveil_core.agents.triage_agent import TriageAgent

from fake_kernel import FakeKernel


async def test_triage_escalates_when_recommended_and_strictly_higher():
    kernel = FakeKernel(
        '{"escalate": true, "escalated_severity": "medium", "reasoning": "r", '
        '"suppress_recommended": false, "suppress_reason": null}'
    )
    agent = TriageAgent(kernel)

    result = await agent.triage(caption="a person near the door", matched_tags=["person"], rule_severity="low")

    assert result.escalate is True
    assert result.escalated_severity == "medium"


async def test_triage_suppress_recommendation_is_carried_but_not_special_cased():
    kernel = FakeKernel(
        '{"escalate": false, "escalated_severity": null, "reasoning": "likely duplicate", '
        '"suppress_recommended": true, "suppress_reason": "same detection as prior frame"}'
    )
    agent = TriageAgent(kernel)

    result = await agent.triage(caption=None, matched_tags=["person"], rule_severity="low")

    assert result.suppress_recommended is True
    assert result.suppress_reason == "same detection as prior frame"


async def test_triage_call_uses_the_kernels_chat_service():
    kernel = FakeKernel('{"escalate": false, "escalated_severity": null, "reasoning": "", "suppress_recommended": false, "suppress_reason": null}')
    agent = TriageAgent(kernel)

    await agent.triage(caption="x", matched_tags=["person"], rule_severity="low")

    assert len(kernel.service.calls) == 1

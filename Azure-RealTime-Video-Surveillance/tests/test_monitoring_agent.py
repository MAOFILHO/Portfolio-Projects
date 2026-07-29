from __future__ import annotations

from surveil_core.agents.monitoring_agent import MonitoringAgent

from fake_kernel import FakeKernel


async def test_analyze_returns_flags_and_severity():
    kernel = FakeKernel(
        '{"flags": ["failure rate jumped from 2% to 18% in the last hour"], '
        '"severity": "high", "summary": "Elevated failure rate detected."}'
    )
    agent = MonitoringAgent(kernel)

    report = await agent.analyze(
        requests_summary=[{"timestamp": "2026-01-01T00:00:00Z", "total": 100, "failed": 18}],
        exceptions=[{"timestamp": "2026-01-01T00:05:00Z", "severity": "Error", "message": "boom", "problem_id": "P1"}],
    )

    assert report.severity == "high"
    assert report.flags == ["failure rate jumped from 2% to 18% in the last hour"]


async def test_analyze_reports_low_severity_when_nothing_unusual():
    kernel = FakeKernel('{"flags": [], "severity": "low", "summary": "Nothing unusual."}')
    agent = MonitoringAgent(kernel)

    report = await agent.analyze(requests_summary=[], exceptions=[])

    assert report.flags == []
    assert report.severity == "low"

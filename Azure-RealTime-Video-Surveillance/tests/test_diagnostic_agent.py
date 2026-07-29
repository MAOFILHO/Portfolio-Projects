from __future__ import annotations

import json

from surveil_core.agents.diagnostic_agent import WebrtcDiagnosticAgent

from fake_kernel import FakeKernel


async def test_diagnose_reads_jsonl_and_returns_agent_report(tmp_path):
    log_path = tmp_path / "session.jsonl"
    events = [
        {"kind": "ice_state", "camera_id": "nest-front-yard", "fields": {"state": "connected"}},
        {"kind": "video_ssrc", "camera_id": "nest-front-yard", "fields": {"ssrc": 12345}},
        {"kind": "stats_snapshot", "camera_id": "nest-front-yard", "fields": {"packets_received": 3000, "packets_lost": 2, "frames_received": 0, "frames_decoded": 0}},
    ]
    with log_path.open("w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    kernel = FakeKernel("ICE connected, packets arrived, but no frame was ever decoded -- consistent with the known aiortc/encoder interop gap.")
    agent = WebrtcDiagnosticAgent(kernel)

    report = await agent.diagnose(log_path)

    assert "aiortc" in report or "interop" in report
    # the parsed events were sent to the model as the user message
    history, _settings, _kwargs = kernel.service.calls[0]
    user_message = str(history.messages[-1])
    assert "12345" in user_message
    assert "packets_received" in user_message

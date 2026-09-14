"""A scriptable stand-in for one caller's ACS media stream.

Satisfies `transport.protocol.MediaTransport` structurally, exactly as FastAPI's WebSocket does,
so `run_call` cannot tell the difference. **Nothing in this module makes a network call, ever** --
it is a list of strings and a list to append to.

Shape borrowed from the sibling project's fake model client
(AWS-Insurance-FNOL-Voice-Agentic-AI, `agents/testing/fake_llm.py`): deterministic, scripted in
call order, structurally satisfying the real interface without importing it.
"""
import asyncio
import json

from fastapi import WebSocketDisconnect


def audio_frame(b64_payload="AAAA"):
    """One inbound ACS audio frame -- lowercase keys, per the verified asymmetry in acs.py."""
    return json.dumps({"kind": "AudioData", "audioData": {"data": b64_payload}})


def dtmf_frame(tone="5"):
    """One inbound ACS DTMF frame. The tone is here so a test can prove it never comes back
    out -- B2 (CLAUDE.md): the PIN never reaches a transcript, log line, or span attribute."""
    return json.dumps({"kind": "DtmfData", "dtmfData": {"data": tone}})


def unknown_frame():
    """A frame kind the relay has no handling for. Must be ignored, never crashed on."""
    return json.dumps({"kind": "SomethingElse", "data": {}})


class FakeTransport:
    """Feeds `frames` to receive_text() in order, then disconnects -- the same contract a real ACS
    media WebSocket has once the caller hangs up.

    `hang=True` blocks forever once `frames` is drained instead of disconnecting, for tests where
    something other than the caller should end the call (a cost cap, or the model running out of
    scripted events). Only a cancel() ends that wait.
    """

    def __init__(self, frames=(), hang=False):
        self._frames = list(frames)
        self._hang = hang
        self.sent = []

    async def receive_text(self):
        if self._frames:
            return self._frames.pop(0)
        if self._hang:
            await asyncio.Future()  # never resolves; only a cancel() ends this
        raise WebSocketDisconnect()

    async def send_text(self, text):
        self.sent.append(text)

    @property
    def sent_audio_payloads(self):
        """The base64 payloads of every outbound audio frame, in order -- what the caller heard."""
        return [
            json.loads(frame)["AudioData"]["Data"]
            for frame in self.sent
            if json.loads(frame).get("Kind") == "AudioData"
        ]

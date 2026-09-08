#!/usr/bin/env python3
"""B5 latency probe: real Azure OpenAI realtime connection, no ACS/PSTN, no phone.

Marco's real phone calls (docs/phase2/evidence/b5-call-log.md) measure the full ACS-media-relay
plus AOAI round trip -- the true caller experience. This probe measures a narrower thing: just
the AOAI realtime leg, driven by connect_realtime() (realtime/client.py) directly instead of a
real call. It reuses run_call() (realtime/session.py) completely unchanged, so the exact same B5
log lines ("caller turn ended" / "agent audio started") land in this process's own stdout -- no
new instrumentation, no duplicated logic.

**Not part of the installed package's runtime and not unit tested** -- an ops/dev tool, same
category as boot.py's own __main__ block and the wizard scripts under docs/phase0/wizard/.

**Keep this data pool separate from the real-call one** (docs/phase2/evidence/b5-call-log.md):
skipping ACS is a real, deliberate narrowing of what's measured, not a free substitute -- see
that file's own note on why, and Marco's own decision recorded there.

Requires the three env vars connect_realtime() already needs -- fetch AOAI_KEY yourself, never
paste it into chat or a committed file:

    AOAI_KEY=$(az containerapp secret show -n ca-azbank-echo-p0 \\
        -g rg-azure-banking-voice-agentic-ai --secret-name aoai-key --query value -o tsv) \\
    AOAI_ENDPOINT=https://aoai-azure-banking-voice-cc.openai.azure.com/ \\
    AOAI_DEPLOYMENT=gpt-realtime-mini \\
    python3 scripts/b5_probe.py --calls 20

Requires macOS (`say` + `afconvert`, both stdlib to the OS) to synthesize caller audio -- no
network TTS, no new dependency. Run on Marco's laptop, same as the Docker builds.
"""
import argparse
import asyncio
import base64
import json
import logging
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "voice-agent"))

from azbank_voice_agent.realtime.client import connect_realtime
from azbank_voice_agent.realtime.session import run_call
from fastapi import WebSocketDisconnect

log = logging.getLogger("b5_probe")

# A handful of short, distinct caller phrases -- enough variety that the model isn't hearing the
# exact same audio every time, without needing a large corpus. Content matters less than volume
# for a pure latency measurement; these mirror what Calls 2-8 actually asked.
UTTERANCES = [
    "Hi, what's my checking account balance",
    "I'd like to transfer five hundred dollars to savings",
    "Can you list my accounts please",
    "What's my savings account balance",
]

_SAMPLE_RATE = 24000  # matches session.py's _AUDIO_CONFIG -- audio/pcm, 24000 Hz, mono
_FRAME_MS = 20  # real ACS streams small chunks, not one giant frame -- mirrors that pacing


def _synthesize_pcm16(text):
    """Shells out to macOS `say` + `afconvert` to get real, intelligible speech audio as raw
    PCM16/24kHz/mono bytes -- the exact wire format session.py expects (_AUDIO_CONFIG). Fails
    loudly on any mismatch rather than silently feeding the model audio it wasn't confirmed to
    expect (same rigor as the rest of this project's wire-format assumptions)."""
    with tempfile.TemporaryDirectory() as tmp:
        aiff_path = os.path.join(tmp, "utterance.aiff")
        wav_path = os.path.join(tmp, "utterance.wav")
        subprocess.run(["say", "-o", aiff_path, text], check=True, capture_output=True)
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@24000", "-c", "1", aiff_path, wav_path],
            check=True, capture_output=True,
        )
        with wave.open(wav_path, "rb") as wav_file:
            if (wav_file.getframerate(), wav_file.getnchannels(), wav_file.getsampwidth()) != (
                _SAMPLE_RATE, 1, 2,
            ):
                raise ValueError(
                    f"afconvert produced {wav_file.getframerate()}Hz/"
                    f"{wav_file.getnchannels()}ch/{wav_file.getsampwidth()}B, not "
                    f"{_SAMPLE_RATE}Hz/1ch/2B -- wire-format assumption broke, fix before trusting "
                    "any latency this probe measures."
                )
            return wav_file.readframes(wav_file.getnframes())


def _chunk_to_frames(pcm_bytes):
    """Splits raw PCM16 into ~20ms base64 ACS-shaped inbound frames (transport/acs.py's
    lowercase-keys inbound shape) -- real ACS streams small chunks continuously, not one frame."""
    bytes_per_frame = int(_SAMPLE_RATE * _FRAME_MS / 1000) * 2  # 2 bytes/sample, mono
    frames = []
    for i in range(0, len(pcm_bytes), bytes_per_frame):
        chunk = pcm_bytes[i:i + bytes_per_frame]
        b64 = base64.b64encode(chunk).decode("ascii")
        frames.append(json.dumps({"kind": "AudioData", "audioData": {"data": b64}}))
    return frames


class _SyntheticTransport:
    """One synthetic call: streams one utterance's frames at real-time pace, waits long enough
    for a reply, then disconnects -- mirrors transport/fake.py's FakeTransport contract exactly,
    just with real audio content and real timing instead of scripted placeholder frames."""

    def __init__(self, frames, tail_seconds=6.0):
        self._frames = list(frames)
        self._tail_seconds = tail_seconds
        self._exhausted = False

    async def receive_text(self):
        if self._frames:
            await asyncio.sleep(_FRAME_MS / 1000)
            return self._frames.pop(0)
        if not self._exhausted:
            self._exhausted = True
            await asyncio.sleep(self._tail_seconds)  # let the model answer before hangup
        raise WebSocketDisconnect()

    async def send_text(self, text):
        pass  # agent audio discarded -- run_call() already logs "agent audio started" for B5


class _DebugRealtime:
    """Wraps a real realtime connection to log every event.type as it arrives -- diagnostic only,
    isolated to this script (never touches session.py, the file this project treats with the most
    care). Added 2026-09-08: the first real run produced 0 caller-turn/audio-started lines across
    3 calls, meaning either no events arrived at all or something upstream of run_call()'s own
    handling is the gap -- this answers which, without guessing."""

    def __init__(self, inner):
        self._inner = inner

    async def send(self, message):
        log.info("-> sent %s", message.get("type"))
        await self._inner.send(message)

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        async for event in self._inner:
            log.info("<- received %s", getattr(event, "type", event))
            yield event


async def _run_one(frames):
    async with connect_realtime() as realtime:
        await run_call(_SyntheticTransport(frames), _DebugRealtime(realtime))


async def _main(calls):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    log.info("synthesizing %d utterance(s)...", len(UTTERANCES))
    frame_sets = [_chunk_to_frames(_synthesize_pcm16(text)) for text in UTTERANCES]

    completed, failed = 0, 0
    for i in range(calls):
        frames = frame_sets[i % len(frame_sets)]
        log.info("--- synthetic call %d/%d ---", i + 1, calls)
        try:
            await _run_one(frames)
            completed += 1
        except Exception:
            log.exception("synthetic call %d failed, continuing", i + 1)
            failed += 1
    log.info("done: %d completed, %d failed", completed, failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", type=int, default=20, help="number of synthetic calls to run")
    args = parser.parse_args()
    for var in ("AOAI_KEY", "AOAI_ENDPOINT", "AOAI_DEPLOYMENT"):
        if var not in os.environ:
            sys.exit(f"b5_probe: {var} is not set -- see this script's own docstring.")
    asyncio.run(_main(args.calls))

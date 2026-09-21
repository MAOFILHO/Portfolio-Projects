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
that file's own note on why, and Marco's own decision recorded there. The run prints its own N so
a percentile quoted from it can state the turn count behind it, which this project requires of
every percentile it quotes anywhere.

**Repaired in Phase 5 (issue #54), after two phases broken.** Phase 3 gave `run_call` a third,
required parameter and this script went on passing two, so it raised `TypeError` before opening a
connection every time it was run. Nothing noticed, because an ops tool has no test.
`assert_probe_matches_run_call()` is the cheap guard against that happening again, and it runs
before anything is synthesized or dialled.

**It now keys a PIN and reaches a real service**, and both are load-bearing. Phase 2's figure was
taken with the gate refusing every tool call, so the core-banking hop was in the path zero times;
a probe that authenticated but reached nothing, or reached something but stayed anonymous, would
re-measure those refusals under a new name. The whole reason B5 freezes in this phase is that tool
calls are the slowest leg.

**Authenticates the way the deployed app does, as whoever you are logged in as.** `connect_realtime`
takes a bearer-token provider (the `AOAI_KEY` secret is retired, D2), and this script builds one over
`azure.identity.aio.DefaultAzureCredential` -- `az login` on a laptop. That identity needs a role
with inference data actions on the account: `Cognitive Services OpenAI User`, the one
`infra/modules/aoai.bicep` grants the Container App's identity, or `Foundry User`, which Marco's login
holds (its `dataActions` are `Microsoft.CognitiveServices/*`). `Owner` and `Contributor` carry none
(`az role definition list`, 2026-09-21). Not yet run against the live deployment -- it dials a billable
realtime connection. It needs two env vars:

    AOAI_ENDPOINT=https://aoai-azure-banking-voice-cc.openai.azure.com/ \\
    AOAI_DEPLOYMENT=gpt-realtime-mini \\
    python3 scripts/b5_probe.py --calls 20 --core-banking-url <url>

Requires macOS (`say` + `afconvert`, both stdlib to the OS) to synthesize caller audio -- no
network TTS, no new dependency. Run on Marco's laptop, same as the Docker builds.
"""
import argparse
import asyncio
import base64
import inspect
import json
import logging
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "voice-agent"))

from azbank_voice_agent.boot import COGNITIVE_SERVICES_SCOPE
from azbank_voice_agent.call_records.fake import FakeCallRecordStore
from azbank_voice_agent.core_banking import HttpCoreBankingClient
from azbank_voice_agent.core_banking.fake import DEFAULT_PIN
from azbank_voice_agent.realtime.client import connect_realtime
from azbank_voice_agent.realtime.session import run_call
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
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

#: One 20ms frame of PCM16 mono, in bytes. Two bytes per sample. Written once: the same expression
#: appeared in `_chunk_to_frames` and `_silence_frames`, where the two copies had to agree for the
#: silence frames to be the same size as the speech frames they pad (/code-review, 2026-09-11).
_BYTES_PER_FRAME = int(_SAMPLE_RATE * _FRAME_MS / 1000) * 2


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
    frames = []
    for i in range(0, len(pcm_bytes), _BYTES_PER_FRAME):
        chunk = pcm_bytes[i:i + _BYTES_PER_FRAME]
        b64 = base64.b64encode(chunk).decode("ascii")
        frames.append(json.dumps({"kind": "AudioData", "audioData": {"data": b64}}))
    return frames


def _silence_frames(seconds):
    """`seconds` of genuine digital-silence PCM16 frames, same shape as `_chunk_to_frames`.

    First real run (2026-09-08) proved why this is needed, not assumed: `speech_started` fired
    correctly (the synthesized speech is real, recognized audio) but `speech_stopped` never did,
    across 3 full calls -- server-side VAD measures silence *from the audio stream itself*, so it
    needs to keep receiving frames (even silent ones) to notice ~200ms of near-zero amplitude has
    passed. A real ACS call streams continuously, silence included; simply stopping sends after
    the spoken utterance (the original bug here) gives the server nothing to measure a pause from
    at all, so no turn ever ends and no B5 latency anchor ever fires."""
    n_frames = int(seconds * 1000 / _FRAME_MS)
    b64_silence = base64.b64encode(b"\x00" * _BYTES_PER_FRAME).decode("ascii")
    frame = json.dumps({"kind": "AudioData", "audioData": {"data": b64_silence}})
    return [frame] * n_frames


#: The arguments this probe passes to `run_call`, positionally, in order. Checked against the real
#: signature before a single call is dialled -- see `assert_probe_matches_run_call`.
_RUN_CALL_ARGUMENTS = ("transport", "realtime", "core_banking", "call_records")


def assert_probe_matches_run_call():
    """Refuse to start if `run_call`'s signature has moved out from under this script (issue #54).

    **This is the cheap guard for a defect that cost two phases.** Phase 3 gave `run_call` a third,
    required parameter; this probe went on passing two, and raised `TypeError` before it opened a
    connection every time it was run from then until Phase 5. Nothing noticed, because an ops tool
    has no test -- and the first anybody would have learned of it is an operator trying to produce
    the figure B5 freezes on.

    Checked at startup, where the operator is, **and** covered by `tests/test_b5_probe.py`, which
    drifts the signature four ways and requires this to fire on three of them and stay quiet on the
    fourth. A guard that silently stopped guarding would pass forever -- the same reason B2's leak
    detector leaks on purpose. It costs microseconds and runs before anything is synthesized or
    dialled.

    A new *optional* parameter is tolerated. Not every change is a break, and a guard that failed on
    those would be switched off within a phase.

    **It is one of this project's two deliberate assertions about shape rather than behaviour** --
    the other being B2's own leak detector. Asserting a signature is normally testing the
    implementation; here the signature *is* the contract between two files that nothing else
    connects.
    """
    _assert_signature_matches(run_call, "run_call", _RUN_CALL_ARGUMENTS)


#: What this probe passes to `connect_realtime`. See `assert_probe_matches_connect_realtime`.
_CONNECT_REALTIME_ARGUMENTS = ("token_provider",)


def assert_probe_matches_connect_realtime():
    """The same guard, for the other function this probe is wired to (Phase 8 gate review 3).

    `connect_realtime` gained a required `token_provider` and the probe kept calling it with
    nothing: `TypeError` before a connection opened. Ruff lints `scripts/` but cannot see an arity
    mismatch, mypy does not cover it, and no test reached it. Same mechanism, same tolerance for a
    new optional parameter.
    """
    _assert_signature_matches(connect_realtime, "connect_realtime", _CONNECT_REALTIME_ARGUMENTS)


def _assert_signature_matches(function, name, expected):
    """`name` is passed rather than read off `function`: the tests patch in stand-ins whose own name
    is not the one an operator should see."""
    signature = inspect.signature(function).parameters
    parameters = list(signature)
    expected = list(expected)
    if parameters[:len(expected)] != expected:
        raise SystemExit(
            f"b5_probe is out of date: {name}'s signature has changed.\n"
            f"  this probe passes: {expected}\n"
            f"  {name} now takes: {parameters}\n"
            "Fix _run_one() to match before running the probe -- a figure produced by a probe "
            "that guessed at the relay's shape is not a measurement of the relay."
        )
    required = [
        parameter_name for parameter_name, parameter in signature.items()
        if parameter.default is inspect.Parameter.empty
    ]
    if set(required) - set(expected):
        raise SystemExit(
            f"b5_probe is out of date: {name} has required parameters this probe does not pass: "
            f"{sorted(set(required) - set(expected))}"
        )


class _SyntheticTransport:
    """One synthetic call: streams one utterance's frames (speech + a trailing silence tail, see
    `_silence_frames`) at real-time pace, waits long enough for a reply, then disconnects --
    mirrors transport/fake.py's FakeTransport contract exactly, just with real audio content and
    real timing instead of scripted placeholder frames."""

    def __init__(self, frames, tail_seconds=6.0, keys=()):
        # The PIN's tones go first, before any audio (issue #54). DTMF frames are not audio
        # appends, so the authenticator has finished and the gate has opened before the model has
        # heard a word -- which is what makes the tool calls that follow *granted* rather than
        # refused, and is the whole reason this probe measures anything the plan cares about.
        self._frames = [
            json.dumps({"kind": "DtmfData", "dtmfData": {"data": key}}) for key in keys
        ] + list(frames)
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


async def _run_one(frames, debug, core_banking, call_records, keys, token_provider):
    async with connect_realtime(token_provider) as realtime:
        if debug:
            realtime = _DebugRealtime(realtime)
        await run_call(
            _SyntheticTransport(frames, keys=keys), realtime, core_banking, call_records
        )


_SILENCE_TAIL_SECONDS = 1.0  # > silence_duration_ms (200ms, session.py's _AUDIO_CONFIG) with margin


async def _main(calls, debug, core_banking_url, pin):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    assert_probe_matches_run_call()
    assert_probe_matches_connect_realtime()
    log.info("synthesizing %d utterance(s)...", len(UTTERANCES))
    silence_tail = _silence_frames(_SILENCE_TAIL_SECONDS)
    frame_sets = [
        _chunk_to_frames(_synthesize_pcm16(text)) + silence_tail for text in UTTERANCES
    ]

    # **A real client against a reachable service** (issue #54). Without this the probe would
    # re-measure Phase 2's refusals under a new name: that figure was taken with the gate refusing
    # every tool call, so the core-banking hop was in the path zero times, and the whole reason B5
    # freezes in this phase is that tool calls are the slowest leg.
    core_banking = HttpCoreBankingClient(base_url=core_banking_url)
    # The probe has no Storage account and needs none: what it measures is turn latency, and the
    # ledger is not in a turn's path. The fake keeps the relay's collaborator contract satisfied
    # without inventing a dependency the measurement does not have.
    call_records = FakeCallRecordStore()
    keys = tuple(pin)

    # One credential for the whole run, so its token cache serves every synthetic call -- the same
    # shape as the app's one shared credential.
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, COGNITIVE_SERVICES_SCOPE)

    completed, failed = 0, 0
    try:
        for i in range(calls):
            frames = frame_sets[i % len(frame_sets)]
            log.info("--- synthetic call %d/%d ---", i + 1, calls)
            try:
                await _run_one(frames, debug, core_banking, call_records, keys, token_provider)
                completed += 1
            except Exception:
                log.exception("synthetic call %d failed, continuing", i + 1)
                failed += 1
    finally:
        await core_banking.aclose()
        await credential.close()
    # **N, printed by the run itself.** Every percentile this project quotes states the turn count
    # behind it, and a probe that made the operator count log lines to find one would be inviting
    # the figure to be reported without it.
    log.info("done: %d completed, %d failed", completed, failed)
    log.info(
        "B5 probe pool: %d completed synthetic calls. This pool is SEPARATE from the real-call "
        "pool and the two are never merged into one unlabelled figure -- the probe skips the ACS "
        "media relay, which is a real narrowing of what is measured.",
        completed,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", type=int, default=20, help="number of synthetic calls to run")
    parser.add_argument(
        "--core-banking-url", default=os.environ.get("CORE_BANKING_URL"),
        help="where mock-core-banking is reachable. REQUIRED: without it the probe would measure "
             "tool calls that fail rather than tool calls that complete, which is the Phase 2 "
             "figure under a new name.",
    )
    parser.add_argument(
        "--pin", default=DEFAULT_PIN,
        help="the PIN the probe keys so the gate grants. Defaults to the demo PIN, which is a "
             "published constant of this prototype.",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="log every event.type sent/received -- verbose, use with a small --calls",
    )
    args = parser.parse_args()
    for var in ("AOAI_ENDPOINT", "AOAI_DEPLOYMENT"):
        if var not in os.environ:
            sys.exit(f"b5_probe: {var} is not set -- see this script's own docstring.")
    if not args.core_banking_url:
        # Refused rather than defaulted, for the reason the boot guard refuses an unconfigured
        # backend: a probe pointed at nothing would report a p95 for a system in which every tool
        # call failed, which is a number that looks like a measurement and is not one.
        sys.exit(
            "b5_probe: --core-banking-url (or CORE_BANKING_URL) is required. Without a reachable "
            "service the probe measures tool calls that fail, which is Phase 2's figure under a "
            "new name -- and Phase 2's figure is exactly what B5 is being re-measured to replace."
        )
    asyncio.run(_main(args.calls, args.debug, args.core_banking_url, args.pin))

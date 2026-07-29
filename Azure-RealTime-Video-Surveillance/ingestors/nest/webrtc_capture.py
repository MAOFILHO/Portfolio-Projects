"""Grabs a single frame from a Nest camera's WebRTC live stream.

Fallback path for cameras that don't advertise CameraClipPreview (so
CameraEventImage.GenerateImage 400s and there's no previewUrl to download).
CameraLiveStream.GenerateWebRtcStream works on any WebRTC-capable device --
which is effectively all current Nest hardware -- but unlike the other two
paths, it requires running a real WebRTC session (SDP offer/answer, ICE,
DTLS-SRTP, RTP video decode) rather than a simple HTTP GET, hence the
dependency on aiortc.

Google's SDM WebRTC implementation doesn't support trickle ICE, so the full
local SDP (with all ICE candidates already gathered) must be sent in one
shot -- see _wait_for_ice_gathering_complete.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
import re

import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.codecs import h264 as _aiortc_h264
from aiortc.rtcrtpreceiver import RTCRtpReceiver

from diagnostics import DiagnosticLogWriter
from sdm_client import SdmClient

logger = logging.getLogger("nest_ingestor.webrtc")

DEFAULT_TIMEOUT_SECONDS = 60.0

# Opt-in structured (JSONL) diagnostic log, additive to the free-text
# logger.warning/info calls throughout this module -- see diagnose_webrtc.py.
# None (default) means disabled: zero overhead, no file written.
_diagnostic_writer: DiagnosticLogWriter | None = None


def set_diagnostic_log_path(path: str | None) -> None:
    global _diagnostic_writer
    _diagnostic_writer = DiagnosticLogWriter(path) if path else None


def _diag(kind: str, camera_id: str | None = None, **fields) -> None:
    if _diagnostic_writer is not None:
        _diagnostic_writer.write(kind, camera_id=camera_id, **fields)

# --- Temporary diagnostic: log the Annex-B NAL unit types present in every
# assembled JitterFrame that fails to decode, so we can tell whether Google's
# encoder is ever actually delivering a keyframe (NAL type 5 = IDR, 7 = SPS,
# 8 = PPS) that our PLI requests should be triggering, versus never sending
# one at all. Remove once the root cause is confirmed.
_NAL_TYPE_NAMES = {5: "IDR", 7: "SPS", 8: "PPS", 1: "non-IDR"}


def _nal_types_in(data: bytes) -> set[int]:
    types = set()
    i = 0
    while i < len(data) - 4:
        if data[i : i + 4] == b"\x00\x00\x00\x01":
            types.add(data[i + 4] & 0x1F)
            i += 4
        else:
            i += 1
    return types


_original_h264_decode = _aiortc_h264.H264Decoder.decode
_diagnostic_counts: dict[str, int] = {"attempts": 0, "with_idr": 0}


def _diagnostic_h264_decode(self, encoded_frame):  # noqa: ANN001, ANN202
    frames = _original_h264_decode(self, encoded_frame)
    if not frames:
        _diagnostic_counts["attempts"] += 1
        types = _nal_types_in(encoded_frame.data)
        has_idr = 5 in types
        if has_idr:
            _diagnostic_counts["with_idr"] += 1
        # Only log every 10th failed attempt (to avoid flooding at ~30fps),
        # but always log the first time an IDR shows up in a failed attempt --
        # that's the specific signal we're hunting for.
        if has_idr or _diagnostic_counts["attempts"] % 10 == 1:
            names = sorted(_NAL_TYPE_NAMES.get(t, str(t)) for t in types)
            logger.warning(
                "H264 decode produced no frame (#%d, %d with IDR seen so far): "
                "%d bytes, nal_types=%s",
                _diagnostic_counts["attempts"],
                _diagnostic_counts["with_idr"],
                len(encoded_frame.data),
                names,
            )
            _diag(
                "h264_decode_fail",
                attempt=_diagnostic_counts["attempts"],
                with_idr_so_far=_diagnostic_counts["with_idr"],
                byte_count=len(encoded_frame.data),
                nal_types=names,
                has_idr=has_idr,
            )
    return frames


_aiortc_h264.H264Decoder.decode = _diagnostic_h264_decode

# Google's SDM WebRTC answer emits non-conformant ICE candidate lines --
# "a=candidate: 1 udp ..." -- missing the required `foundation` token before
# the component id. aiortc's strict RFC5245 parser then misreads the
# component ("1") as the foundation and the transport ("udp") as the
# component, raising `ValueError: invalid literal for int(): 'udp'`. Insert a
# synthetic (unique per line) foundation token before handing the SDP to
# aiortc; a real ICE session never touches this value's meaning for our
# single-frame-capture use case.
_MISSING_FOUNDATION_CANDIDATE = re.compile(r"^a=candidate: (\d+ (?:udp|tcp) .+)$", re.MULTILINE)


def _patch_missing_candidate_foundations(sdp: str) -> str:
    counter = itertools.count(1)

    def _insert_foundation(match: re.Match) -> str:
        return f"a=candidate:{next(counter)} {match.group(1)}"

    return _MISSING_FOUNDATION_CANDIDATE.sub(_insert_foundation, sdp)


async def _log_inbound_video_stats(pc: RTCPeerConnection, camera_id: str | None = None) -> None:
    """Diagnostic for when no video frame decodes in time -- distinguishes
    "no video RTP packets ever arrived" (transport/demux problem) from
    "packets arrived but never assembled into a decodable frame" (codec/
    keyframe problem), which call for entirely different fixes.
    """
    try:
        stats = await pc.getStats()
    except Exception:  # noqa: BLE001 - diagnostic only, must not mask the real error
        logger.exception("Failed to fetch WebRTC stats for diagnostics")
        return
    for report in stats.values():
        if getattr(report, "kind", None) == "video" and report.type == "inbound-rtp":
            packets_received = getattr(report, "packetsReceived", "?")
            packets_lost = getattr(report, "packetsLost", "?")
            frames_received = getattr(report, "framesReceived", "?")
            frames_decoded = getattr(report, "framesDecoded", "?")
            logger.error(
                "Video inbound-rtp stats: packetsReceived=%s packetsLost=%s "
                "framesReceived=%s framesDecoded=%s",
                packets_received,
                packets_lost,
                frames_received,
                frames_decoded,
            )
            _diag(
                "stats_snapshot",
                camera_id=camera_id,
                packets_received=packets_received,
                packets_lost=packets_lost,
                frames_received=frames_received,
                frames_decoded=frames_decoded,
            )


_KEYFRAME_REQUEST_INTERVAL_SECONDS = 2.0


def _video_ssrc_from_sdp(sdp: str) -> int | None:
    """Pulls the video m-line's SSRC directly out of the SDP answer.

    getStats() only reports an inbound-rtp entry for an SSRC once packets
    for it have actually arrived -- so deriving the PLI target from stats
    creates a chicken-and-egg deadlock if the remote side is withholding
    video until it receives a keyframe request. The SSRC is already known
    at negotiation time (it's in the SDP itself), so use that instead.
    """
    in_video = False
    for line in sdp.splitlines():
        if line.startswith("m="):
            in_video = line.startswith("m=video")
            continue
        if in_video and line.startswith("a=ssrc:"):
            try:
                return int(line[len("a=ssrc:") :].split()[0])
            except ValueError:
                continue
    return None


async def _request_keyframes_until_done(
    pc: RTCPeerConnection,
    frame_future: asyncio.Future,
    initial_ssrc: int | None,
    camera_id: str | None = None,
) -> None:
    """Periodically asks the sender for a keyframe (RTCP PLI).

    aiortc's jitter buffer only sends a PLI reactively, when its buffer
    overflows from packet loss -- it never asks for one just because a
    stream is starting. Google's encoder won't insert a keyframe on its own
    schedule fast enough for a one-shot capture, so without an explicit
    request the decoder can receive thousands of clean (zero-loss) delta-
    frame packets and never produce a single decodable frame, since a delta
    frame is meaningless without a prior keyframe as its reference.

    Sends the first PLI immediately using the SSRC from the SDP answer
    (not from getStats(), which won't have an entry until packets for that
    SSRC have already arrived -- see _video_ssrc_from_sdp).
    """
    video_receiver = next(
        (r for r in pc.getReceivers() if r.track is not None and r.track.kind == "video"), None
    )
    if video_receiver is None:
        return

    ssrc = initial_ssrc
    if ssrc is not None:
        logger.info("Requesting keyframe (RTCP PLI) for ssrc=%s (from SDP)", ssrc)
        _diag("rtcp_pli", camera_id=camera_id, ssrc=ssrc, source="sdp")
        await video_receiver._send_rtcp_pli(ssrc)

    while not frame_future.done():
        await asyncio.sleep(_KEYFRAME_REQUEST_INTERVAL_SECONDS)
        if frame_future.done():
            return
        stats = await pc.getStats()
        stats_ssrc = next(
            (
                report.ssrc
                for report in stats.values()
                if getattr(report, "kind", None) == "video" and report.type == "inbound-rtp"
            ),
            None,
        )
        ssrc = stats_ssrc or ssrc
        if ssrc is not None:
            logger.info("Requesting keyframe (RTCP PLI) for ssrc=%s", ssrc)
            _diag("rtcp_pli", camera_id=camera_id, ssrc=ssrc, source="stats")
            await video_receiver._send_rtcp_pli(ssrc)


async def _log_state_heartbeat(
    pc: RTCPeerConnection, frame_future: asyncio.Future, camera_id: str | None = None
) -> None:
    """Temporary diagnostic: logs connection/ICE state every 5s regardless of
    whether it changes, so a connection that's stuck (never fires a
    statechange event because it never leaves its initial state) is still
    visible. Remove once the root cause is confirmed.
    """
    while not frame_future.done():
        await asyncio.sleep(5.0)
        if frame_future.done():
            return
        receiver_kinds = [(r.track.kind if r.track else None) for r in pc.getReceivers()]
        logger.warning(
            "Heartbeat: ice=%s conn=%s signaling=%s receivers=%s",
            pc.iceConnectionState,
            pc.connectionState,
            pc.signalingState,
            receiver_kinds,
        )
        _diag(
            "heartbeat",
            camera_id=camera_id,
            ice_state=pc.iceConnectionState,
            connection_state=pc.connectionState,
            signaling_state=pc.signalingState,
            receiver_kinds=receiver_kinds,
        )


async def _wait_for_ice_gathering_complete(pc: RTCPeerConnection) -> None:
    if pc.iceGatheringState == "complete":
        return
    done: asyncio.Future = asyncio.get_event_loop().create_future()

    @pc.on("icegatheringstatechange")
    def _on_change() -> None:
        if pc.iceGatheringState == "complete" and not done.done():
            done.set_result(None)

    await done


async def _capture_frame_async(
    sdm_client: SdmClient, device_name: str, timeout: float
) -> bytes:
    pc = RTCPeerConnection()
    frame_future: asyncio.Future = asyncio.get_event_loop().create_future()

    # Temporary diagnostic: connection/ICE/signaling state changes weren't
    # logged at all before, so a track that never fires and a track that
    # fires but never decodes look identical from the logs -- this tells
    # us which one we're actually hitting (e.g. ICE stuck in "checking"
    # points at network/firewall, "connected" with no track points at an
    # SDP/negotiation semantics problem). Remove once the root cause is
    # confirmed.
    @pc.on("iceconnectionstatechange")
    def _on_ice_state() -> None:
        logger.warning("ICE connection state: %s", pc.iceConnectionState)
        _diag("ice_state", camera_id=device_name, state=pc.iceConnectionState)

    @pc.on("connectionstatechange")
    def _on_conn_state() -> None:
        logger.warning("Peer connection state: %s", pc.connectionState)
        _diag("connection_state", camera_id=device_name, state=pc.connectionState)

    @pc.on("signalingstatechange")
    def _on_signaling_state() -> None:
        logger.warning("Signaling state: %s", pc.signalingState)
        _diag("signaling_state", camera_id=device_name, state=pc.signalingState)

    @pc.on("track")
    def _on_track(track) -> None:  # noqa: ANN001 - aiortc's MediaStreamTrack
        logger.info("Received %s track", track.kind)
        if track.kind != "video":
            return

        async def _reader() -> None:
            try:
                logger.info("Waiting for first video frame...")
                frame = await track.recv()
                logger.info("Got a video frame")
                if not frame_future.done():
                    frame_future.set_result(frame)
            except Exception as exc:  # noqa: BLE001 - surfaced via the future
                if not frame_future.done():
                    frame_future.set_exception(exc)

        asyncio.ensure_future(_reader())

    # Google's SDM WebRTC endpoint rejects the offer unless it has audio,
    # video, and application (data channel) m-lines, in that exact order --
    # even though we only care about video. aiortc emits m-lines in the
    # order transceivers/channels are added, so audio must come first.
    pc.addTransceiver("audio", direction="recvonly")
    video_transceiver = pc.addTransceiver("video", direction="recvonly")
    pc.createDataChannel("dummy")

    # aiortc offers VP8 before H264 by default. Every capture attempt so far
    # has received plenty of RTP packets (hundreds to thousands) but never
    # decoded a single frame, and our H264Decoder diagnostic patch never even
    # fired -- strongly suggesting Google's server is actually negotiating
    # VP8, not H264, and something in that path silently never produces a
    # frame. Force H264 so our diagnostics apply to the codec really in use.
    h264_codecs = [
        codec
        for codec in RTCRtpReceiver.getCapabilities("video").codecs
        if codec.mimeType == "video/H264"
    ]
    if h264_codecs:
        video_transceiver.setCodecPreferences(h264_codecs)

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    await _wait_for_ice_gathering_complete(pc)

    media_session_id = None
    try:
        results = sdm_client.generate_webrtc_stream(device_name, pc.localDescription.sdp)
        media_session_id = results.get("mediaSessionId")
        answer_sdp = _patch_missing_candidate_foundations(results["answerSdp"])
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
        await pc.setRemoteDescription(answer)
        rtpmap_lines = [
            line.strip()
            for line in answer_sdp.splitlines()
            if line.startswith("a=rtpmap") and ("H264" in line or "VP8" in line or "VP9" in line)
        ]
        for line in rtpmap_lines:
            logger.info("Negotiated video codec line: %s", line)
        m_lines = [line.strip() for line in answer_sdp.splitlines() if line.startswith("m=")]
        logger.warning("Answer SDP m-lines: %s", m_lines)
        logger.warning(
            "Immediately after setRemoteDescription: ice=%s conn=%s signaling=%s",
            pc.iceConnectionState, pc.connectionState, pc.signalingState,
        )
        _diag(
            "sdp_negotiated",
            camera_id=device_name,
            m_lines=m_lines,
            rtpmap_lines=rtpmap_lines,
            ice_state=pc.iceConnectionState,
            connection_state=pc.connectionState,
            signaling_state=pc.signalingState,
        )

        video_ssrc = _video_ssrc_from_sdp(answer_sdp)
        logger.warning("Video SSRC parsed from SDP answer: %s", video_ssrc)
        _diag("video_ssrc", camera_id=device_name, ssrc=video_ssrc)
        keyframe_requester = asyncio.ensure_future(
            _request_keyframes_until_done(pc, frame_future, video_ssrc, camera_id=device_name)
        )
        heartbeat = asyncio.ensure_future(_log_state_heartbeat(pc, frame_future, camera_id=device_name))
        try:
            frame = await asyncio.wait_for(frame_future, timeout=timeout)
        except asyncio.TimeoutError:
            await _log_inbound_video_stats(pc, camera_id=device_name)
            raise
        finally:
            keyframe_requester.cancel()
            heartbeat.cancel()
    finally:
        await pc.close()
        if media_session_id:
            sdm_client.stop_webrtc_stream(device_name, media_session_id)

    image = frame.to_ndarray(format="bgr24")
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise ValueError("Failed to JPEG-encode the captured WebRTC frame")
    return encoded.tobytes()


def capture_frame_via_webrtc(
    sdm_client: SdmClient,
    device_name: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    diagnostic_log_path: str | None = None,
) -> bytes:
    """Synchronous entry point -- runs its own asyncio event loop.

    Safe to call from a plain (non-async) Pub/Sub callback thread since each
    call gets a fresh loop; not meant for high-throughput use, just one
    frame per motion/person event.

    `diagnostic_log_path`: opt-in structured JSONL diagnostic log (see
    diagnostics.py) for `diagnose_webrtc.py` to feed to the diagnostic
    agent. None (default) disables it -- zero overhead, no file written.
    """
    set_diagnostic_log_path(diagnostic_log_path)
    try:
        return asyncio.run(_capture_frame_async(sdm_client, device_name, timeout))
    finally:
        if _diagnostic_writer is not None:
            _diagnostic_writer.close()

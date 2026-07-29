"""Standalone, local/on-demand diagnostic tool for the open Nest WebRTC
video-capture bug (see README.md's "Known limitation" section).

Runs a single WebRTC capture attempt against one configured camera with
structured diagnostic logging enabled, then feeds the resulting JSONL log to
`WebrtcDiagnosticAgent`, which writes a plain-language status report.

Not part of the deployed Container App image -- this imports
`surveil_core.agents` from the editable local install (`pip install -e
../../shared` from this folder's virtualenv, same as this component's
existing local-dev instructions) and authenticates to Azure OpenAI via the
developer's own `az login` session (DefaultAzureCredential), which needs the
"Cognitive Services OpenAI User" role on the deployed Azure OpenAI account --
grant it once with:

    az role assignment create --assignee <your-principal-id> \\
        --role "Cognitive Services OpenAI User" \\
        --scope <openai-account-resource-id>

Usage:
    OPENAI_ENDPOINT=https://<name>.openai.azure.com/ \\
    OPENAI_CHAT_DEPLOYMENT=chat \\
        python diagnose_webrtc.py <camera_id> [--timeout 60] [--output report.md]

<camera_id> is one of the labels configured in NEST_INGESTOR_CONFIG's
google_devices (see config.py).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

from auth import GoogleTokenManager
from config import get_config
from sdm_client import SdmClient
from webrtc_capture import DEFAULT_TIMEOUT_SECONDS, capture_frame_via_webrtc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nest_ingestor.diagnose")


def _resolve_device_name(camera_id: str) -> str:
    config = get_config()
    devices = config.devices()
    for device_name, label in devices.items():
        if label == camera_id:
            return device_name
    raise SystemExit(
        f"No configured device found for camera_id={camera_id!r}. "
        f"Configured labels: {sorted(devices.values())}"
    )


async def _run(camera_id: str, timeout: float, output: Path | None) -> None:
    from surveil_core.agents import WebrtcDiagnosticAgent, build_kernel

    endpoint = os.environ.get("OPENAI_ENDPOINT")
    if not endpoint:
        raise SystemExit("OPENAI_ENDPOINT must be set (see this script's module docstring for usage).")
    deployment_name = os.environ.get("OPENAI_CHAT_DEPLOYMENT", "chat")

    device_name = _resolve_device_name(camera_id)
    config = get_config()
    token_manager = GoogleTokenManager(
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
        refresh_token=config.google_refresh_token,
    )
    sdm_client = SdmClient(token_manager)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        log_path = Path(tmp.name)

    logger.info("Running WebRTC capture attempt against %s (device %s)", camera_id, device_name)
    try:
        capture_frame_via_webrtc(sdm_client, device_name, timeout=timeout, diagnostic_log_path=str(log_path))
        logger.info("Capture succeeded -- a frame was received. Diagnosing the session anyway for a full report.")
    except Exception:
        logger.exception("Capture attempt failed or timed out -- diagnosing the collected log")

    from azure.identity import DefaultAzureCredential

    kernel = build_kernel(endpoint=endpoint, deployment_name=deployment_name, credential=DefaultAzureCredential())
    agent = WebrtcDiagnosticAgent(kernel)
    report = await agent.diagnose(log_path)

    if output:
        output.write_text(report, encoding="utf-8")
        logger.info("Report written to %s", output)
    else:
        print(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("camera_id", help="Camera label as configured in NEST_INGESTOR_CONFIG's google_devices")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--output", type=Path, default=None, help="Write the report to this file instead of stdout")
    args = parser.parse_args()

    asyncio.run(_run(args.camera_id, args.timeout, args.output))


if __name__ == "__main__":
    sys.exit(main())

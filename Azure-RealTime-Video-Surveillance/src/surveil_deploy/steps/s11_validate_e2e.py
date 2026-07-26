from __future__ import annotations

import time

import httpx

from surveil_deploy.config import DeployConfig
from surveil_deploy.console import log_info, log_step, log_success, log_warning
from surveil_deploy.runner import run_json
from surveil_deploy.state import DeploymentState

STEP_NAME = "s11_validate_e2e"
STEP_TITLE = "End-to-end validation — capture -> analyze -> alert"

# The Function App's blob trigger here is the classic polling-based kind
# (not Event Grid) -- Azure documents discovery as taking "up to 10 minutes"
# in the worst case, and it really is that variable in practice: two
# consecutive test uploads during initial rollout took 4.5min and 6.5min
# respectively, so this is not a one-off cold-start fluke. 600s matches
# Microsoft's documented ceiling. If this still isn't enough headroom, the
# real fix is switching the Function's binding from the classic blob trigger
# to an Event Grid-based one (near-instant, no more polling latency) -- see
# docs/troubleshooting.md.
MAX_WAIT_SECONDS = 600
POLL_INTERVAL_SECONDS = 5
PROGRESS_LOG_INTERVAL_SECONDS = 30
TEST_CAMERA_ID = "e2e-smoke-test"


def _fetch_frame_upload_api_key(container_app_name: str, resource_group: str) -> str:
    # Fetched live rather than exposed as a Bicep deployment output -- ARM
    # output values are stored in deployment history, a bigger exposure
    # surface than a scoped secret-value read here.
    secrets = run_json([
        "az", "containerapp", "secret", "list",
        "--name", container_app_name, "--resource-group", resource_group,
        "--show-values", "-o", "json",
    ])
    for secret in secrets:
        if secret.get("name") == "frame-upload-api-key":
            return secret.get("value", "")
    return ""


def run(config: DeployConfig, state: DeploymentState) -> dict:
    log_step(11, 12, STEP_TITLE)

    fixture_path = config.source_dir / "tests" / "fixtures" / "person_test_frame.jpg"
    if not fixture_path.exists():
        log_warning(
            f"{fixture_path} not found — skipping the live E2E detection check. "
            "Generate a test frame with a person in it, e.g.:\n"
            "      ffmpeg -i sample_videos/swat-soldier-with-weapon-13884574-720p.mp4 "
            "-vframes 1 tests/fixtures/person_test_frame.jpg"
        )
        return {"e2e_validated": False}

    outputs = state.resource_outputs
    api_base_url = outputs.get("API_BASE_URL") or f"https://{outputs['CONTAINER_APP_FQDN']}"
    api_key = _fetch_frame_upload_api_key(outputs["CONTAINER_APP_NAME"], outputs["AZURE_RESOURCE_GROUP"])
    headers = {"X-Api-Key": api_key} if api_key else {}

    log_info(f"Uploading test frame to camera '{TEST_CAMERA_ID}'")
    with httpx.Client(timeout=30) as client:
        with open(fixture_path, "rb") as f:
            response = client.post(
                f"{api_base_url}/api/v1/frames",
                data={"camera_id": TEST_CAMERA_ID},
                files={"file": ("test.jpg", f, "image/jpeg")},
                headers=headers,
            )
        response.raise_for_status()
        blob_name = response.json()["blob_name"]
        log_info(f"Frame uploaded as {blob_name}; waiting for the Function to analyze it")

        start = time.monotonic()
        deadline = start + MAX_WAIT_SECONDS
        next_progress_log = start + PROGRESS_LOG_INTERVAL_SECONDS
        matching_event = None
        while time.monotonic() < deadline:
            events_response = client.get(f"{api_base_url}/api/v1/events", params={"limit": 20})
            events_response.raise_for_status()
            for event in events_response.json().get("events", []):
                if event.get("RowKey") and event.get("PartitionKey") == TEST_CAMERA_ID and event.get("FrameBlobName") == blob_name:
                    matching_event = event
                    break
            if matching_event:
                break
            now = time.monotonic()
            if now >= next_progress_log:
                elapsed = int(now - start)
                log_info(f"Still waiting for the blob trigger to fire ({elapsed}s elapsed, up to {MAX_WAIT_SECONDS}s expected on a cold Function App) ...")
                next_progress_log = now + PROGRESS_LOG_INTERVAL_SECONDS
            time.sleep(POLL_INTERVAL_SECONDS)

    if not matching_event:
        raise RuntimeError(
            f"No analysis event appeared for {blob_name} within {MAX_WAIT_SECONDS}s. "
            "Check the Function App logs (`az webapp log tail --name <func-app-name> --resource-group <rg>` -- "
            "the `az functionapp log tail` command does not exist)."
        )

    is_alert = bool(matching_event.get("IsAlert"))
    if is_alert:
        log_success(f"E2E validated: detection fired an alert (matched tags: {matching_event.get('MatchedTags')})")
    else:
        log_warning(
            "E2E pipeline ran end-to-end (frame analyzed and event recorded) but the test frame "
            "did not match the configured ALERT_WATCH_TAGS — this is not necessarily a failure, "
            "just confirms the detection path executed without raising an alert."
        )

    return {"e2e_validated": True, "e2e_alert_fired": is_alert}

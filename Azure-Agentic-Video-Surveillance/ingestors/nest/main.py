from __future__ import annotations

import logging
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from google.cloud import pubsub_v1

from auth import GoogleTokenManager
from backend_client import post_frame
from config import get_config
from pubsub_parser import CameraEvent, parse_camera_events
from sdm_client import SdmClient
from webrtc_capture import capture_frame_via_webrtc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("nest_ingestor")

# A single real-world doorbell press is commonly redelivered by Pub/Sub as
# 2-4 separate messages carrying the same eventId within a few seconds of
# each other (observed in production: same eventId, distinct message
# publishTimes). Without dedup, each redelivery spawns its own ~60s WebRTC
# capture session racing the others for the same underlying event -- wasted
# work, and each extra session is one more chance to eat into Google's
# rate limit. 5 minutes comfortably covers any realistic redelivery burst
# without leaking memory over this container's 24/7 lifetime.
_DEDUP_TTL_SECONDS = 300.0


class _RecentEventDeduper:
    """Thread-safe recently-seen set for (device_name, event_id) pairs."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._seen: dict[tuple[str, str], float] = {}

    def seen_before(self, key: tuple[str, str]) -> bool:
        now = time.monotonic()
        with self._lock:
            self._seen = {k: t for k, t in self._seen.items() if now - t < self._ttl}
            if key in self._seen:
                return True
            self._seen[key] = now
            return False


def main() -> None:
    config = get_config()
    watch_types = set(config.watch_event_types_list())
    devices = config.devices()

    token_manager = GoogleTokenManager(
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
        refresh_token=config.google_refresh_token,
    )
    sdm_client = SdmClient(token_manager)

    # Runs actual event processing (SDM API calls, WebRTC capture, backend
    # POST) off Pub/Sub's own callback thread pool. Without this, a slow
    # WebRTC capture (up to a minute) can occupy enough of Pub/Sub's limited
    # worker threads that the client can't promptly ack messages or keep its
    # streaming connection healthy -- observed as message redelivery and the
    # subscriber going silent under real-world testing with multiple cameras.
    worker_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="event-worker")
    deduper = _RecentEventDeduper(_DEDUP_TTL_SECONDS)

    def process_event(event: CameraEvent, camera_id: str) -> None:
        logger.info(
            "Camera event fired: %s camera=%s (eventId=%s, hasPreview=%s)",
            event.event_type,
            camera_id,
            event.event_id,
            bool(event.preview_url),
        )
        try:
            if event.preview_url:
                # Cheapest path: no extra command call needed.
                image_bytes = sdm_client.download_clip_preview_frame(event.preview_url)
            elif event.event_id:
                try:
                    image_url, image_token = sdm_client.generate_event_image(
                        event.device_name, event.event_id
                    )
                    image_bytes = sdm_client.download_event_image(image_url, image_token)
                except Exception:
                    # Expected on WebRTC-only devices without CameraClipPreview.
                    logger.info(
                        "GenerateImage unavailable for camera=%s, falling back to WebRTC capture",
                        camera_id,
                    )
                    image_bytes = capture_frame_via_webrtc(sdm_client, event.device_name)
            else:
                return
            post_frame(config.backend_url, camera_id, image_bytes, config.backend_api_key)
        except Exception:
            logger.exception("Failed to process camera event %s (camera=%s)", event.event_id, camera_id)

    def handle_message(message: pubsub_v1.subscriber.message.Message) -> None:
        # Ack immediately and hand off processing -- this callback must
        # return fast regardless of how long event processing takes.
        message.ack()
        logger.info("Pub/Sub message received (%d bytes)", len(message.data))
        try:
            events = parse_camera_events(message.data)
        except Exception:
            logger.exception("Failed to parse Pub/Sub message: %r", message.data)
            return
        for event in events:
            camera_id = devices.get(event.device_name)
            if camera_id is None:
                logger.info("Ignoring event for unconfigured device=%s", event.device_name)
                continue
            if event.event_type not in watch_types:
                logger.info("Ignoring unwatched event_type=%s", event.event_type)
                continue
            # ClipPreview events carry no eventId (see pubsub_parser) and
            # already take the cheap preview_url path in process_event, so
            # they're not part of the WebRTC-race problem this guards
            # against -- only dedup events that actually have one.
            if event.event_id and deduper.seen_before((event.device_name, event.event_id)):
                logger.info(
                    "Skipping duplicate redelivery of eventId=%s (camera=%s)", event.event_id, camera_id
                )
                continue
            worker_pool.submit(process_event, event, camera_id)

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = config.subscription_path()
    logger.info("Listening for Nest camera events on %s", subscription_path)
    logger.info("Watching cameras: %s", ", ".join(sorted(devices.values())) or "(none configured)")
    logger.info("Watching event types: %s", ", ".join(sorted(watch_types)))

    # Container orchestrators (Azure Container Apps, Kubernetes) send SIGTERM
    # on shutdown/redeploy, not SIGINT -- Python has no default translation
    # for SIGTERM into an exception, so without this handler a container
    # restart would kill in-flight worker_pool tasks instead of draining them
    # the way Ctrl-C (SIGINT/KeyboardInterrupt) already does below.
    def _handle_sigterm(signum, frame) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    future = subscriber.subscribe(subscription_path, callback=handle_message)
    try:
        future.result()
    except (KeyboardInterrupt, SystemExit):
        future.cancel()
        worker_pool.shutdown(wait=False)
        logger.info("Stopped.")


if __name__ == "__main__":
    main()

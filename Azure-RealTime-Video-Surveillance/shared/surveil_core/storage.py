"""Thin, keyless (managed-identity) wrappers around Blob / Queue / Table storage.

All clients authenticate with `azure.identity` credentials (DefaultAzureCredential
in Azure, AzureCliCredential for local dev) — no storage account keys are ever
used, matching the "no hardcoded secrets" fix called out in docs/architecture.md.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from azure.core.credentials import TokenCredential
from azure.data.tables import TableClient
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.queue import QueueClient, TextBase64EncodePolicy, TextBase64DecodePolicy

from surveil_core.models import AlertMessage, SurveillanceEvent

FRAMES_CONTAINER = "frames"
EVENTS_CONTAINER = "events"
CLIPS_CONTAINER = "clips"
ALERTS_QUEUE = "alerts"
EVENTS_TABLE = "events"
AUDIT_TABLE = "audit"


class SurveillanceStorage:
    def __init__(self, account_url: str, credential: TokenCredential) -> None:
        self._blob_service = BlobServiceClient(account_url=account_url, credential=credential)
        queue_account_url = account_url.replace(".blob.", ".queue.")
        table_account_url = account_url.replace(".blob.", ".table.")
        self._alerts_queue = QueueClient(
            account_url=queue_account_url,
            queue_name=ALERTS_QUEUE,
            credential=credential,
            message_encode_policy=TextBase64EncodePolicy(),
            message_decode_policy=TextBase64DecodePolicy(),
        )
        self._events_table = TableClient(
            endpoint=table_account_url,
            table_name=EVENTS_TABLE,
            credential=credential,
        )
        self._audit_table = TableClient(
            endpoint=table_account_url,
            table_name=AUDIT_TABLE,
            credential=credential,
        )

    # ---- frames ----------------------------------------------------------

    def upload_frame(self, camera_id: str, blob_name: str, image_bytes: bytes) -> str:
        container = self._blob_service.get_container_client(FRAMES_CONTAINER)
        blob = container.get_blob_client(blob_name)
        blob.upload_blob(
            image_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type="image/jpeg"),
            metadata={"camera_id": camera_id},
        )
        return blob.url

    def download_frame(self, blob_name: str) -> bytes:
        container = self._blob_service.get_container_client(FRAMES_CONTAINER)
        return container.get_blob_client(blob_name).download_blob().readall()

    def upload_annotated_frame(self, blob_name: str, image_bytes: bytes) -> str:
        container = self._blob_service.get_container_client(EVENTS_CONTAINER)
        blob = container.get_blob_client(blob_name)
        blob.upload_blob(
            image_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type="image/jpeg"),
        )
        return blob.url

    # ---- clips -------------------------------------------------------------

    def upload_clip(self, camera_id: str, blob_name: str, video_bytes: bytes, content_type: str) -> str:
        container = self._blob_service.get_container_client(CLIPS_CONTAINER)
        blob = container.get_blob_client(blob_name)
        blob.upload_blob(
            video_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
            metadata={"camera_id": camera_id},
        )
        return blob.url

    def download_clip(self, blob_name: str) -> tuple[bytes, str]:
        container = self._blob_service.get_container_client(CLIPS_CONTAINER)
        blob = container.get_blob_client(blob_name)
        downloaded = blob.download_blob()
        content_type = downloaded.properties.content_settings.content_type or "video/webm"
        return downloaded.readall(), content_type

    def list_recent_clips(self, limit: int = 50) -> list[dict]:
        # camera_id is read from the blob name's path prefix ("{camera_id}/{file}"),
        # not blob metadata -- list_blobs() doesn't fetch metadata unless
        # explicitly requested (include=["metadata"], an extra round-trip cost),
        # and the path prefix is already a structurally guaranteed source of
        # truth (see _blob_name() in routes/clips.py).
        container = self._blob_service.get_container_client(CLIPS_CONTAINER)
        blobs = sorted(
            container.list_blobs(),
            key=lambda b: b.last_modified,
            reverse=True,
        )[:limit]
        return [
            {
                "camera_id": b.name.split("/", 1)[0] if "/" in b.name else "",
                "blob_name": b.name,
                "last_modified": b.last_modified.isoformat() if b.last_modified else "",
            }
            for b in blobs
        ]

    # ---- events table ------------------------------------------------------

    def save_event(self, event: SurveillanceEvent) -> None:
        entity = {
            "PartitionKey": event.camera_id,
            "RowKey": event.event_id,
            "FrameBlobName": event.frame_blob_name,
            "CapturedAt": event.captured_at.isoformat(),
            "AnalyzedAt": event.analyzed_at.isoformat(),
            "Caption": event.caption or "",
            "Detections": event.model_dump_json(include={"detections"}),
            "IsAlert": event.is_alert,
            "MatchedTags": json.dumps(event.matched_tags),
            "Severity": event.severity or "",
        }
        self._events_table.upsert_entity(entity)

    def list_recent_events(self, limit: int = 50) -> list[dict]:
        # Table Storage has no ORDER BY -- entities come back ordered by
        # PartitionKey then RowKey, not by time. Fetching only the first page
        # would silently skip whole camera partitions once earlier-sorting
        # partition keys (alphabetically) fill the page, so every entity must
        # be scanned before sorting by AnalyzedAt and trimming to `limit`.
        results = [dict(entity) for entity in self._events_table.list_entities()]
        results.sort(key=lambda e: e.get("AnalyzedAt", ""), reverse=True)
        return results[:limit]

    # ---- audit trail ---------------------------------------------------------

    def log_audit_event(self, actor: str, action: str, details: str = "") -> None:
        now = datetime.now(timezone.utc)
        entity = {
            "PartitionKey": now.strftime("%Y-%m-%d"),
            "RowKey": str(uuid.uuid4()),
            "Actor": actor,
            "Action": action,
            "Details": details,
            "Timestamp": now.isoformat(),
        }
        self._audit_table.upsert_entity(entity)

    def list_recent_audit_events(self, limit: int = 50) -> list[dict]:
        entities = self._audit_table.list_entities(results_per_page=limit)
        results = []
        for page in entities.by_page():
            for entity in page:
                results.append(dict(entity))
                if len(results) >= limit:
                    return sorted(results, key=lambda e: e.get("Timestamp", ""), reverse=True)
        return sorted(results, key=lambda e: e.get("Timestamp", ""), reverse=True)

    # ---- alerts queue ------------------------------------------------------

    def enqueue_alert(self, alert: AlertMessage) -> None:
        self._alerts_queue.send_message(alert.model_dump_json())

    def receive_alerts(self, max_messages: int = 8):
        return self._alerts_queue.receive_messages(messages_per_page=max_messages)

    def delete_alert_message(self, message) -> None:
        self._alerts_queue.delete_message(message)

    def ensure_resources(self) -> None:
        """Idempotently create containers/queue/table if missing (used by smoke tests / local dev)."""
        for name in (FRAMES_CONTAINER, EVENTS_CONTAINER, CLIPS_CONTAINER):
            container = self._blob_service.get_container_client(name)
            if not container.exists():
                container.create_container()
        if not self._queue_exists():
            self._alerts_queue.create_queue()
        try:
            self._events_table.create_table()
        except Exception:
            pass
        try:
            self._audit_table.create_table()
        except Exception:
            pass

    def _queue_exists(self) -> bool:
        try:
            self._alerts_queue.get_queue_properties()
            return True
        except Exception:
            return False


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

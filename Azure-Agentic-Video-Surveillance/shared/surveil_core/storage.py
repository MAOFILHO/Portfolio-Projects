"""Thin, keyless (managed-identity) wrappers around Blob / Queue / Table storage.

All clients authenticate with `azure.identity` credentials (DefaultAzureCredential
in Azure, AzureCliCredential for local dev) — no storage account keys are ever
used, matching the "no hardcoded secrets" fix called out in docs/architecture.md.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from azure.core.credentials import TokenCredential
from azure.data.tables import TableClient
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.queue import QueueClient, TextBase64EncodePolicy, TextBase64DecodePolicy

from surveil_core.models import AlertMessage, SurveillanceEvent

logger = logging.getLogger("surveil_core.storage")

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

    def query_events(
        self,
        camera_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        is_alert: bool | None = None,
        severity: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        continuation_token: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Server-side filtered query, for the NL Event Query Agent and any
        future feature that needs more than "give me everything" -- unlike
        `list_recent_events` above, this uses OData filters so Table Storage
        only returns matching partitions/rows instead of a full table scan.

        `parameters=` (rather than interpolating values into `query_filter`
        directly) is azure-data-tables' own parameterized-query mechanism --
        it substitutes `@name` placeholders safely, so this is not vulnerable
        to OData filter injection the way naive string interpolation would
        be.

        `tags` is filtered client-side after the fact: `MatchedTags` is
        stored as an opaque JSON-string column, which Table Storage's OData
        filters can't inspect (no substring/array-contains support).
        """
        filters: list[str] = []
        params: dict[str, object] = {}
        if camera_id:
            filters.append("PartitionKey eq @camera_id")
            params["camera_id"] = camera_id
        if start:
            filters.append("AnalyzedAt ge @start")
            params["start"] = start.isoformat()
        if end:
            filters.append("AnalyzedAt le @end")
            params["end"] = end.isoformat()
        if is_alert is not None:
            filters.append("IsAlert eq @is_alert")
            params["is_alert"] = is_alert
        if severity:
            filters.append("Severity eq @severity")
            params["severity"] = severity

        if filters:
            query_filter = " and ".join(filters)
            logger.info("query_events filter=%r params=%r limit=%r", query_filter, params, limit)
            entities = self._events_table.query_entities(
                query_filter=query_filter, parameters=params, results_per_page=limit
            )
        else:
            query_filter = None
            entities = self._events_table.list_entities(results_per_page=limit)

        pages = entities.by_page(continuation_token=continuation_token)
        try:
            page = next(pages, None)
        except Exception:
            # query_entities()/list_entities() only build the lazy ItemPaged;
            # the actual HTTP request (and thus any "InvalidInput" rejection)
            # happens here, at first iteration -- log the exact filter/params
            # that triggered it, since Azure Monitor's own HTTP auto-tracing
            # redacts $filter query-string contents as sensitive data.
            logger.exception("query_events filter=%r params=%r rejected by Table Storage", query_filter, params)
            raise
        results = [dict(entity) for entity in page] if page is not None else []

        if tags:
            wanted = {t.strip().lower() for t in tags if t.strip()}
            results = [
                r
                for r in results
                if wanted & {t.lower() for t in json.loads(r.get("MatchedTags") or "[]")}
            ]

        results.sort(key=lambda e: e.get("AnalyzedAt", ""), reverse=True)
        return results, pages.continuation_token

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
            # NOT "Timestamp" -- that's a Table Storage system-reserved
            # property (service-managed for optimistic concurrency, exposed
            # via TableEntity.metadata, not as a regular dict key). Writing a
            # custom "Timestamp" value is silently absorbed by the service
            # and never comes back from `dict(entity)` -- confirmed live,
            # this produced "Invalid Date" in the Audit Trail UI.
            "LoggedAt": now.isoformat(),
        }
        self._audit_table.upsert_entity(entity)

    def list_recent_audit_events(self, limit: int = 50) -> list[dict]:
        # Same reasoning as list_recent_events above: Table Storage orders
        # entities by PartitionKey/RowKey, not time, so returning as soon as
        # `limit` entities are collected (in that raw order) can silently
        # drop genuinely recent entries once the table holds more than one
        # page -- every entity must be scanned before sorting and trimming.
        results = [dict(entity) for entity in self._audit_table.list_entities()]
        results.sort(key=lambda e: e.get("LoggedAt", ""), reverse=True)
        return results[:limit]

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

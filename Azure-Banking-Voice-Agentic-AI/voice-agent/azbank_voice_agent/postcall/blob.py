"""The real transcript store: redacted turns to Azure Blob Storage, by managed identity (Phase 8).

Takes **already-redacted** turns and nothing else -- redaction is the pipeline's job and happens
first (ADR-007). One immutable blob per call, `<correlation_id>.json`, never overwritten. The content
says `agent_turns`, because that is all it is (D14): caller speech is never transcribed here.

No connection string, no account key, no SAS -- `DefaultAzureCredential`, exactly as the call-record
store. `azure-storage-blob` is imported lazily inside the one constructor that needs it.

**What is and is not verified.** The constructor and `upload_blob(..., overwrite=)` signatures were
read off the pinned package (`azure-storage-blob==12.30.2`) by introspection on 2026-09-19. Behaviour
against real Storage is unverified until the first live call, the standing the Table client had until
its first real deploy: a role assignment returning 200 OK proves creation, not access.
"""
import json

from ..call_records import is_storable_id

#: The one container transcripts live in. `infra/modules/call-records-store.bicep` creates it.
TRANSCRIPT_CONTAINER = "transcripts"


class BlobTranscriptStore:
    """`container_client` is injected so the write path is driven with no network, as the Table
    store takes its table client. `from_account_url` is what production uses."""

    def __init__(self, container_client):
        self._container = container_client

    @classmethod
    def from_account_url(cls, account_url, credential, container=TRANSCRIPT_CONTAINER):
        from azure.storage.blob.aio import ContainerClient

        return cls(ContainerClient(account_url, container, credential=credential))

    async def aclose(self):
        await self._container.close()

    async def write(self, correlation_id, turns):
        # The pipeline replaces an unsafe id before it gets here; this is the store refusing on its
        # own account, because a path separator would put the blob somewhere the container never meant.
        if not is_storable_id(correlation_id):
            raise ValueError("correlation id is not a safe blob name")
        name = f"{correlation_id}.json"
        await self._container.upload_blob(
            name, json.dumps({"agent_turns": list(turns)}), overwrite=False
        )
        return name

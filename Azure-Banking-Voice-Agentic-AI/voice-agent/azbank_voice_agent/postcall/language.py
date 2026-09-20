"""The real redactor: Azure AI Language's Conversation PII job API, by managed identity (Phase 8).

Plain REST over `httpx`, not an SDK: the only stable SDK that could reach this API dropped it, and
the API has no stable SDK (docs/phase8/research-postcall-adapters.md, Q1d). Shapes are from the
`2024-11-01` GA spec; that note cites each one.

The agent's turns go up as one text conversation, come back as one job result, and are matched to
what was sent **by item id, never by position**. Then every string gets the deterministic number scrub
(`scrub.py`) on top, because the service does not promise to catch a bare digit string.

**Anything unexpected raises.** ADR-007: the pipeline turns a raise into "no transcript" and never
into a fallback to the raw text, so this module's whole job on a surprise is to refuse to return
anything. It logs nothing at all -- a raw turn must not reach a log line, and an exception's message
can echo one (B2).

**The bearer token goes to the Language host and nowhere else.** The poll URL comes from the
service's `Operation-Location` header, and it is followed verbatim -- but only if it is https on the
configured host, so a hostile or mistaken header cannot collect the token.

Not verified against the live service until the first live call: the fixtures in the tests pin the
shape the docs describe, which is not the same as the service returning it.
"""
import asyncio
from urllib.parse import urlsplit

from .scrub import scrub_numbers

API_VERSION = "2024-11-01"
JOBS_PATH = "/language/analyze-conversations/jobs"

#: Documented per-item limit (data-limits page): 1,000 characters per conversation item. A longer
#: turn fails closed rather than being split, because a split could cut a PII span in two.
MAX_ITEM_CHARS = 1000

#: Entra scope for Language, from the OAuth2 declaration in both Language OpenAPI specs.
TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"

_TERMINAL = frozenset({"succeeded", "partiallyCompleted", "failed", "cancelled"})


class RedactionError(Exception):
    """The service's answer was not something safe to return. The message carries no turn text."""


class LanguagePIIRedactor:
    """`http` is a shared `httpx.AsyncClient` and `token_provider` an async callable returning a
    bearer token (`azure.identity.aio.get_bearer_token_provider`); both are injected so the whole
    round trip runs against a scripted transport in tests."""

    def __init__(self, endpoint, http, token_provider, poll_interval_seconds=1.0):
        parts = urlsplit(endpoint)
        if parts.scheme != "https" or not parts.netloc:
            raise ValueError("the Language endpoint must be an https account URL")
        self._host = parts.netloc
        self._base = f"https://{parts.netloc}"
        self._http = http
        self._token_provider = token_provider
        self._poll_interval = poll_interval_seconds

    async def redact(self, turns):
        sendable = [(index, turn) for index, turn in enumerate(turns) if turn.strip()]
        result = ["" for _ in turns]
        if not sendable:
            return result
        if any(len(turn) > MAX_ITEM_CHARS for _, turn in sendable):
            raise ValueError("a turn is longer than the service's item limit")

        conversation_id = "postcall"
        redacted_by_id = await self._run_job(conversation_id, [(str(i), turn) for i, turn in sendable])
        for index, _ in sendable:
            result[index] = scrub_numbers(redacted_by_id[str(index)])
        return result

    async def _headers(self):
        return {"Authorization": f"Bearer {await self._token_provider()}"}

    async def _run_job(self, conversation_id, items):
        body = {
            "displayName": "postcall-pii",
            "analysisInput": {"conversations": [{
                "id": conversation_id,
                "language": "en",
                "modality": "text",
                "conversationItems": [
                    {"id": item_id, "participantId": "agent", "role": "agent", "text": text}
                    for item_id, text in items
                ],
            }]},
            "tasks": [{
                "taskName": "pii",
                "kind": "ConversationalPIITask",
                "parameters": {
                    "modelVersion": "latest",
                    "piiCategories": ["All"],
                    # The Conversation task defaults this to false; a banking transcript should
                    # not sit in the service's own logs by default.
                    "loggingOptOut": True,
                },
            }],
        }
        submitted = await self._http.post(
            f"{self._base}{JOBS_PATH}", params={"api-version": API_VERSION},
            json=body, headers=await self._headers(),
        )
        submitted.raise_for_status()
        poll_url = self._trusted_poll_url(submitted.headers.get("Operation-Location"))

        while True:
            polled = await self._http.get(poll_url, headers=await self._headers())
            polled.raise_for_status()
            state = polled.json()
            if state.get("status") in _TERMINAL:
                return self._redacted_by_id(state, conversation_id, {item_id for item_id, _ in items})
            await asyncio.sleep(self._poll_interval)

    def _trusted_poll_url(self, location):
        parts = urlsplit(location or "")
        if parts.scheme != "https" or parts.netloc != self._host:
            raise RedactionError("the poll URL is missing or is not on the Language host")
        return location

    @staticmethod
    def _redacted_by_id(state, conversation_id, expected_ids):
        if state.get("status") != "succeeded" or state.get("errors"):
            raise RedactionError("the job did not succeed")
        tasks = (state.get("tasks") or {}).get("items") or []
        if len(tasks) != 1 or tasks[0].get("status") != "succeeded":
            raise RedactionError("the task did not succeed")
        results = tasks[0].get("results") or {}
        if results.get("errors"):
            raise RedactionError("the service reported per-conversation errors")
        conversations = results.get("conversations") or []
        if len(conversations) != 1 or conversations[0].get("id") != conversation_id:
            raise RedactionError("the results are not for the conversation that was sent")

        redacted = {}
        for item in conversations[0].get("conversationItems") or []:
            item_id = item.get("id")
            text = (item.get("redactedContent") or {}).get("text")
            if item_id in redacted or not isinstance(text, str):
                raise RedactionError("an item is duplicated or carries no redacted text")
            redacted[item_id] = text
        if set(redacted) != expected_ids:
            raise RedactionError("the returned items are not the items that were sent")
        return redacted

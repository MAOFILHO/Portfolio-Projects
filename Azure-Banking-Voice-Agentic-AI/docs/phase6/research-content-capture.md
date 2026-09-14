# Phase 6 research — content-capture defaults (open items 15 and 16)

Pure documentation research on `PROJECT_STATE.md` open items 15 and 16, both raised in
`docs/phase6/exit-criteria.md` (D8, criterion 3, criterion 4) and both blocking on GitHub issues
`#61`/`#62`. **No application code was written or changed for this task.** All claims below are
sourced from live fetches of primary sources performed **2026-09-13** (URL + fetch date next to
every claim). Where a primary source does not settle something, it is marked **OPEN QUESTION**
rather than filled in by inference.

**Scoping, pinned versions**:

- `voice-agent/pyproject.toml` pins `fastapi==0.115.14` and `httpx>=0.27` (no upper bound). No local
  venv or `pip freeze` record exists in this worktree to read the resolved `httpx` version directly
  (`voice-agent/Dockerfile` writes `installed-versions.txt` only inside the built container image,
  which was not available to this research). PyPI's registry metadata for `httpx`
  ([pypi.org/pypi/httpx/json](https://pypi.org/pypi/httpx/json), fetched 2026-09-13) shows the
  newest release satisfying `>=0.27` is **`0.28.1`** (released 2024-12-06 and still latest as of this
  fetch), so that is the version any real build resolves to and the version this note pins to.
  `requests` is **not a dependency of this project at all** — `voice-agent/pyproject.toml` has no
  `requests` entry anywhere (runtime, dev, or test extras).
- The three instrumentation packages in question — `opentelemetry-instrumentation-fastapi`,
  `-httpx`, `-requests` — ship from one monorepo
  ([`open-telemetry/opentelemetry-python-contrib`](https://github.com/open-telemetry/opentelemetry-python-contrib))
  and release in lockstep. PyPI's registry metadata for all three
  ([pypi.org/pypi/opentelemetry-instrumentation-fastapi/json](https://pypi.org/pypi/opentelemetry-instrumentation-fastapi/json),
  [.../opentelemetry-instrumentation-httpx/json](https://pypi.org/pypi/opentelemetry-instrumentation-httpx/json),
  [.../opentelemetry-instrumentation-requests/json](https://pypi.org/pypi/opentelemetry-instrumentation-requests/json),
  all fetched 2026-09-13) shows the current release of all three is **`0.65b0`** (fastapi's package
  released 2026-07-16). The FastAPI package's own `requires_dist` pins `fastapi~=0.92` — i.e.
  `>=0.92,<1.0` — which this project's `0.115.14` satisfies. The httpx package's `requires_dist`
  accepts `httpx>=0.18.0` under its `instruments-any` extra, which `0.28.1` satisfies. **This
  project has no version of any of the three instrumentations installed today** (Phase 6 has not
  begun); `0.65b0` is what a real install would resolve to as of this fetch, and this note is pinned
  to that exact release, quoting its source directly from GitHub `main` (the tag for `0.65b0` was not
  separately diffed against `main`, following the same practice Phase 4's note used and stated
  explicitly for a different package — no discrepancy was found or expected for the narrow functions
  quoted below, which are old, stable code paths in this repo).
- Azure OpenAI resource: `aoai-azure-banking-voice-cc`, Canada Central, deployment
  `gpt-realtime-mini`, realtime (speech-to-speech, WebSocket) API — **not** the REST
  completions/chat-completions endpoint.

---

## 1. Open item 16 — do the FastAPI/httpx/requests OTel instrumentations capture bodies by default?

### 1a. `opentelemetry-instrumentation-fastapi` 0.65b0 — no such capability exists, on or off

The public entry point is `FastAPIInstrumentor.instrument_app`:

> ```python
> @staticmethod
> def instrument_app(
>     app: fastapi.FastAPI,
>     server_request_hook: ServerRequestHook = None,
>     client_request_hook: ClientRequestHook = None,
>     client_response_hook: ClientResponseHook = None,
>     tracer_provider: TracerProvider | None = None,
>     meter_provider: MeterProvider | None = None,
>     excluded_urls: str | None = None,
>     http_capture_headers_server_request: list[str] | None = None,
>     http_capture_headers_server_response: list[str] | None = None,
>     http_capture_headers_sanitize_fields: list[str] | None = None,
>     exclude_spans: list[Literal["receive", "send"]] | None = None,
> ) -> None:
> ```
> — [`opentelemetry-python-contrib`, `instrumentation/opentelemetry-instrumentation-fastapi/src/opentelemetry/instrumentation/fastapi/__init__.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/opentelemetry-instrumentation-fastapi/src/opentelemetry/instrumentation/fastapi/__init__.py), fetched 2026-09-13 (`main`)

**There is no `capture_request_body`, `capture_response_body`, or equivalent parameter, and the word
"body" does not appear anywhere in this module.** The only content-adjacent knobs are the three hook
parameters and the three header-capture list parameters — all `None`/off by default, and headers are
opt-in **by name**, not a blanket capture (`http_capture_headers_server_request` etc. — see docs
below).

The hooks are ASGI-level and receive metadata, not bodies. From the type-alias definitions used by
the underlying ASGI instrumentation FastAPI's instrumentor wraps:

> `ServerRequestHook`: `Callable[[Span, _Scope], None] | None` — passed a server span and the ASGI
> **scope** mapping (method, path, headers, client address — connection metadata) for every incoming
> request.
> `ClientRequestHook` / `ClientResponseHook`: `Callable[[Span, _Scope, _Message], None] | None` —
> called with the span, the ASGI scope, and the ASGI **event** message dict, invoked when the
> application's `receive`/`send` callables are exercised.
> — [`opentelemetry-python-contrib`, `instrumentation/opentelemetry-instrumentation-asgi/src/opentelemetry/instrumentation/asgi/types.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/opentelemetry-instrumentation-asgi/src/opentelemetry/instrumentation/asgi/types.py), fetched 2026-09-13 (`main`)

The published usage docs describe the same three hooks with the same scope: `server_request_hook` is
"passed a server span and ASGI scope object for every incoming request"; `client_request_hook` /
`client_response_hook` are "called with the internal span, and ASGI scope and event when the method
`receive`/`send` is called" —
[`opentelemetry-python-contrib` FastAPI instrumentation docs](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html), fetched 2026-09-13. The
documented configurable environment variables on that same page are `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS`
/ `OTEL_PYTHON_EXCLUDED_URLS` and the three `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_*` variables
(request headers, response headers, sanitize-fields) — **no body-capture variable is documented,
because none exists.**

**Important nuance, stated plainly because it matters to how "no capability" is read**: the ASGI
`receive` event for an HTTP request *does* carry the raw body bytes in its `message["body"]` field —
that is simply what the ASGI spec puts there. So a `client_request_hook` a developer **writes
themselves** could reach in and pull `message["body"]` out and call `span.set_attribute(...)` on it.
**That is real, but it is not a default and not a flag** — it requires someone to write that specific
line of application code; the instrumentation itself does nothing with the body at any point in its
own source. This is the same shape Phase 4's research found for the GenAI instrumentation's
`request_hook`/`response_hook` pattern generally: hooks are an opt-in extension point, not a
capture toggle.

**Verdict: default off, and there is no opt-in flag to turn on — only a hand-written hook could ever
put body content into a span, and none is written.**

### 1b. `opentelemetry-instrumentation-httpx` 0.65b0 — same verdict, and the hook objects can't even see a body without extra work

The hook objects passed to `request_hook`/`response_hook` are typed tuples carrying connection
metadata only:

> ```python
> class RequestInfo(typing.NamedTuple):
>     method: bytes
>     url: httpx.URL | tuple[bytes, bytes, int | None, bytes]
>     headers: httpx.Headers | None
>     stream: httpx.SyncByteStream | httpx.AsyncByteStream | None
>     extensions: MutableMapping[str, typing.Any] | None
>
> class ResponseInfo(typing.NamedTuple):
>     status_code: int
>     headers: httpx.Headers | None
>     stream: httpx.SyncByteStream | httpx.AsyncByteStream
>     extensions: MutableMapping[str, typing.Any] | None
> ```
> — [`opentelemetry-python-contrib`, `instrumentation/opentelemetry-instrumentation-httpx/src/opentelemetry/instrumentation/httpx/__init__.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/opentelemetry-instrumentation-httpx/src/opentelemetry/instrumentation/httpx/__init__.py), fetched 2026-09-13 (`main`)

Neither tuple has a `body`/`content` field; `stream` is the raw (unconsumed) byte stream object. The
module documents the hooks as receiving "the raw arguments provided to the transport layer" /"the raw
return values from the transport layer" — connection-layer objects, not decoded content. **The word
"body" does not appear anywhere in this file.** Unlike the `requests` case below, reading the body
from `stream` inside a hand-written hook would mean consuming the actual request/response byte
stream out from under the transport — a materially more invasive and riskier thing to do than
reading an already-buffered attribute, which is presumably why no such convenience exists here even
as a documented pattern.

**Verdict: default off; no `capture_request_body`/`capture_response_body` parameter exists; the hook
objects don't expose a body at all without the caller consuming the transport stream themselves.**

### 1c. `opentelemetry-instrumentation-requests` 0.65b0 — default off, but the hook objects are one line away from a body

`RequestsInstrumentor._instrument`'s own docstring enumerates every keyword argument it accepts:

> ```
> Instruments requests module
>
> Args:
>     **kwargs: Optional arguments
>         ``tracer_provider``: a TracerProvider, defaults to global
>         ``request_hook``: An optional callback invoked right after span creation.
>         ``response_hook``: An optional callback invoked before span finishes.
>         ``excluded_urls``: A string containing comma-delimited list of regexes
>         ``duration_histogram_boundaries``: A list of float values
> ```
> — [`opentelemetry-python-contrib`, `instrumentation/opentelemetry-instrumentation-requests/src/opentelemetry/instrumentation/requests/__init__.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/opentelemetry-instrumentation-requests/src/opentelemetry/instrumentation/requests/__init__.py), fetched 2026-09-13 (`main`)

with the hook type aliases:

> ```python
> _RequestHookT = Callable[[Span, PreparedRequest], None] | None
> _ResponseHookT = Callable[[Span, PreparedRequest, Response], None] | None
> ```
> — same file, fetched 2026-09-13

**No `capture_request_body`/`capture_response_body` parameter exists here either, and "body" does not
appear in the file.** The difference from httpx: `requests.PreparedRequest` and `requests.Response`
are `requests`' own fully-buffered objects, which already expose `.body` and `.content`/`.text`
without the hook doing any stream consumption — so a hand-written `request_hook` here is a
materially smaller lift than httpx's. That is still a fact about how easy a *hand-written* hook would
be, not about anything this instrumentation does by default. **This project has no `requests`
dependency today**, so this package would only become relevant if a future ticket added one.

**Verdict: default off; no capability exists to turn it on; a hand-written hook is easier to write
than httpx's but still requires someone to write it.**

### 1d. The one default-on content risk this research found — and it is not a body

Reading the FastAPI/ASGI instrumentation source further (because "does it capture bodies" is not the
same question as "is there a content leak"): the ASGI instrumentation that underlies FastAPI's spans
builds its `http.url` span attribute by **appending the raw, URL-decoded query string to the URL, by
default, with no opt-in required**:

> ```python
> query_string = scope.get("query_string")
> if query_string and http_url:
>     if isinstance(query_string, bytes):
>         query_string = query_string.decode("utf8")
>     http_url += "?" + urllib.parse.unquote(query_string)
> ```
> — [`opentelemetry-python-contrib`, `instrumentation/opentelemetry-instrumentation-asgi/src/opentelemetry/instrumentation/asgi/__init__.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/opentelemetry-instrumentation-asgi/src/opentelemetry/instrumentation/asgi/__init__.py), fetched 2026-09-13 (`main`)

This value does pass through a `redact_url()` function before being set on the span, but that
function's default redaction list is narrow and cloud-signature-specific, not general-purpose:

> ```python
> def redact_url(url: str) -> str:
>     """Redact sensitive data from the URL, including credentials and query parameters."""
>     url = remove_url_credentials(url)
>     url = redact_query_parameters(url)
>     return url
>
> PARAMS_TO_REDACT = ["AWSAccessKeyId", "Signature", "sig", "X-Goog-Signature"]
> ```
> — [`opentelemetry-python-contrib`, `util/opentelemetry-util-http/src/opentelemetry/util/http/__init__.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/util/opentelemetry-util-http/src/opentelemetry/util/http/__init__.py), fetched 2026-09-13 (`main`)

None of those four names would match a hypothetical `incomingCallContext=` or phone-number query
parameter. **This is a real, default-on content-capture path — it is just not a "body" path,** and
D8/D15 should account for it if any future route ever puts caller-identifying data in a query
string. §2 below establishes that the current `/api/incoming-call` handler does not.

### 1e. Item 16 — table and verdict

| instrumentation | body capture, default | opt-in flag exists? | what a hand-written hook receives |
|---|---|---|---|
| `opentelemetry-instrumentation-fastapi` 0.65b0 | **Off — no capability at all** | No | ASGI scope / event dict (metadata only; body bytes are technically reachable inside the raw ASGI `receive` message but nothing reads them) |
| `opentelemetry-instrumentation-httpx` 0.65b0 | **Off — no capability at all** | No | `RequestInfo`/`ResponseInfo` (method, URL, headers, raw unconsumed stream, extensions — no body field) |
| `opentelemetry-instrumentation-requests` 0.65b0 | **Off — no capability at all** | No | `PreparedRequest`/`Response` (buffered, so `.body`/`.content` are one line away, but nothing reads them by default) |

**Item 16 is SETTLED.** None of the three instrumentations captures request or response bodies by
default, and none exposes a `capture_request_body`/`capture_response_body`-style opt-in flag —
that capability does not exist in any of the three packages at the pinned release (`0.65b0`).
Enabling `opentelemetry-instrumentation-fastapi` on the ACS webhook would **not** place the raw POST
body — and therefore not `incomingCallContext` — into any span attribute, span-event attribute, or
log record through any documented default or opt-in mechanism these packages provide. The one
default-on content risk found is unrelated to bodies: the full request URL, **including its query
string**, lands in the `http.url` span attribute unless the route in question is excluded or the
value happens to match one of four cloud-signature parameter names. §2 addresses whether that risk
reaches this project's actual webhook.

---

## 2. Does the ACS webhook route give the query string / header / path risk anywhere to land?

`voice-agent/azbank_voice_agent/app.py:175-188`:

```python
@app.post("/api/incoming-call")
async def incoming_call(request: Request):
    events = await request.json()
    for event in events:
        if event.get("eventType") == "Microsoft.EventGrid.SubscriptionValidationEvent":
            ...
        if event.get("eventType") == "Microsoft.Communication.IncomingCall":
            incoming_call_context = event["data"]["incomingCallContext"]
            correlation_id = event["data"].get("correlationId")
```

Three facts, read directly from this handler:

1. **The route is a fixed literal path with no path parameters** — `/api/incoming-call`, nothing
   templated. `http.route` would just be that literal string; no caller data can ride the path.
2. **Nothing in the handler reads `request.query_params` or any header.** ACS's Event Grid webhook
   delivery for this event, as this project actually uses it, is a bare `POST` whose entire payload
   is the JSON array body — `incoming_call_context` and `correlation_id` are read out of
   `event["data"]`, i.e. **exclusively from the POST body**, never from the URL or a header.
3. Therefore §1d's query-string risk **does not reach this handler as written** — there is no query
   string to redact or fail to redact, because ACS's webhook shape for this event never puts anything
   in one. The risk in §1d is real for FastAPI instrumentation in general and worth a line in D15's
   allowlist discipline or an `excluded_urls` note if any future route changes this, but it is not a
   live gap in the current code.

Combined with §1's finding that no instrumentation captures the body by default: **the caller's
phone number, if `incomingCallContext` encodes it, has no default-on or default-off-but-flaggable
path into telemetry via any of these three packages, given how this handler is actually written
today.** D8's own framing — "the caller's phone number is protected by never acquiring it, the scan
is the net" — is not weakened by turning FastAPI instrumentation on, as far as these three packages'
documented behavior goes.

---

## 3. Open item 15 — what does the `RequestResponse` diagnostic-log category actually contain?

### 3a. The category exists; its content is undocumented in every Microsoft primary source fetched

The canonical Azure Monitor reference table for this resource type lists `RequestResponse` with an
**empty** "Example queries" column and no per-category description or schema at all:

> | Category | Costs to export | Log table | ... | Example queries |
> | --- | --- | --- | --- | --- |
> | Audit | No | AzureDiagnostics | ... | |
> | AzureOpenAIRequestUsage | Yes | AzureDiagnostics | ... | |
> | ManagedNetworkEvent | Yes | AzureDiagnostics | ... | |
> | **RequestResponse** | No | AzureDiagnostics | ... | **(empty)** |
> | Trace | No | AzureDiagnostics | ... | |
> — [Supported log categories - Microsoft.CognitiveServices/accounts - Azure Monitor | Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-logs/microsoft-cognitiveservices-accounts-logs), fetched 2026-09-13 (page `ms.date: 2026-08-21`)

The **same** empty row, with the **same** four columns and no content description, is repeated
verbatim in the Azure-OpenAI-specific reference:

> — [Monitoring data reference for Azure OpenAI - Microsoft Foundry | Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/openai/monitor-openai-reference), "Supported resource logs for Microsoft.CognitiveServices/accounts", fetched 2026-09-13 (page `ms.date: 2026-05-19`)

The generic "Enable diagnostic logging" how-to instructs enabling `RequestResponse` but never
describes what it contains — it only says to select it, alongside `Audit` and `AllMetrics`, and shows
sample Kusto queries that project generic columns (`TimeGenerated`, `Category`, `OperationName`,
`DurationMs`) with no field specific to `RequestResponse`:

> "Select **Audit**, **RequestResponse**, and **AllMetrics**. Then set the retention period..."
> — [Enable diagnostic logging - Foundry Tools | Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/diagnostic-logging), fetched 2026-09-13 (page `ms.date: 2025-10-02`) — this page is
> generic to all Cognitive Services/"Foundry Tools" resources (Speech, Vision, etc.), not
> Azure-OpenAI-specific, and never mentions Azure OpenAI or the realtime API by name.

The "Monitor Azure OpenAI (classic)" how-to page — the most Azure-OpenAI-specific narrative page
found — describes *how* to route and query resource logs in general terms and points back to the
same empty reference table for the actual category list; it never describes `RequestResponse`'s
fields either:

> "For the available resource log categories, their associated Log Analytics tables, and the log
> schemas for Azure OpenAI, see [Azure OpenAI monitoring data reference]..."
> — [Monitor Azure OpenAI in Microsoft Foundry Models (classic) | Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/monitor-openai), fetched 2026-09-13 (page `ms.date: 2025-11-06`) — the reference it points to is the same empty table quoted above.

### 3b. The destination table is a generic pass-through with no per-service schema published

All four categories, `RequestResponse` included, land in `AzureDiagnostics` — a table Microsoft's own
reference describes as having no fixed per-service schema:

> "Stores resource logs for Azure services that use Azure Diagnostics mode... The resource log for
> each Azure service has a unique set of columns. The AzureDiagnostics table includes the most common
> columns used by Azure services. If a resource log includes a column that doesn't already exist in
> the AzureDiagnostics table, that column is added the first time that data is collected."
> — [Azure Monitor Logs reference - AzureDiagnostics | Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/azurediagnostics), fetched 2026-09-13 (page `ms.date: 2026-01-27`)

The table's own published column list (fetched in full) contains only generic, resource-agnostic
columns (`OperationName`, `DurationMs`, `ResultType`, `Category`, `Resource`, a catch-all
`properties_s` string column, and an `AdditionalFields` dynamic property bag for anything past the
500-column cap) — **nothing specific to Cognitive Services or Azure OpenAI, and no column that would
tell a reader in advance whether prompt/completion content is present.** Whatever `RequestResponse`
actually writes for this resource type would show up in `properties_s` or `AdditionalFields`, whose
*content* is exactly what is undocumented.

### 3c. No official source connects `RequestResponse` to the realtime API in either direction

Across all four Microsoft Learn pages fetched for this section, **the word "realtime" appears
exactly once, and only in a metric, not this log category**:

> **Realtime API Seconds Used** — RealtimeAPI number of seconds used | `RealtimeUsageTime` | ... |
> Total (Sum) | `Region`, `ModelDeploymentName` | PT1M | Yes
> — [Monitoring data reference for Azure OpenAI | Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/openai/monitor-openai-reference), "Category: Azure OpenAI - Usage", fetched 2026-09-13

That is a **platform metric** (a seconds-used counter, `DS Export: Yes` meaning it *can* be routed to
logs as a metric row) — categorically different from a resource log, and it says nothing about
request/response content. **No fetched page states, in either direction, whether `RequestResponse`
fires at all for realtime/WebSocket sessions**, as opposed to only for classic REST-style
`Completions`/`ChatCompletions` calls, and none states what it would contain if it does fire.

### 3d. Secondary sources — inconsistent with each other, and not authoritative

Community sources found in the course of this search are recorded here explicitly as **not primary**
and are not the basis for any conclusion, but they are worth noting because they disagree with each
other, which is itself informative: one Microsoft Q&A community answer describes `RequestResponse`
for Azure OpenAI as covering "the actual token counts and latency" (metadata only); a different
search result describes seeing `requestPayload_s`/`responsePayload_s` columns holding prompt/chat
message text for `Completions_Create`/`ChatCompletions_Create` operations specifically. **No
Microsoft-authored primary source fetched confirms either claim, and this note does not adopt
either.**

### 3e. Item 15 — verdict

**No official Microsoft documentation states what `RequestResponse` contains for
`Microsoft.CognitiveServices/accounts`, for Azure OpenAI specifically, or for the realtime API most
specifically** — not a schema, not a field list, not a worked example, not even a one-line prose
description beyond "select this checkbox." The category's own reference-table row is empty in both
places it appears, its destination table is a documented generic pass-through with no
per-service schema, and its one connection to "realtime" in official docs is an unrelated metric.

**OPEN QUESTION 15a**: whether `RequestResponse` emits any rows at all for a realtime/WebSocket
deployment (`gpt-realtime-mini`), as distinct from being silently empty because the category
predates Azure OpenAI and may be scoped to classic HTTP request/response cycles. Not answerable from
documentation; only a queried table after a known emission (`CLAUDE.md`'s 200-OK rule) would settle
it, and `docs/phase6/exit-criteria.md` explicitly forbids enabling the category before that query
happens.

**OPEN QUESTION 15b**: if it does emit rows for realtime sessions, whether their content is metadata
only or includes prompt/completion/audio content. Not answerable from any primary source fetched.

**This does not block Phase 6.** `docs/phase6/exit-criteria.md` criterion 4 accepts either "open item
15 answered" **or** "`RequestResponse` left disabled with that recorded" as satisfying the criterion.
Given there is no primary-source basis to predict this category's content safely, and given
`docs/phase6/exit-criteria.md`'s own "What this phase must not do" list already forbids enabling it
before its destination table is queried and read, the conservative action — leaving `RequestResponse`
disabled — is the one the exit criteria already contemplate as sufficient, independent of whether
15a/15b are ever resolved.

---

## Answers to open items 15 and 16

- **Item 16 — SETTLED.** None of `opentelemetry-instrumentation-fastapi`, `-httpx`, or `-requests`
  (compatible release `0.65b0`, matching this project's `fastapi==0.115.14` / `httpx==0.28.1` pins)
  captures HTTP request or response bodies by default or via any documented opt-in flag — that
  capability does not exist in any of the three packages; enabling FastAPI instrumentation on the ACS
  webhook (`voice-agent/azbank_voice_agent/app.py`'s `/api/incoming-call` handler, which carries
  `incomingCallContext` only in its POST body, never in a query string, header, or path parameter)
  would not put it into any span, span-event, or log record through these packages' own mechanisms.
- **Item 15 — SETTLED as "undocumented."** No Microsoft primary source fetched (Azure Monitor's
  supported-logs reference, the Azure-OpenAI-specific monitoring reference, the generic and
  Azure-OpenAI-specific diagnostic-logging how-tos, or the `AzureDiagnostics` table reference)
  describes what the `RequestResponse` category contains, for Azure OpenAI generally or the realtime
  API specifically, or connects it to the realtime API in either direction — so the phase 6 blocking
  question resolves via `docs/phase6/exit-criteria.md` criterion 4's own fallback: `RequestResponse`
  stays disabled until its destination table can be queried and read, and that satisfies the
  criterion without requiring the category's actual content to be known.

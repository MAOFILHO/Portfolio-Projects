# Phase 4 research — the three carried findings

Pure documentation research on the three items `docs/phase4/findings.md` carries forward into Phase 5
and Phase 6. **No application code was written or changed for this task.** All claims below are
sourced from live fetches of primary sources performed **2026-09-10** (URL + fetch date next to every
claim), per `CLAUDE.md`'s rule that a factual API question is never answered from memory. Where a
primary source does not clearly answer something, it is marked **OPEN QUESTION** rather than filled in
by inference — including the several places where the answer is *nearly* obvious.

Sources used are Microsoft Learn, the OpenAI Realtime API reference (via the `openai` Python SDK's
own OpenAPI-generated types, pinned to the exact version this project depends on), the Azure SDK
source and REST specs on GitHub, and the OpenTelemetry semantic-convention repositories. Where a
claim exists only in secondary writing, that is stated explicitly.

**Deployment this research is scoped to**: Azure OpenAI resource `aoai-azure-banking-voice-cc`,
region **Canada Central**, deployment name `gpt-realtime-mini`, model version **`2025-10-06`**, SKU
`GlobalStandard`, `NoAutoUpgrade`. Documented successor per B3: `gpt-realtime-1.5`, version
`2026-02-23`. Telephony is ACS Call Automation **bidirectional media streaming** over a WebSocket to
a Python app in Azure Container Apps.

**B3 pinning discipline, stated up front and honoured throughout**: every capability claim below is
pinned to a version — the `openai` SDK at `3.6.0` (this project's pin, `voice-agent/pyproject.toml`),
the Call Automation REST spec at `2026-03-12`, the Call Automation docs at their stated `ms.date`.
Where a source is version-less, that is called out as a weakness of the source, not smoothed over.
**Nothing below is pinned to `gpt-realtime-mini` `2025-10-06` specifically**, because no primary
source fetched today documents `conversation.item.create` per model version — see OPEN QUESTION 1e.

---

## 1. The injected conversation item's wire shape

The relay's `_spoken_note` (`voice-agent/azbank_voice_agent/realtime/session.py:52-74`) sends:

```json
{
  "type": "conversation.item.create",
  "item": {
    "type": "message",
    "role": "system",
    "content": [{ "type": "input_text", "text": "..." }]
  }
}
```

followed by a `response.create`. The question is whether that is the documented shape, and what a
rejection would look like.

### 1a. Azure's own reference page is a one-paragraph pass-through

The Azure realtime reference page no longer documents events at all. Its entire body, as fetched, is:

> "The Azure OpenAI Realtime API follows the OpenAI Realtime API specification. For the full API
> reference, see the [OpenAI Realtime API reference](https://developers.openai.com/api/reference/resources/realtime).
>
> Note
>
> **Azure deviation:** The accepted values for the `model` field in `input_audio_transcription`
> settings differ from the OpenAI reference. Azure OpenAI requires the name of the existing model
> deployment for the field, like `my-gpt-4o-transcribe-deployment`."

— [Realtime API reference - Microsoft Foundry | Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/openai/realtime-audio-reference), fetched 2026-09-10 (page `ms.date: 2026-05-13`)

**This answers the "Azure deviations" sub-question directly and narrowly.** The page's stated purpose
is "Reference for the Azure OpenAI Realtime API events, with notes on Azure-specific deviations from
the OpenAI specification" (page `description` metadata, same fetch), and the *only* deviation it
notes is the `input_audio_transcription.model` field. **No documented Azure deviation touches
`conversation.item.create`, its item types, its roles, or its content part types.**

That is a statement about what Microsoft documents, not a guarantee about what the service does. It
is the same class of claim as Phase 1's — and Phase 1 found the docs' prose wrong about
`response.audio.delta` vs `response.output_audio.delta`, which a live probe had to settle
(`docs/phase1/research-aoai-realtime-wire-format.md` §2).

### 1b. Which item types `conversation.item.create` accepts

`platform.openai.com` returns HTTP 403 to automated fetches (attempted 2026-09-10), so the
authoritative text was taken from the OpenAPI-generated types shipped in the `openai` Python SDK —
the same spec, generated rather than prose, and pinnable to a version. **Quoted at tag `v3.6.0`, the
exact version `voice-agent/pyproject.toml` pins (`openai==3.6.0`); the text was also checked at
`main` (v3.13.0) and is byte-identical for every type quoted in this section.**

The event itself:

> ```python
> class ConversationItemCreateEvent(BaseModel):
>     """
>     Add a new Item to the Conversation's context, including messages, function
>     calls, and function call responses. This event can be used both to populate a
>     "history" of the conversation and to add new items mid-stream, but has the
>     current limitation that it cannot populate assistant audio messages.
>
>     If successful, the server will respond with a `conversation.item.created`
>     event, otherwise an `error` event will be sent.
>     """
>
>     item: ConversationItem
>     """A single item within a Realtime conversation."""
>
>     type: Literal["conversation.item.create"]
>     """The event type, must be `conversation.item.create`."""
> ```
> — [`openai-python`, `src/openai/types/realtime/conversation_item_create_event.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/conversation_item_create_event.py), fetched 2026-09-10 at tag `v3.6.0`

The `ConversationItem` union enumerates every accepted item type:

> ```python
> ConversationItem: TypeAlias = Annotated[
>     Union[
>         RealtimeConversationItemSystemMessage,
>         RealtimeConversationItemUserMessage,
>         RealtimeConversationItemAssistantMessage,
>         RealtimeConversationItemFunctionCall,
>         RealtimeConversationItemFunctionCallOutput,
>         RealtimeMcpApprovalResponse,
>         RealtimeMcpListTools,
>         RealtimeMcpToolCall,
>         RealtimeMcpApprovalRequest,
>     ],
>     PropertyInfo(discriminator="type"),
> ]
> ```
> — [`openai-python`, `src/openai/types/realtime/conversation_item.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/conversation_item.py), fetched 2026-09-10 at tag `v3.6.0`

**`system` is one of exactly three message roles, and it is first in the union.** It is not a
"documented-but-degenerate" case: it has its own generated model class, with its own docstring
describing precisely the use this project puts it to.

### 1c. Which role values are valid, and which content types per role

**System — `input_text` only, and this is exactly this project's use case:**

> ```python
> class Content(BaseModel):
>     text: Optional[str] = None
>     """The text content."""
>
>     type: Optional[Literal["input_text"]] = None
>     """The content type. Always `input_text` for system messages."""
>
>
> class RealtimeConversationItemSystemMessage(BaseModel):
>     """
>     A system message in a Realtime conversation can be used to provide additional context or
>     instructions to the model. This is similar but distinct from the instruction prompt provided
>     at the start of a conversation, as system messages can be added at any point in the
>     conversation. For major changes to the conversation's behavior, use instructions, but for
>     smaller updates (e.g. "the user is now asking about a different topic"), use system messages.
>     """
>
>     content: List[Content]
>     """The content of the message."""
>
>     role: Literal["system"]
>     """The role of the message sender. Always `system`."""
>
>     type: Literal["message"]
>     """The type of the item. Always `message`."""
> ```
> — [`openai-python`, `src/openai/types/realtime/realtime_conversation_item_system_message.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/realtime_conversation_item_system_message.py), fetched 2026-09-10 at tag `v3.6.0`

Three things in that quote are load-bearing for this project:

1. `role` is `Literal["system"]` and `type` is `Literal["message"]` — the exact pair `_spoken_note`
   sends.
2. `input_text` is not merely *allowed* on a system message, it is the **only** allowed content type
   — "Always `input_text` for system messages."
3. "system messages can be added at any point in the conversation" — the mid-session case, stated
   in so many words.

**User — `input_text`, `input_audio`, `input_image`:**

> ```python
>     type: Optional[Literal["input_text", "input_audio", "input_image"]] = None
>     """The content type (`input_text`, `input_audio`, or `input_image`)."""
> ...
>     role: Literal["user"]
>     """The role of the message sender. Always `user`."""
> ```
> — [`openai-python`, `src/openai/types/realtime/realtime_conversation_item_user_message.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/realtime_conversation_item_user_message.py), fetched 2026-09-10 at tag `v3.6.0`

**Assistant — `output_text` / `output_audio`, *not* `text`:**

> ```python
>     type: Optional[Literal["output_text", "output_audio"]] = None
>     """
>     The content type, `output_text` or `output_audio` depending on the session
>     `output_modalities` configuration.
>     """
> ...
>     role: Literal["assistant"]
>     """The role of the message sender. Always `assistant`."""
> ```
> — [`openai-python`, `src/openai/types/realtime/realtime_conversation_item_assistant_message.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/realtime_conversation_item_assistant_message.py), fetched 2026-09-10 at tag `v3.6.0`

So the question's framing — "is `input_text` restricted to `user` and `text` to `assistant`" — is
answered **no on both halves**: `input_text` is valid on `system` (and is the only thing valid
there), and the assistant's text type is spelled `output_text`, not `text`. The `text` spelling and
an `item_reference` content type appear in older prose on the OpenAI docs site
([Realtime API reference — resources/realtime](https://developers.openai.com/api/reference/resources/realtime),
fetched 2026-09-10, which renders the sentence "The content type (`input_text`, `input_audio`,
`item_reference`, `text`)") and are **not** in the generated types at `v3.6.0` or `main`. Where the
site prose and the generated types disagree, this note treats the generated types as authoritative,
because Phase 1 already established for this exact API that the SDK's generated wire values were
right and the docs' prose was wrong (`docs/phase1/research-aoai-realtime-wire-format.md` §2).

**OPEN QUESTION 1a**: whether `item_reference` is still a valid *content part* type inside a
`conversation.item.create` message (as opposed to inside `response.create`'s `input` array, where the
`ConversationItem` union does not include it either). The OpenAI docs site prose says yes; the
generated types say no. Not resolvable from the two sources fetched, and not needed by this project.

### 1d. What a rejection looks like on the wire

`ConversationItemCreateEvent`'s own docstring (quoted in §1b) states the contract: *"If successful,
the server will respond with a `conversation.item.created` event, otherwise an `error` event will be
sent."* The `error` event's shape:

> ```python
> class RealtimeErrorEvent(BaseModel):
>     """
>     Returned when an error occurs, which could be a client problem or a server
>     problem. Most errors are recoverable and the session will stay open, we
>     recommend to implementors to monitor and log error messages by default.
>     """
>
>     error: RealtimeError
>     """Details of the error."""
>
>     event_id: str
>     """The unique ID of the server event."""
>
>     type: Literal["error"]
>     """The event type, must be `error`."""
> ```
> — [`openai-python`, `src/openai/types/realtime/realtime_error_event.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/realtime_error_event.py), fetched 2026-09-10 at tag `v3.6.0`

> ```python
> class RealtimeError(BaseModel):
>     """Details of the error."""
>
>     message: str
>     """A human-readable error message."""
>
>     type: str
>     """The type of error (e.g., "invalid_request_error", "server_error")."""
>
>     code: Optional[str] = None
>     """Error code, if any."""
>
>     event_id: Optional[str] = None
>     """The event_id of the client event that caused the error, if applicable."""
>
>     param: Optional[str] = None
>     """Parameter related to the error, if any."""
> ```
> — [`openai-python`, `src/openai/types/realtime/realtime_error.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/realtime_error.py), fetched 2026-09-10 at tag `v3.6.0`

Concretely, a rejection arrives as a top-level frame with `"type": "error"`, a server-generated
`event_id`, and a nested `error` object carrying `message` (required, human-readable), `type`
(required, a free-form string — `"invalid_request_error"` and `"server_error"` are given only as
examples), and optionally `code`, `param`, and `error.event_id`.

**The single most useful fact for the relay** is `error.event_id`: "The event_id of the client event
that caused the error, if applicable." `ConversationItemCreateEvent` accepts an optional
client-generated `event_id` ("Optional client-generated ID used to identify this event", same file as
§1b). **If the relay stamps its own `event_id` on the injected item, it can correlate a rejection to
that exact injection rather than guessing** — which is precisely the "tell a rejection from silence"
requirement. `_spoken_note` currently sends no `event_id`.

**OPEN QUESTION 1b**: `error.type` is typed `str`, not an enum, and `error.code` is `Optional[str]`
with the bare gloss "Error code, if any." **No primary source fetched enumerates the possible `code`
values, and none states which `type`/`code` a rejected item shape would produce.** A relay cannot
therefore be written to match on a specific code; it can only match on `type == "error"` plus the
correlated `event_id`. Anything narrower is guessing.

**OPEN QUESTION 1c**: neither source states a *timeout*. There is no documented upper bound on how
long the server may take to answer a `conversation.item.create` with either
`conversation.item.created` or `error`, so "rejection vs silence" cannot be decided from docs alone —
only by a real call, or by the relay imposing its own deadline.

### 1e. If a system-role message were not accepted — the documented alternatives

Nothing fetched suggests it would be rejected, but the alternatives were researched as asked, and
they matter because §1a's guarantee is about Microsoft's documentation, not the service.

**Option A — `session.update` `instructions`.** The realtime session's `instructions` field is a
plain string, settable at any time; Phase 1 confirmed the field and the session-update mechanism
against this deployment (`docs/phase1/research-aoai-realtime-wire-format.md` §1), and the relay
already uses it for handoffs (`realtime/session.py:_session_update`). **Trade-offs**: the system
message docstring in §1c draws the line explicitly — *"For major changes to the conversation's
behavior, use instructions, but for smaller updates (e.g. 'the user is now asking about a different
topic'), use system messages."* A PIN outcome is the second kind. Worse, `instructions` is
*replaced*, not appended, so injecting a one-off fact this way means either rewriting the whole
agent prompt with the fact spliced in (and the fact then persists for the rest of the call, having to
be un-said later) or losing the agent's prompt. It also does not itself cause speech; a
`response.create` is still required.

**Option B — a `user`-role message.** Structurally valid (§1c) and the shape OpenAI's own
conversation guide illustrates for injecting text mid-session:

> ```json
> {
>   "type": "conversation.item.create",
>   "item": {
>     "type": "message",
>     "role": "user",
>     "content": [{"type": "input_text", "text": "What Prince album sold the most copies?"}]
>   }
> }
> ```
> — [Realtime conversations | OpenAI API](https://developers.openai.com/api/docs/guides/realtime-conversations), fetched 2026-09-10

**Trade-off, and it is a real one for a banking IVR**: this writes into the conversation history a
turn attributed to the *caller* that the caller never said. Any transcript of the call then contains
a fabricated caller utterance, and the model's later behaviour is conditioned on the caller having
"said" that their PIN check passed. For a system whose entire B1 constraint is about not confusing
"the caller asserted X" with "the system of record confirmed X", that is the wrong role, even though
the wire shape is legal.

**Option C — out-of-band `response.create` with per-response `instructions` and `input`.** This is
the third documented mechanism and the one no source fetched today describes as a substitute for a
system message, but which technically covers the case:

> ```python
> class ResponseCreateEvent(BaseModel):
>     """
>     ...
>     The `response.create` event includes inference configuration like
>     `instructions` and `tools`. If these are set, they will override the Session's
>     configuration for this Response only.
>
>     Responses can be created out-of-band of the default Conversation, meaning that they can
>     have arbitrary input, and it's possible to disable writing the output to the Conversation.
>     ...
>     Clients can set `conversation` to `none` to create a Response that does not write to the default
>     Conversation. Arbitrary input can be provided with the `input` field, which is an array accepting
>     raw Items and references to existing Items.
>     """
> ```
> — [`openai-python`, `src/openai/types/realtime/response_create_event.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/response_create_event.py), fetched 2026-09-10 at tag `v3.6.0`

> ```python
>     conversation: Union[str, Literal["auto", "none"], None] = None
>     """Controls which conversation the response is added to. ...
>     Set this to `none` to create an out-of-band response which
>     will not add items to default conversation.
>     """
>
>     input: Optional[List[ConversationItem]] = None
>     """Input items to include in the prompt for the model.
>
>     Using this field creates a new context for this Response instead of using the
>     default conversation. An empty array `[]` will clear the context for this
>     Response. ...
>     """
>
>     instructions: Optional[str] = None
>     """The default system instructions (i.e. system message) prepended to model calls. ...
>     Note that the server sets default instructions which will be used if
>     this field is not set ...
>     """
> ```
> — [`openai-python`, `src/openai/types/realtime/realtime_response_create_params.py`](https://github.com/openai/openai-python/blob/main/src/openai/types/realtime/realtime_response_create_params.py), fetched 2026-09-10 at tag `v3.6.0`

**Trade-offs**: per-response `instructions` override the session's for that response only — no
rewrite, no cleanup, and the note is genuinely system-voiced. But `conversation: "none"` means the
spoken outcome is *not* written to the conversation, so the model has no memory that it said it; and
`input` replaces the context for that response entirely, so the model answers without the call so
far unless items are re-listed by reference. For a one-sentence outcome announcement that the rest of
the call does need to remember (the caller is now verified), that is a worse fit than the system
message.

**OPEN QUESTION 1d — the one that actually matters here.** Everything in §1b–§1e describes the
OpenAI Realtime specification. **No primary source fetched today states that Azure's
`/openai/v1/realtime` GA endpoint accepts a `system`-role `input_text` message on
`conversation.item.create`** — Azure's reference page (§1a) delegates wholesale to OpenAI's spec and
notes one unrelated deviation, which is evidence but not a statement. This is exactly the gap
`docs/phase4/findings.md` §2 records, and the docs narrow it without closing it.

**OPEN QUESTION 1e — B3-shaped, and unresolved.** No source fetched documents
`conversation.item.create` behaviour **per model version**. The `openai` SDK types are pinned to an
SDK version, not to `gpt-realtime-mini` `2025-10-06`; Azure's Realtime page lists supported models but
says nothing about item types per version. B3 exists because this project has already seen one
deployment name span versions with different behaviour, and Phase 1's central finding was precisely a
version-specific capability question that doc research could not settle and a live probe did
(`docs/phase1/research-aoai-realtime-wire-format.md` §5). **The same method applies here: this is a
one-frame probe against the live deployment, not a further reading exercise.**

---

## 2. The DTMF wire vocabulary over bidirectional media streaming

The code assumes an inbound frame shaped `{"kind": "DtmfData", "dtmfData": {"data": "<tone>"}}` with
`<tone>` a single character (`voice-agent/azbank_voice_agent/transport/acs.py:37-41`).

### 2a. The frame shape — confirmed, on every source that has one

Microsoft's audio-streaming quickstart shows the frame identically in all four language pivots
(C#, Java, JavaScript, Python):

> #### DTMF example
>
> When DTMF is enabled Azure Communication Services sends a `DtmfData` type.
>
> ```json
> {
>   "kind": "DtmfData",
>   "dtmfData": {
>     "data": "3"
>   }
> }
> ```
> — [Audio streaming quickstart - Azure Communication Services | Microsoft Learn](https://learn.microsoft.com/en-us/azure/communication-services/how-tos/call-automation/audio-streaming-quickstart), fetched 2026-09-10 (page `ms.date: 2024-07-15`, `updated_at: 2026-06-12`)

The .NET SDK's own parser dispatches on the same two keys:

> ```csharp
> string kind = streamingData.GetProperty("kind").ToString();
> ...
>     case "DtmfData":
>         DtmfDataInternal dtmfInternal = JsonSerializer.Deserialize<DtmfDataInternal>(streamingData.GetProperty("dtmfData").ToString());
>         return new DtmfData(dtmfInternal.Data, dtmfInternal.Timestamp, dtmfInternal.ParticipantRawId);
> ```
> — [`azure-sdk-for-net`, `sdk/communication/Azure.Communication.CallAutomation/src/Models/Streaming/StreamingData.cs`](https://github.com/Azure/azure-sdk-for-net/blob/main/sdk/communication/Azure.Communication.CallAutomation/src/Models/Streaming/StreamingData.cs), fetched 2026-09-10 (`main`)

…and so does the JavaScript SDK's:

> ```typescript
>       case "DtmfData": {
>         const dtmfData: DtmfData = {
>           data: jsonObject.dtmfData.data,
>         };
> ```
> — [`azure-sdk-for-js`, `sdk/communication/communication-call-automation/src/streamingData.ts`](https://github.com/Azure/azure-sdk-for-js/blob/main/sdk/communication/communication-call-automation/src/streamingData.ts), fetched 2026-09-10 (`main`)

The full inbound object, per the .NET internal model, has three fields — only one of which the docs'
example shows:

> ```csharp
> internal class DtmfDataInternal
> {
>     [JsonPropertyName("data")]
>     public string Data { get; set; }
>
>     [JsonPropertyName("timestamp")]
>     public DateTime Timestamp { get; set; }
>
>     [JsonPropertyName("participantRawID")]
>     public string ParticipantRawId { get; set; }
> }
> ```
> — [`azure-sdk-for-net`, `.../Models/Streaming/Media/DtmfDataInternal.cs`](https://github.com/Azure/azure-sdk-for-net/blob/main/sdk/communication/Azure.Communication.CallAutomation/src/Models/Streaming/Media/DtmfDataInternal.cs), fetched 2026-09-10 (`main`)

Note the casing of `participantRawID` — camelCase with a capitalised `ID` suffix, matching the
`audioData.participantRawID` in the quickstart's `AudioData` sample. `acs.py` reads neither field;
that is a deliberate B2-friendly narrowness, not an omission to fix.

**Casing asymmetry — confirmed, and confirmed to be Microsoft's own doing.** Inbound frames use a
lowercase `kind` discriminator with a camelCase payload key; the same page's outbound (server → ACS)
Python sample uses capitalised keys:

> ```python
>         data = {
>             "Kind": "AudioData",
>             "AudioData": {
>                 "Data": buffer
>             },
>             "StopAudio": None
>         }
> ```
> — [Audio streaming quickstart](https://learn.microsoft.com/en-us/azure/communication-services/how-tos/call-automation/audio-streaming-quickstart), Python pivot, fetched 2026-09-10

This independently corroborates the asymmetry `acs.py`'s module docstring records from Phase 0/1 and
`docs/PLAN.md`'s "Key protocol facts (verified)". The stop frame is spelled
`{"Kind": "StopAudio", "AudioData": None, "StopAudio": {}}` on the same page — noted here only
because it is the other outbound shape and it shares the capitalised convention.

### 2b. The tone vocabulary — the load-bearing answer, and it is only half-answered

**What the primary sources actually show for the media-stream path: a literal character.**

Two independent primary artefacts, both showing a bare digit and neither showing a spelled token:

- The docs' example, `"data": "3"` (§2a).
- The .NET SDK's own round-trip test, which asserts the parsed value equals the input character:

> ```csharp
>         public void ParseDtmfData_Test()
>         {
>             string dtmfJson = "{"
>                 + "\"kind\": \"DtmfData\","
>                 + "\"dtmfData\": {"
>                 + "\"data\": \"5\""
>                 + "}"
>                 + "}";
>
>             DtmfData streamingDtmf = (DtmfData)StreamingData.Parse(dtmfJson);
>             ValidateDtmfData(streamingDtmf);
>         }
>         private static void ValidateDtmfData(DtmfData streamingDtmf)
>         {
>             Assert.That(streamingDtmf, Is.Not.Null);
>             Assert.That(streamingDtmf.Data, Is.EqualTo("5"));
>         }
> ```
> — [`azure-sdk-for-net`, `.../tests/Streaming/StreamingDataParserTests.cs`](https://github.com/Azure/azure-sdk-for-net/blob/main/sdk/communication/Azure.Communication.CallAutomation/tests/Streaming/StreamingDataParserTests.cs), fetched 2026-09-10 (`main`)

Both parsers (§2a) pass `data` through untouched — no enum lookup, no decode, no mapping table on
either side. Whatever the service puts in that string is what the application sees.

**A direct contradiction between primary sources, recorded rather than resolved.** The .NET SDK's
public `DtmfData` class documents the very same field as base64:

> ```csharp
>     public class DtmfData : StreamingData
>     {
>         /// <summary>
>         /// The dtmf data, encoded as a base64 string
>         /// </summary>
>         public DtmfData(string data)
> ...
>         /// <summary>
>         /// The dtmf data in base64 string.
>         /// </summary>
>         public string Data { get; }
> ```
> — [`azure-sdk-for-net`, `.../Models/Streaming/Media/DtmfData.cs`](https://github.com/Azure/azure-sdk-for-net/blob/main/sdk/communication/Azure.Communication.CallAutomation/src/Models/Streaming/Media/DtmfData.cs), fetched 2026-09-10 (`main`)

…and the JavaScript SDK documents it as something else again:

> ```typescript
> export interface DtmfData {
>   /** A unique identifier for the media subscription.*/
>   data: string;
> }
> ```
> — [`azure-sdk-for-js`, `sdk/communication/communication-call-automation/src/models/streaming.ts`](https://github.com/Azure/azure-sdk-for-js/blob/main/sdk/communication/communication-call-automation/src/models/streaming.ts), fetched 2026-09-10 (`main`)

Three primary artefacts describe one field three incompatible ways: a base64 string, a media
subscription identifier, and (per the docs example and the .NET test) a literal tone character. The
two docstrings read as copy-paste from `AudioData` and `AudioMetadata` respectively — `"5"` is not
valid base64 for anything meaningful and is manifestly not a subscription id. **The executable
artefact (a test that asserts on the value) and Microsoft's own worked example agree with each
other and against both docstrings**, so the literal-character reading is the one this note reports.
That is a judgement about which primary source to trust, and it is stated as one.

**The enumeration this question asked for does not exist in any primary source fetched.** The docs
example shows `"3"`. The .NET test shows `"5"`. **No primary source fetched enumerates the media-stream
`data` vocabulary at all.** The Call Automation REST spec at `2026-03-12` — the service's own
swagger, `info.version: "2026-03-12"` — **does not define the websocket streaming frames at all**: a
scan of the whole document for `dtmfData`, `audioData`, and `AudioMetadata` returns zero occurrences
([`azure-rest-api-specs`, `specification/communication/data-plane/CallAutomation/stable/2026-03-12/communicationservicescallautomation.json`](https://github.com/Azure/azure-rest-api-specs/blob/main/specification/communication/data-plane/CallAutomation/stable/2026-03-12/communicationservicescallautomation.json), fetched 2026-09-10). The websocket contract lives *only* in the docs samples and the SDK
parsers; it has no schema.

**The spelled-token vocabulary that does exist belongs to the other DTMF path, not this one.** The
REST spec defines exactly one DTMF tone enum, and it is referenced only by `ContinuousDtmfRecognitionToneReceived.tone`,
`DtmfResult.tones`, and the send/recognize request models:

> ```json
> "Tone": {
>  "description": "List of valid stop tones",
>  "enum": [
>   "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
>   "a", "b", "c", "d", "pound", "asterisk"
>  ],
>  "type": "string",
>  "x-ms-enum": { "name": "Tone", "modelAsString": true }
> }
> ```
> — same REST spec file, `definitions.Tone`, fetched 2026-09-10

The Python SDK's generated mirror of that enum is identical (`ZERO = "zero"` … `POUND = "pound"`,
`ASTERISK = "asterisk"`), — [`azure-sdk-for-python`, `.../callautomation/_generated/models/_enums.py`](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/communication/azure-communication-callautomation/azure/communication/callautomation/_generated/models/_enums.py), fetched 2026-09-10 (`main`). **Neither the enum nor anything referencing it
is reachable from the media-streaming websocket frame**, which has no schema to reference it from.

**OPEN QUESTION 2a — the single most consequential gap in this document.** For the media-streaming
websocket path, the only tone values shown by any primary source are `"3"` and `"5"`. **`*`, `#`, and
`A`–`D` have no documented spelling on this path whatsoever.** Whether `*` arrives as `"*"`,
`"asterisk"`, or `"star"`, and `#` as `"#"`, `"pound"`, or `"hash"`, is **not answerable from the
documentation**, and the two candidate vocabularies that do exist (literal characters, from the
digit examples; spelled tokens, from the `Tone` enum on the webhook path) disagree on exactly those
four characters. The keypad state machine treats `*` as clear and `#` as ignore, so this is not a
cosmetic question: on the spelled-token vocabulary the state machine would silently ignore both
control keys and the caller could never clear a mis-key. **A single real call pressing `*` and `#`
settles it and nothing short of that does.** (Mitigation available without any new evidence: accept
*both* vocabularies at the classifier — a small, testable widening whose cost is one mapping table
and whose failure mode is nothing.)

### 2c. Enabling DTMF over the media stream, and its relation to the webhook events

**One switch, named in every language pivot of the quickstart.** From the C# pivot:

> ```csharp
> MediaStreamingOptions mediaStreamingOptions = new MediaStreamingOptions(MediaStreamingAudioChannel.Unmixed);
>  mediaStreamingOptions.TransportUri = new Uri(websocketUri);
>  mediaStreamingOptions.EnableBidirectional = true;
>  mediaStreamingOptions.AudioFormat = AudioFormat.Pcm24KMono;
>  mediaStreamingOptions.EnableDtmfTones = true;
> ```

and from the Java pivot, with Microsoft's own inline comment saying what it does:

> ```java
> mediaStreamingOptions.setEnableDtmfTones(true); // Allow receiving DTMF tones
> ```

and from the Python pivot — the same call this project makes:

> ```python
> media_streaming_options = MediaStreamingOptions(
>     transport_url=WEBSOCKET_URI_HOST,
>     transport_type=StreamingTransportType.WEBSOCKET,
>     content_type=MediaStreamingContentType.AUDIO,
>     audio_channel_type=MediaStreamingAudioChannelType.MIXED,
>     start_media_streaming=True,
>     enable_bidirectional=True,
>     enable_dtmf_tones=True,
>     audio_format=AudioFormat.PCM24_K_MONO
> )
> ```
> — all three from [Audio streaming quickstart](https://learn.microsoft.com/en-us/azure/communication-services/how-tos/call-automation/audio-streaming-quickstart), fetched 2026-09-10

The REST spec backs the field, on the websocket-transport variant specifically:

> ```json
> "WebSocketMediaStreamingOptions": {
>  "description": "Represents the options for WebSocket transport.",
>  "properties": {
>   "transportUrl": { "description": "The transport URL for media streaming.", "type": "string" },
>   "contentType": { "$ref": "#/definitions/MediaStreamingContentType" },
>   "startMediaStreaming": { "description": "A value indicating whether the media streaming should start immediately after the call is answered.", "type": "boolean" },
>   "enableBidirectional": { "description": "A value indicating whether bidirectional streaming is enabled.", "type": "boolean" },
>   "audioFormat": { "$ref": "#/definitions/AudioFormat" },
>   "enableDtmfTones": { "description": "A value that indicates whether to stream the DTMF tones.", "type": "boolean" }
>  },
>  "x-ms-discriminator-value": "websocket"
> }
> ```
> — same REST spec file, `definitions.WebSocketMediaStreamingOptions`, fetched 2026-09-10

**`voice-agent/azbank_voice_agent/app.py:133-141` already sets `enable_dtmf_tones=True` alongside
`enable_bidirectional=True` and `start_media_streaming=True`.** That is the documented enabling path,
and it matches the quickstart's Python sample field for field.

**DTMF-over-media-stream and `ContinuousDtmfRecognition` are separate mechanisms with separate
vocabularies and separate delivery channels.** Continuous DTMF recognition is a mid-call *action*
requiring its own start call and delivering tones to the *webhook* callback, not the websocket:

> ## Continuous DTMF recognition
>
> You can subscribe to receive continuous DTMF tones throughout the call. Your application receives
> DTMF tones when the targeted participant presses on a key on their keypad. The tones are sent to
> your application one by one as the participant presses on them.
>
> ### StartContinuousDtmfRecognitionAsync method
>
> Start detecting DTMF tones sent by a participant.
> — [Managing media actions with Call Automation | Microsoft Learn](https://learn.microsoft.com/en-us/azure/communication-services/how-tos/call-automation/control-mid-call-media-actions), fetched 2026-09-10 (page `ms.date: 2024-07-16`)

Its delivery is the `ContinuousDtmfRecognitionToneReceived` event, whose payload carries `tone` (the
spelled-token `Tone` enum of §2b) plus a `sequenceId`:

> Azure Communication Services provides you with `SequenceId` as part of the
> `ContinuousDtmfRecognitionToneReceived` event. Your application can use it to reconstruct the order
> in which the participant entered the DTMF tones.
> — same page, fetched 2026-09-10

That same page's own "Audio streaming" section points elsewhere for the websocket path — *"With audio
streaming, you can subscribe to real-time audio streams from an ongoing call. For more information …
see Quickstart: Server-side audio streaming"* — and never mentions the websocket in its DTMF sections.
Conversely the audio-streaming quickstart names only `EnableDtmfTones` and never mentions continuous
recognition. **So: the websocket path is enabled by `enableDtmfTones`, and the webhook path is enabled
by `StartContinuousDtmfRecognition`; they are documented as disjoint features with disjoint tone
spellings.**

**OPEN QUESTION 2b**: **no primary source states, in so many words, that
`StartContinuousDtmfRecognition` is *not* additionally required for tones to arrive on the media
websocket.** The disjointness above is inferred from two pages each documenting one mechanism and
neither cross-referencing the other for DTMF — strong, but not a statement. Phase 0's live evidence
(tones observed arriving on calls 2 and 3) is the stronger evidence here, and it is this project's
own, not a doc's; it should be read as settling the question in practice while the docs leave it
formally open.

**OPEN QUESTION 2c — ordering and timing.** **No primary source fetched offers any ordering or timing
guarantee between DTMF frames and audio frames on the same socket.** The audio-streaming concept page
gives timing for *audio* only — *"Framerate: 50 frames per second; Packet stream rate: 20-ms rate;
Data packet size: 640 bytes for 16,000 hz and 960 bytes for 24,000 hz"*
([Audio streaming overview](https://learn.microsoft.com/en-us/azure/communication-services/concepts/call-automation/audio-streaming-concept), fetched 2026-09-10, page `ms.date: 2024-11-24`) — and says nothing about DTMF at all; the
word does not appear on that page. The `DtmfData` payload carries a `timestamp` (§2a), which is
suggestive of ordering being the application's problem, but no doc says so. Notably, the *webhook*
path does ship an explicit ordering aid (`sequenceId`, quoted above) and the media-stream path
ships no equivalent — a difference worth knowing before Phase 5 assumes arrival order equals press
order for a four-digit entry.

---

## 3. The OpenTelemetry span-attribute surface Phase 6 will have to protect

B2 names OTel span attributes as one of four protected surfaces. `docs/phase4/findings.md` reports
that surface as uncovered rather than met, because this project emits no spans. This section
establishes what Phase 6 would actually create.

### 3a. The conventions moved, and are still Development-status

The `opentelemetry.io` GenAI span page now redirects:

> "GenAI semantic conventions have moved to the OpenTelemetry GenAI semantic conventions repository"
> — [opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/), fetched 2026-09-10

The live spec is [`open-telemetry/semantic-conventions-genai`](https://github.com/open-telemetry/semantic-conventions-genai),
`docs/gen-ai/gen-ai-spans.md`, whose header reads **`**Status**: [Development][DocumentStatus]`**
(fetched 2026-09-10, `main`). Every `gen_ai.*` attribute quoted below is badged *Development*, not
*Stable*. **Phase 6 will be building against a moving spec, and this note is a snapshot of
2026-09-10.**

### 3b. Which attributes carry model input and output

Three, all on the Inference span, all at requirement level **`Opt-In`** — the weakest level the
conventions define:

| Attribute | Requirement level | Description (verbatim from the spec table) |
|---|---|---|
| `gen_ai.input.messages` | `Opt-In` | "The chat history provided to the model as an input." |
| `gen_ai.output.messages` | `Opt-In` | "Messages returned by the model where each message represents a specific model response (choice, candidate)." |
| `gen_ai.system_instructions` | `Opt-In` | "The system message or instructions provided to the GenAI model separately from the chat history." |

— [`semantic-conventions-genai`, `docs/gen-ai/gen-ai-spans.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md), Inference span attribute table, fetched 2026-09-10

Each carries an explicit sensitivity warning in its own footnote:

> **[35] `gen_ai.input.messages`:** Messages MUST be provided in the order they were sent to the model.
> Instrumentations MAY provide a way for users to filter or truncate input messages.
>
> > [!Warning]
> > This attribute is likely to contain sensitive information including user/PII data.

> **[38] `gen_ai.system_instructions`:** This attribute SHOULD be used when the corresponding provider or API
> allows to provide system instructions or messages separately from the chat history.
>
> Instructions that are part of the chat history SHOULD be recorded in
> `gen_ai.input.messages` attribute instead.
>
> > [!Warning]
> > This attribute may contain sensitive information.

— same file, footnotes [35] and [38], fetched 2026-09-10

**The older `gen_ai.prompt` / `gen_ai.completion` attribute names are gone.** A grep of the current
attribute registry ([`docs/registry/attributes/gen-ai.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md), fetched 2026-09-10) finds no
`gen_ai.prompt` or `gen_ai.completion` entries — only `gen_ai.prompt.name`, `gen_ai.prompt.version`,
and `gen_ai.prompt.variable` (the last of which is *also* warned as possibly sensitive: *"This
attribute may contain sensitive information"*, footnote [14] of the registry). A B2 scanner written
against a hardcoded list of three attribute names would already be one rename behind; it should scan
the whole `gen_ai.*` namespace, and the `gen_ai.prompt.variable.<name>` form shows why — it is a
*prefix*, with the attribute key itself carrying caller-supplied naming.

### 3c. Attributes, events, or log records — the answer is "all three, deliberately"

The spec's own guidance section is explicit that this is a choice the application makes, and that
option 1 is the default:

> ## Capturing instructions, inputs, and outputs
>
> ### Full (buffered) content
>
> Model instructions, user messages, and model outputs are considered sensitive and
> are often large in size.
>
> Recording large or sensitive content in telemetry may be problematic due to high
> storage costs, regulatory requirements, or the need to enforce different access
> models for operational and user data.
>
> OpenTelemetry instrumentations SHOULD NOT capture them by default, but SHOULD
> provide an option for users to opt in.
>
> Application developers should choose an appropriate usage pattern based on
> application needs and maturity:
>
> 1. [Default] Don't record instructions, inputs, or outputs.
> 2. Record instructions, inputs, and outputs on the GenAI spans using corresponding
>    attributes (`gen_ai.system_instructions`, `gen_ai.input.messages`,
>    `gen_ai.output.messages`).
> ...
> 3. Store content externally and record references on the spans.

— [`semantic-conventions-genai`, `docs/gen-ai/gen-ai-spans.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md), fetched 2026-09-10

The same attributes may be recorded on events instead of spans, with a different serialisation:

> When the attribute is recorded on events, it MUST be recorded in structured form. When recorded on
> spans, it MAY be recorded as a JSON string if structured format is not supported and SHOULD be
> recorded in structured form otherwise.
> — same file, footnotes [35] and [36], fetched 2026-09-10

> If structured attributes are not yet supported on spans in a given language, the
> corresponding attribute value SHOULD be serialized to JSON string on spans and
> recorded in its structured form on events.
> — same file, "Recording content on attributes", fetched 2026-09-10

And there is a dedicated event that exists precisely to carry content off the trace:

> ## Event: `gen_ai.client.inference.operation.details`
> ...
> Describes the details of a GenAI completion request including chat history and parameters.
>
> This event could be used to store input and output details independently from traces.
>
> **Requirement level:** Opt-In.
> — [`semantic-conventions-genai`, `docs/gen-ai/gen-ai-events.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md), fetched 2026-09-10

**Direct consequence for B2.** The constraint's wording names "transcript, log line, OTel span
attribute, or persisted record". Under the current spec, the same content can travel as a **span
attribute**, as a **structured attribute on a span event**, or as a **log record** — and option 3
lets it leave the process entirely to external storage with only a reference on the span. A Phase 6
B2 scanner that reads span attributes only would miss two of the three in-process paths and all of
the fourth. **The surface Phase 6 must protect is wider than B2's wording, and this is the concrete
form of that.** (B2's existing log-record rule in `tests/test_zz_b2_leak_scan.py` already covers the
log-record path by construction, since it patches `logging.Logger.handle`; that does *not* extend to
the OTel logging pipeline, which does not go through stdlib handlers.)

### 3d. The switch and its default — off, in every form

**OpenTelemetry.** The current spec does not standardise a variable name; it names one only by
example, twice, as the illustrative gate:

> Instrumentations SHOULD NOT capture this attribute by default. Capture SHOULD be gated
> by an explicit user opt-in, for example `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`.
> — [`semantic-conventions-genai`, `docs/gen-ai/gen-ai-spans.md`](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md), footnotes [11] and [12] on the Memory span, fetched 2026-09-10

The Python implementation defines it and hard-codes the default:

> ```python
> def is_content_enabled() -> bool:
>     capture_content = environ.get(OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT, "false")
>
>     return capture_content.lower() == "true"
> ```
> — [`opentelemetry-python-contrib`, `instrumentation-genai/opentelemetry-instrumentation-openai-v2/src/opentelemetry/instrumentation/openai_v2/utils.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation-genai/opentelemetry-instrumentation-openai-v2/src/opentelemetry/instrumentation/openai_v2/utils.py), fetched 2026-09-10 (`main`)

**Exact name**: `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`. **Exact default**: `"false"`.
The instrumentor's module docstring states the same in prose and adds the value vocabulary:

> By default, the instrumentation aligns with `Semantic Conventions v1.30.0` and does not capture
> prompt or completion content. Behavior is controlled via environment variables:
>
> - ``OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`` - opt into the
>   latest GenAI semantic conventions. Required to access the newer attributes
>   and the ``span_only`` / ``event_only`` / ``span_and_event`` content modes.
>   Without this flag, the instrumentation stays on v1.30.0 conventions.
> - ``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`` - enable capture of
>   prompts, completions, tool arguments, and return values. Set to ``true``
>   on the legacy path, or one of ``span_only``, ``event_only``,
>   ``span_and_event`` when experimental conventions are enabled.
> - ``OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK=upload`` together with
>   ``OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH=<fsspec-uri>`` - upload
>   prompts and completions to an ``fsspec``-compatible destination …
> — [`opentelemetry-instrumentation-openai-v2/.../__init__.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation-genai/opentelemetry-instrumentation-openai-v2/src/opentelemetry/instrumentation/openai_v2/__init__.py), fetched 2026-09-10 (`main`)

Two things there matter to B2 beyond the on/off default: `span_and_event` means the *same* content
can land on both signals from one setting, and `OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK=upload`
exfiltrates content to a filesystem/S3/GCS path — a fourth destination that a span-attribute scanner
cannot see at all.

**Azure.** Azure's own equivalent, on the SDKs that implement GenAI tracing:

> You can capture prompt and completion contents by setting
> `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` environment to `true` (case insensitive).
> — [`azure-sdk-for-python`, `sdk/ai/azure-ai-inference/README.md`](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-inference/README.md), located via GitHub code search 2026-09-10

> To enabled content recording, set the `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` environment
> variable to `true`. Content in this context refers to chat message content, function call tool
> related function names, function parameter names and values.
> — [`azure-sdk-for-net`, `sdk/ai/Azure.AI.Agents.Persistent/README.md`](https://github.com/Azure/azure-sdk-for-net/blob/main/sdk/ai/Azure.AI.Agents.Persistent/README.md), located via GitHub code search 2026-09-10

Its default is documented as off:

> `enabled`: defaults to `false`. Env var: `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED`
> — [`azure-sdk-for-js`, `sdk/ai/ai-projects/src/tracing/configuration.ts`](https://github.com/Azure/azure-sdk-for-js/blob/main/sdk/ai/ai-projects/src/tracing/configuration.ts), located via GitHub code search 2026-09-10

Azure is migrating to the OTel name and keeping its own as a fallback:

> by OpenTelemetry, and all new applications are encouraged to use it when content recording is
> required. For legacy reasons, content recordings will also be enabled if
> `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` environment variable is set to `true`.
> — [`azure-sdk-for-python`, `sdk/ai/azure-ai-agents/README.md`](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-agents/README.md), located via GitHub code search 2026-09-10

**Both switches default to off.** For B2 that means the OTel surface is not merely empty today
because this project emits no spans; it would *still* be empty on the day Phase 6 turns tracing on,
unless someone additionally sets one of these two variables. **Phase 6's B2 work on this surface is
therefore primarily a negative assertion — that neither variable is set in the container's
environment, and that no code sets the equivalent programmatic flag — plus a scanner for the day
someone flips it.** That is a far cheaper obligation than "scan every span", and it is testable
without emitting a single span.

### 3e. Is the realtime/WebSocket path instrumented at all? — No. Plainly, no.

The Python OpenAI instrumentation wraps exactly five call sites, and enumerates them in its own
`_instrument`:

> ```python
>         wrap_function_wrapper(
>             "openai.resources.chat.completions",
>             "Completions.create", ...
>         wrap_function_wrapper(
>             "openai.resources.chat.completions",
>             "AsyncCompletions.create", ...
>         # Add instrumentation for the embeddings API
>         wrap_function_wrapper(
>             "openai.resources.embeddings",
>             "Embeddings.create", ...
>         wrap_function_wrapper(
>             "openai.resources.embeddings",
>             "AsyncEmbeddings.create", ...
>         if responses_module is not None and latest_experimental_enabled:
>             wrap_function_wrapper(
>                 "openai.resources.responses.responses",
>                 "Responses.create", ...
> ```
> — [`opentelemetry-instrumentation-openai-v2/.../__init__.py`](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation-genai/opentelemetry-instrumentation-openai-v2/src/opentelemetry/instrumentation/openai_v2/__init__.py), fetched 2026-09-10 (`main`)

`_uninstrument` unwraps the same five and nothing else. **There is no wrapper on
`openai.resources.realtime`, on the realtime WebSocket connection manager, or on any realtime event
send/receive path.** Chat completions, embeddings, responses — that is the whole surface.

The Azure Monitor OpenTelemetry distro's auto-instrumented library list contains no GenAI
instrumentation whatsoever:

> ```python
> _FULLY_SUPPORTED_INSTRUMENTED_LIBRARIES = (
>     _AZURE_SDK_INSTRUMENTATION_NAME,
>     "django",
>     "fastapi",
>     "flask",
>     "httpx",
>     "httpx2",
>     "psycopg2",
>     "requests",
>     "urllib",
>     "urllib3",
> )
> # Opt-in
> _PREVIEW_INSTRUMENTED_LIBRARIES = ()
> ```
> — [`azure-sdk-for-python`, `sdk/monitor/azure-monitor-opentelemetry/azure/monitor/opentelemetry/_constants.py`](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/monitor/azure-monitor-opentelemetry/azure/monitor/opentelemetry/_constants.py), fetched 2026-09-10 (`main`)

**So: the realtime path this project's relay uses is uninstrumented by both the OpenTelemetry OpenAI
instrumentation and the Azure Monitor distro. Adding `azure-monitor-opentelemetry` in Phase 6
produces spans for FastAPI, httpx, requests and the Azure SDK — and zero `gen_ai.*` attributes, because
nothing in that list touches the realtime socket.** This materially shrinks the surface B2 must
protect: `gen_ai.input.messages` and friends cannot appear on a realtime turn unless this project
writes the instrumentation itself.

There is one adjacent data point worth recording, because it shows the gap is being closed elsewhere
and could close here: Azure's **VoiceLive** SDK — a *different* service, not the Azure OpenAI realtime
endpoint this project uses — does instrument its realtime WebSocket, and shipped a fix for leaking
content by default:

> Telemetry: `gen_ai.event.content` on `.done` and related response events now correctly respects the
> content recording opt-in (`OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` or
> `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED`). Previously these events emitted message content
> (transcripts, function-call arguments, response bodies) unconditionally.
> — [`azure-sdk-for-net`, `sdk/voicelive/Azure.AI.VoiceLive/CHANGELOG.md`](https://github.com/Azure/azure-sdk-for-net/blob/main/sdk/voicelive/Azure.AI.VoiceLive/CHANGELOG.md), located via GitHub code search 2026-09-10

That is not this project's SDK and is cited only as evidence that (a) realtime GenAI instrumentation
uses a *different* attribute name again (`gen_ai.event.content`), and (b) a shipped Azure SDK has
already emitted realtime transcripts and function-call arguments unconditionally once. Both are
reasons for a Phase 6 B2 scanner to work by namespace and by value, not by a fixed attribute list.

### 3f. What captures bodies independently of GenAI instrumentation

**Azure OpenAI resource logs.** A diagnostic setting on `Microsoft.CognitiveServices/accounts`
offers five categories:

> | Category | Costs to export | Log table |
> | --- | --- | --- |
> | Audit | No | AzureDiagnostics |
> | AzureOpenAIRequestUsage | Yes | AzureDiagnostics |
> | ManagedNetworkEvent | Yes | AzureDiagnostics |
> | RequestResponse | No | AzureDiagnostics |
> | Trace | No | AzureDiagnostics |
> — [Monitoring data reference for Azure OpenAI | Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/monitor-openai-reference), "Supported resource logs for Microsoft.CognitiveServices/accounts", fetched 2026-09-10 (page `ms.date: 2026-05-19`)

**OPEN QUESTION 3a — and it is a B2 question, not a curiosity.** The reference page names a category
called **`RequestResponse`** and gives it **no description at all** — the table has no description
column, and neither that page nor [Monitor Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/monitor-openai)
(fetched 2026-09-10, page `ms.date: 2025-11-06`) states anywhere whether that category captures
request or response **bodies** — i.e. prompts and completions. Neither page contains a sentence
either promising or ruling out content capture. **A category literally named `RequestResponse`, whose
content coverage is undocumented, is exactly the kind of thing B2 must not be assumed safe about.**
Two things follow: this project should not enable that category on `aoai-azure-banking-voice-cc`
without first querying the destination table for rows and reading them (the "ARM 200 OK proves
creation, not delivery" rule in `CLAUDE.md` cuts both ways — it also means nobody has *checked* what
lands there); and if it is ever enabled, its rows are a fifth B2 surface. Note also that this project
sends the PIN over DTMF, not into the model, so a prompt-logging category would capture the PIN only
if the relay were to put it in a model message — which `_spoken_note`'s "outcome only, never a digit"
rule exists to prevent.

**Application Insights / Azure Monitor generally.** The distro's instrumented-library list (§3e)
covers HTTP client and server frameworks. **OPEN QUESTION 3b**: no primary source was fetched today
establishing whether `opentelemetry-instrumentation-fastapi` / `-httpx` / `-requests`, as configured
by the Azure Monitor distro, capture request or response **bodies** by default. The general OTel HTTP
conventions record method, URL, status and (opt-in) headers rather than bodies, but that was not
verified against those packages' source in this pass and is therefore **not asserted here**. Phase 6
should settle it by reading those instrumentations' source rather than assuming — the relay's own
FastAPI endpoint receives the ACS webhook and, in Phase 5, the media WebSocket, so a body-capturing
default there would put DTMF frames into telemetry. This is the highest-value unanswered question in
section 3 and it is cheap to answer.

---

## What this changes

Blunt version first: **the docs settle question 1, half-settle question 2, and reshape question 3.**
Only one of the three carried findings actually closes.

### Question 1 — the injected item shape: **settled at the specification level; still needs one live frame for Azure and for the version**

- **Confirmed correct**: `voice-agent/azbank_voice_agent/realtime/session.py:_spoken_note`. Every
  field is exactly what the generated spec requires — `type: "message"`, `role: "system"`,
  `content: [{"type": "input_text", ...}]`. `input_text` is not merely permitted on a system message,
  it is the *only* permitted content type there, and the spec's own docstring describes this use case
  ("system messages can be added at any point in the conversation… for smaller updates"). The
  function's docstring should stop implying the shape is speculative; what is unverified is Azure's
  and this version's acceptance of it, not the shape.
- **Confirmed correct**: sending `response.create` after the item. `response.create` is the documented
  trigger for inference; the item alone does not speak.
- **Contradicted — mildly, and not in this project's code**: the idea that assistant-role text is
  spelled `text`. Current spec says `output_text`. Nothing here sends an assistant message, so this
  is a note for Phase 5/6, not a defect.
- **A gap worth closing cheaply**: `_spoken_note` sends no `event_id`. The `error` event's
  `error.event_id` is the *only* documented way to attribute a rejection to a specific client frame.
  Stamping one turns "a rejection arrived at some point" into "*this* injection was rejected" — which
  is the exact requirement `docs/phase4/findings.md` §2 states. One field, no behaviour change, and it
  is what makes the Phase 5 real call diagnostic rather than merely pass/fail.
- **Still unverifiable from docs**: whether Azure's GA endpoint accepts it (OPEN QUESTION 1d), and
  whether `gpt-realtime-mini` `2025-10-06` specifically accepts it (OPEN QUESTION 1e). No source
  documents this event per model version, which is precisely the case B3 exists for. **Phase 1 settled
  its own central version question with a one-shot live probe after doc research stalled at the same
  wall; the same move applies and is the recommended one.** Also unverifiable: the `error.code`
  vocabulary (1b) and any response deadline (1c) — so the relay must key on `type == "error"` plus a
  correlated `event_id` plus its own timeout, and nothing narrower.

### Question 2 — the DTMF vocabulary: **frame shape confirmed; the tone vocabulary is NOT settled, and this is the one to worry about**

- **Confirmed correct**: `voice-agent/azbank_voice_agent/transport/acs.py:classify_inbound`. The
  `{"kind": "DtmfData", "dtmfData": {"data": ...}}` shape matches Microsoft's example, the .NET
  parser, the .NET round-trip test, and the JS parser. The lowercase-inbound /
  capitalised-outbound asymmetry that `outbound_audio_frame` relies on is corroborated by
  Microsoft's own Python sample on the same page. The defensive `(msg.get("dtmfData") or {}).get("data")`
  is well-judged: there is no schema behind this frame anywhere in the REST spec, so nothing
  constrains what may arrive.
- **Confirmed correct**: `voice-agent/azbank_voice_agent/app.py:133-141`. `enable_dtmf_tones=True`
  alongside `enable_bidirectional=True` and `start_media_streaming=True` is exactly the documented
  enabling path and matches the quickstart's Python sample field for field. `StartContinuousDtmfRecognition`
  is a different, webhook-delivered mechanism and is correctly not used.
- **NOT settled, and the docs cannot settle it**: the tone vocabulary for `*`, `#`, and `A`–`D`.
  Every primary example on this path shows a digit (`"3"`, `"5"`); the only enumerated tone
  vocabulary in Azure's specs is the spelled-token `Tone` enum (`"pound"`, `"asterisk"`), and it
  belongs exclusively to the webhook path, which has no reachability from the media-stream frame.
  **The keypad state machine's `*` = clear and `#` = ignore are unverified against any primary source
  and cannot be.** On the wrong vocabulary they fail silently — the caller who mis-keys can never
  clear. This is the single most consequential open item in this document.
  - Recommended without waiting for evidence: accept both vocabularies at the classifier
    (`"*"`/`"asterisk"`/`"star"` → clear, `"#"`/`"pound"`/`"hash"` → ignore). Cost is a mapping table
    and a test; benefit is that Phase 5's real call cannot fail on a spelling.
  - **Phase 5's real call must press `*` and `#`, not only digits.** A four-digit-only test call
    would leave this exactly as open as it is now while looking like it closed.
- **Three primary sources contradict each other** on what `data` even holds — literal character
  (docs example + .NET test), base64 (.NET `DtmfData` docstring), and a media subscription id (JS
  `DtmfData` docstring). This note goes with the executable evidence over the two docstrings and says
  so; a future session should not be surprised to find "base64" written in an Azure SDK.
- **Still unverifiable from docs**: ordering/timing between DTMF and audio frames (OPEN QUESTION 2c).
  No guarantee exists in any source. The webhook path ships a `sequenceId` for exactly this problem
  and the media-stream path ships nothing equivalent — so **Phase 5 must not assume arrival order
  equals press order** without observing it. That assumption is currently implicit in a four-digit
  accumulator.

### Question 3 — the OTel surface: **the surface is much smaller than feared, and differently shaped**

- **`docs/phase4/findings.md`'s reporting of B2's OTel surface as uncovered rather than met is
  vindicated and can now be made precise.** It is not merely "we emit no spans"; it is that the
  realtime path is uninstrumented by every off-the-shelf option, and both content switches default
  off. The honest Phase 6 statement is: *the surface is empty for three independent reasons, each
  separately checkable.*
- **Confirmed for Phase 6 planning**: adding `azure-monitor-opentelemetry` produces spans for
  FastAPI, httpx, requests, urllib and the Azure SDK — and **no `gen_ai.*` attributes at all**, because
  no GenAI instrumentation is in its list and the OTel OpenAI instrumentation wraps only
  chat-completions, embeddings and responses. **The realtime WebSocket path is uninstrumented.** Any
  `gen_ai.*` attribute in this project would have to be written by this project.
- **Confirmed**: the switches and their defaults —
  `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` (default `"false"`, hard-coded in the Python
  implementation) and Azure's `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` (documented default
  `false`). **Phase 6's cheapest and strongest B2 assertion on this surface is a negative one**: neither
  variable is set in the container environment, and no code sets the programmatic equivalent. That is
  testable today, with no spans and no deployment.
- **Reshapes B2's stated surface**: content can travel as a span attribute, as a structured attribute
  on a span event, as a log record, or — via `OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK=upload` —
  out of the process entirely to a filesystem or object store. B2's wording names one of those four.
  A scanner reading span attributes only would be an empty claim of the same kind
  `docs/phase4/findings.md` already refuses to make elsewhere. Scan the `gen_ai.*` namespace by
  prefix and by value, not a fixed list of three names: the older `gen_ai.prompt`/`gen_ai.completion`
  names are already gone, `gen_ai.prompt.variable.<name>` is a caller-named prefix, and Azure's own
  realtime SDK uses a different name again (`gen_ai.event.content`).
- **Still unverifiable from docs, and both are worth a Phase 6 ticket**: (3a) whether the Azure OpenAI
  `RequestResponse` diagnostic-log category captures request/response **bodies** — undocumented, and a
  category with that name and no description should not be enabled on this resource until its
  destination table has been queried and read; (3b) whether the FastAPI/httpx/requests
  instrumentations capture bodies by default — not verified in this pass and therefore not asserted,
  but directly relevant because the relay's own FastAPI app receives the ACS webhook and the media
  WebSocket. (3b) is cheap to close by reading source and should be closed before Phase 6 enables
  anything.

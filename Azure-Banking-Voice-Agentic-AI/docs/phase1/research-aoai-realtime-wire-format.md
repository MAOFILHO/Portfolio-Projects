# Phase 1 research — Azure OpenAI Realtime API wire format

Pure documentation research for the ACS-media-streaming <-> Azure OpenAI realtime bridge. No
bridge/application code was written for this task. All claims below are sourced from live fetches
of primary docs performed 2026-08-29 (URL + fetch date next to every claim), per
`docs/PLAN.md` decision to never answer from memory on a factual unknown. Where a primary source did
not answer a question clearly, that is marked **OPEN QUESTION** rather than filled in by inference.

Deployment this research is scoped to: `aoai-azure-banking-voice-cc`, model `gpt-realtime-mini`,
model **version `2025-10-06`**, SKU `GlobalStandard`, `NoAutoUpgrade`, region Canada Central (per
`PROJECT_STATE.md` / `docs/PLAN.md`). B3 requires every capability claim to be pinned to this exact
model+version, not the model name alone — that discipline is followed throughout.

---

## 1. `session.update` message shape

Azure's realtime API is explicitly a pass-through of OpenAI's own spec, with one documented
deviation:

> "The Azure OpenAI Realtime API follows the OpenAI Realtime API specification. For the full API
> reference, see the OpenAI Realtime API reference. **Azure deviation:** The accepted values for the
> `model` field in `input_audio_transcription` settings differ from the OpenAI reference. Azure
> OpenAI requires the name of the existing model deployment for the field, like
> `my-gpt-4o-transcribe-deployment`."
> — [Realtime API reference - Microsoft Foundry | Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/openai/realtime-audio-reference), fetched 2026-08-29

**Two session shapes exist in Microsoft's own docs, not clearly reconciled — see OPEN QUESTION
below.** The how-to guide's example (older/flatter shape, shown as the `session.created` echo and as
a `session.update` sample) uses top-level fields:

```json
{
  "type": "session.update",
  "session": {
    "voice": "alloy",
    "instructions": "Your custom system instructions.",
    "input_audio_format": "pcm16",
    "input_audio_transcription": { "model": "<your-transcription-deployment-name>" },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 200,
      "create_response": true
    },
    "tools": []
  }
}
```
— [Use the GPT Realtime API for speech and audio with Azure OpenAI](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio), fetched 2026-08-29 (doc dated `ms.date: 2026-07-29`)

The **same page**, in its "voice-agent quickstart" code sample referenced from the WebSockets
how-to, uses a different, nested GA shape:

```javascript
const sessionConfig = {
    'type': 'realtime',
    'instructions': 'You are a helpful assistant. You respond by voice and text.',
    'output_modalities': ['audio'],
    'audio': {
        'input': {
            'transcription': { 'model': 'whisper-1' },
            'format': { 'type': 'audio/pcm', 'rate': 24000 },
            'turn_detection': {
                'type': 'server_vad',
                'threshold': 0.5,
                'prefix_padding_ms': 300,
                'silence_duration_ms': 200,
                'create_response': true
            }
        },
        'output': {
            'voice': 'alloy',
            'format': { 'type': 'audio/pcm', 'rate': 24000 }
        }
    }
};
```
— [Use the GPT Realtime API via WebSockets](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio-websockets), fetched 2026-08-29

Both shapes agree on the essentials needed for Phase 1:

- **System prompt**: the `instructions` field, top-level under `session`, a plain string. Confirmed
  in both shapes above, and in the `session.created` echo example (below).
- **`session.type`**: GA docs say `session.update` uses `session.type` to pick the session kind —
  `"realtime"` for voice-agent speech-to-speech (what Phase 1 needs) vs `"transcription"` for
  transcription-only sessions. — [how-to/realtime-audio](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio), fetched 2026-08-29
- **All session fields are optional.** "All session parameters are optional and can be omitted if
  not needed." — same source.
- **`tools`** stays a top-level array sibling of `instructions`/`audio` even in the GA nested shape —
  confirmed by the GA-shape MCP-tools example on the same page:
  ```json
  { "session": { "type": "realtime", "tools": [ { "type": "mcp", "server_label": "stripe", "..." : "..." } ] } }
  ```
  — [how-to/realtime-audio](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio), fetched 2026-08-29

The server confirms configuration with a `session.updated` event. A full `session.created` echo
(older/flat shape) from the same page:

```json
{
  "type": "session.created",
  "session": {
    "model": "gpt-4o-mini-realtime-preview-2024-12-17",
    "modalities": ["audio", "text"],
    "instructions": "Your knowledge cutoff is 2023-10. ...",
    "voice": "alloy",
    "turn_detection": { "type": "server_vad", "threshold": 0.5, "prefix_padding_ms": 300, "silence_duration_ms": 200 },
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "input_audio_transcription": null,
    "tool_choice": "auto",
    "temperature": 0.8,
    "max_response_output_tokens": "inf",
    "tools": []
  }
}
```

**OPEN QUESTION 1a**: Microsoft's own docs mix the older flat `session.update` shape
(`input_audio_format`, `output_audio_format`, `modalities` as top-level session fields) with the
newer GA nested shape (`session.type: "realtime"`, `output_modalities`, `audio.input.format`,
`audio.output.format`) without stating which one the current GA `/openai/v1/realtime` endpoint
actually requires, or whether it accepts both for backward compatibility. Community reports
independently confirm this is a live migration pain point: *"Realtime API Beta -> Realtime API GA -
Receiving type error with session.audio.input.format"* (OpenAI Developer Community, not a primary
source, surfaced via search 2026-08-29, not independently verified against Azure's endpoint). Before
the bridge is built, this needs to be resolved against the **live** Azure endpoint for the
`aoai-azure-banking-voice-cc` deployment (not inferred from docs) — send a real `session.update` in
each shape and see which one the server accepts/echoes.

**OPEN QUESTION 1b**: `max_response_output_tokens`, `temperature`, `tool_choice`, and `modalities`
appear in the `session.created` echo but the how-to guide never states explicitly which of these are
settable via `session.update` vs read-only/response-time-only fields. The Azure how-to page states
`response.create` can override "output and response generation properties," but doesn't enumerate
which properties that includes. Not resolved by any primary source fetched.

---

## 2. Audio format

**ACS side (confirmed in Phase 0, restated here for reference only, not re-verified in this task):**
PCM 16-bit, 24kHz, mono (`Pcm24KMono`), base64-encoded in `AudioData`/`DtmfData` JSON frames.

**Azure OpenAI realtime side — two format-value vocabularies exist depending on schema version**
(same split as section 1):

- **Older/flat schema** (`input_audio_format` / `output_audio_format` as plain strings): values seen
  in Microsoft's own troubleshooting section and OpenAI's own examples are `pcm16`, plus (per OpenAI's
  general realtime docs, not Azure-specific) `g711_ulaw` and `g711_alaw`.
  The Azure how-to page's troubleshooting section states explicitly, without qualifying input vs.
  output separately:
  > "The Realtime API expects audio in a specific format: **Format**: PCM 16-bit (pcm16).
  > **Channels**: Mono (single channel). **Sample rate**: 24kHz."
  — [how-to/realtime-audio, "Audio format issues"](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio), fetched 2026-08-29
- **GA nested schema** (`audio.input.format` / `audio.output.format` as objects): values are
  MIME-type-like strings — `audio/pcm` (24kHz only), `audio/pcmu` (G.711 μ-law), `audio/pcma` (G.711
  A-law) — each with a `rate` field. Confirmed by the GA voice-agent quickstart sample (section 1)
  using `{ "type": "audio/pcm", "rate": 24000 }` for both input and output, and independently by the
  OpenAI Realtime API reference:
  > `audio/pcm` — "Only a 24kHz sample rate is supported." `audio/pcmu` — G.711 μ-law. `audio/pcma` —
  > G.711 A-law. All audio transmitted in events like `input_audio_buffer.append` must be
  > Base64-encoded audio bytes.
  — [Realtime API Reference — resources/realtime](https://developers.openai.com/api/reference/resources/realtime), fetched 2026-08-29

**Match assessment**: `audio/pcm` at `rate: 24000` (equivalently, the flat schema's `pcm16` at the
troubleshooting section's stated 24kHz/mono) is **PCM16, 24kHz, mono — an exact match to ACS's
`Pcm24KMono`** on sample rate, bit depth, and channel count. No sample-rate or bit-depth conversion
should be required in either direction; only the transport envelope differs — ACS wraps base64 audio
in its own `{"Kind":"AudioData","AudioData":{"Data":"<base64>"}}` JSON frame while the realtime API
wraps the same base64 payload in `input_audio_buffer.append` (client→server, field `audio`) and — per
a live probe against `aoai-azure-banking-voice-cc`, 2026-08-29, output_modalities=["audio"] —
**`response.output_audio.delta`** (field `delta`), **not** `response.audio.delta` as this document
previously stated from doc prose alone. The installed `openai` Python SDK's own generated type
(`response_audio_delta_event.py`) already carried `type: Literal["response.output_audio.delta"]`,
contradicting its own filename — the live probe was run specifically to resolve that contradiction
rather than trust either source, and confirmed the SDK's wire value, not the docs' prose, is what
Azure actually sends: 8 `response.output_audio.delta` events observed (6400–38400 base64 chars each)
plus separate `response.output_audio_transcript.delta` events (a text transcript stream, not audio —
do not confuse the two). The bridge's job is therefore re-enveloping the base64 payload between the
two JSON frame shapes, not resampling/re-encoding audio.

Azure's own troubleshooting section adds a chunking recommendation not stated by OpenAI's own docs
fetched today: "Check that audio chunks aren't too large; send audio in small increments (recommended:
100ms chunks)." — [how-to/realtime-audio](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio), fetched 2026-08-29

**OPEN QUESTION 2**: Neither Azure's troubleshooting note ("PCM 16-bit... Mono... 24kHz") nor the GA
schema's `audio/pcm` entry states explicitly whether that single 24kHz/16-bit/mono spec applies
identically to *both* `input` and `output`, or only documents one direction and assumes symmetry. The
GA quickstart sample does set the same `{ "type": "audio/pcm", "rate": 24000 }` for both
`audio.input.format` and `audio.output.format`, which is the strongest evidence of symmetry, but no
doc states "input and output must use the same format" as a hard rule.

---

## 3. Function/tool calling over the realtime connection

**Tool declaration** (session config, `tools` array — format confirmed by OpenAI's realtime-tools
guide, and structurally consistent with the `tools: []` field seen in both Azure session shapes above):

```json
{
  "type": "function",
  "name": "function_name",
  "description": "What the function does",
  "parameters": {
    "type": "object",
    "properties": { "...": "..." },
    "required": ["..."]
  }
}
```
— [Realtime conversations | OpenAI API](https://developers.openai.com/api/docs/guides/realtime-conversations), fetched 2026-08-29

**Model requests a call** — streamed incrementally, then finalized:

- `response.function_call_arguments.delta` — incremental argument-JSON chunks (not useful to act on
  individually; "Streaming isn't very useful for function calling — you need the complete function
  call structure before you can call the function.")
- `response.function_call_arguments.done` — the event to actually wait for. Exact shape:
  ```json
  {
    "event_id": "event_5556",
    "type": "response.function_call_arguments.done",
    "response_id": "resp_002",
    "item_id": "fc_001",
    "output_index": 0,
    "call_id": "call_001",
    "name": "get_weather",
    "arguments": "{\"location\": \"San Francisco\"}"
  }
  ```
  — [Server events | OpenAI API Reference](https://platform.openai.com/docs/api-reference/realtime-server-events/response/function_call_arguments/done), surfaced via search and cross-checked against `response.done`'s own output-item shape 2026-08-29
- The same information is also present, non-streamed, inside the terminal `response.done` event's
  `response.output[]` array as an item with `"type": "function_call"`, carrying `name`, `arguments`
  (a JSON string), and `call_id` — described as "a system-generated ID for this function call — you
  will need this ID to pass a function call result back to the model."
  — [Realtime conversations | OpenAI API](https://developers.openai.com/api/docs/guides/realtime-conversations), fetched 2026-08-29

**Sending the tool result back** — a `conversation.item.create` with a `function_call_output` item,
keyed by the `call_id` from the request:

```json
{
  "type": "conversation.item.create",
  "item": {
    "type": "function_call_output",
    "call_id": "call_sHlR7iaFwQ2YQOqm",
    "output": "{...result...}"
  }
}
```

**Making the model speak the answer, not just call the tool silently**: submitting the
`function_call_output` item alone does not produce a spoken/text response — a subsequent
`response.create` event must be sent to make the model generate a new response incorporating the
tool output. Both facts confirmed together at
[Realtime conversations | OpenAI API](https://developers.openai.com/api/docs/guides/realtime-conversations), fetched 2026-08-29.

This event flow (`response.function_call_arguments.done` → `conversation.item.create` with
`function_call_output` → `response.create`) is OpenAI's general Realtime API behavior, not
Azure-specific; no Azure doc fetched today restates or diverges from it. Given Azure's own reference
page states it "follows the OpenAI Realtime API specification" (section 1), this project should treat
it as applicable — **contingent on section 5's open question about whether `gpt-realtime-mini`
`2025-10-06` supports function calling at all.**

**OPEN QUESTION 3**: No Azure-specific doc fetched today shows a worked function-calling example
against a `/openai/v1/realtime` (GA) session — only the MCP-server-tools example (section 1) and
OpenAI's own generic guide. Whether Azure's GA endpoint streams
`response.function_call_arguments.delta` events at all is separately in question — a Microsoft Q&A
thread titled *"Realtime API doesn't stream response.function_call_arguments.delta events"* was
surfaced by search (not fetched/verified as primary evidence here; flagged for follow-up) claiming
Azure only sends `response.text.delta` for a function call, never the arguments-delta events, while
the same client against api.openai.com receives them correctly. If true, the bridge must not depend
on delta events and should key off `response.function_call_arguments.done` / `response.done` only —
recommended regardless, but this needs live confirmation against the actual
`aoai-azure-banking-voice-cc` deployment before Phase 1 build, not assumed from a forum post.

---

## 4. Turn detection

`turn_detection` (flat schema) / `audio.input.turn_detection` (GA nested schema) accepts three types:

- **`none`** — manual/push-to-talk. Caller must send `input_audio_buffer.commit` and `response.create`
  explicitly; useful for push-to-talk or when an external VAD (e.g., caller-side) controls flow.
- **`server_vad`** (default) — "Automatically chunks the audio based on periods of silence." Fields:
  - `threshold` (0–1) — "Activation threshold... A higher threshold will require louder audio to
    activate."
  - `prefix_padding_ms` — audio to include before VAD-detected speech start.
  - `silence_duration_ms` — silence duration before speech-stop is declared; "shorter values [mean]
    turns will be detected more quickly" (documented latency/false-cutoff tradeoff: shorter =
    faster turn detection but higher risk of cutting the caller off mid-sentence; longer = fewer
    false cutoffs but added latency before the model responds).
  - `create_response` (speech-to-speech only) — if `false`, VAD still detects end-of-speech but the
    server will not auto-generate a response until the client sends `response.create` — usable for a
    moderation step before the model answers.
  - `interrupt_response` (speech-to-speech only) — not documented beyond being conversation-mode
    scoped; no further detail found today.
- **`semantic_vad`** — "Chunks the audio when the model believes, based on the words said by the
  user, that they have completed their utterance," using a semantic classifier scoring how likely the
  user is done speaking, waiting out a timeout when that probability is low. Field: `eagerness` — one
  of `low` ("let the user take their time to speak"), `medium`, `high` ("chunk the audio as soon as
  possible"), or `auto` (default, equivalent to `medium`) — this is the documented latency/interruption
  tradeoff knob: higher eagerness cuts in faster but risks interrupting; lower eagerness waits longer
  and is less likely to interrupt or chunk a transcript prematurely.

Sources: [how-to/realtime-audio, "Voice activity detection (VAD) and the audio buffer"](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio), fetched 2026-08-29; VAD field/tradeoff detail cross-checked against [Voice activity detection (VAD) | OpenAI API](https://developers.openai.com/api/docs/guides/realtime-vad), fetched 2026-08-29.

**Known Azure-specific caveat, not independently re-verified today**: a Microsoft Q&A thread titled
*"Azure OpenAI Realtime API Ignores semantic_vad Turn Detection Setting"* was surfaced by search,
reporting that on Azure, `semantic_vad` configuration is accepted and echoed back correctly by
`session.updated`, but zero `input_audio_buffer.speech_started` events are subsequently emitted and
`interrupt_response` has no effect. This is a community report, not confirmed against a primary
Microsoft doc or against the live `aoai-azure-banking-voice-cc` deployment — flagged as an
**OPEN QUESTION**, not assumed true. If accurate, Phase 1 should default to `server_vad`
(the documented Azure default) rather than `semantic_vad`, and confirm the choice with a real test
call before relying on it, consistent with the project's "verify against live state" resume
discipline.

---

## 5. Version-specific facts

**API version / endpoint**: Azure's current guidance is to use the GA endpoint form, with no
date-based `api-version` query parameter:

> "For the Realtime API, use the GA endpoint with `/openai/v1` in the URL. Don't use date-based API
> versions or the `api-version` query parameter."
— [how-to/realtime-audio](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio), fetched 2026-08-29 (page dated `ms.date: 2026-07-29`)

The WebSocket URL construction shown in the current quickstart is `wss://{endpoint}/openai/v1`
(no `api-version=...` suffix) — [Use the GPT Realtime API via WebSockets](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio-websockets), fetched 2026-08-29.
Older preview-era docs and examples elsewhere use date-based `api-version` values
(e.g. `2024-10-01-preview`) against a different, non-`/v1` endpoint shape — those are documented as
superseded by the GA form, not as an alternative still recommended for new work.

**Supported realtime models** (Azure, per the current how-to page) include, among others:
`gpt-4o-realtime-preview` (`2024-12-17`), `gpt-realtime` (`2025-08-28`), **`gpt-realtime-mini`
(`2025-10-06`)**, `gpt-realtime-mini` (`2025-12-15`), `gpt-realtime-1.5` (`2026-02-23`). Both
`gpt-realtime-mini` versions are listed as supported for global deployments, with the Realtime API
overall stated to support "up to 32,000 input tokens and 4,096 output tokens" (this token-limit figure
is not broken out per model/version in the source).
— [how-to/realtime-audio, "Supported models"](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio), fetched 2026-08-29; token limits cross-checked against the [Foundry Models sold by Azure comparison table](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure), fetched 2026-08-29 (`gpt-realtime` `2025-08-28` (GA) / `gpt-realtime-mini` `2025-10-06` / `gpt-realtime-mini` `2025-12-15` share one table row: "Input: 32,000 Output: 4,096").

### RESOLVED 2026-08-29 — live probe against `aoai-azure-banking-voice-cc` confirms: YES

The open question below was settled empirically, not by further doc research, per its own
recommendation. A live WebSocket session was opened against the actual deployment (`gpt-realtime-mini`,
model version `2025-10-06`, Canada Central — confirmed via `az cognitiveservices account deployment
list` immediately before the probe), declaring one trivial tool (`get_time`, no parameters) and
sending a text prompt ("What time is it?") designed to trigger it.

**Result: unambiguous yes.** The `session.updated` echo included the declared tool verbatim (not
silently dropped). The model did not answer in text — it emitted a `function_call` item, and the
full event sequence included both `response.function_call_arguments.delta` (`delta: "{}"`) *and*
`response.function_call_arguments.done` (`call_id`, `name: "get_time"`, `arguments: "{}"`), with
zero error events end to end. This also resolves this document's own OPEN QUESTION 3 (whether Azure
streams `function_call_arguments.delta` at all) — for this deployment, on this run, it does.

**No B3 pin change is needed.** `gpt-realtime-mini` `2025-10-06` supports function/tool calling on
Azure; Phase 1's scope is buildable against the currently-pinned deployment as-is. The changelog-based
inference above (that `2025-12-15` reaching "parity... in function-calling" implied `2025-10-06`
lacked it) turned out to be wrong, or at least not applicable to basic single-tool function calling —
left in place below verbatim as the reasoning trail, not deleted, since the empirical result is what
should be trusted, not silence over what was inferred first and why it was worth checking.

Full raw request/response event log: probe was run from a throwaway script (not committed — pure
diagnostic, no bridge code), output preserved as `docs/phase1/evidence/tool-calling-probe-2026-08-29.json`.

---

### Does `gpt-realtime-mini` `2025-10-06` support function/tool calling on Azure? — the load-bearing finding (superseded by the live result above, kept for the reasoning trail)

**This is the single most important finding of this research task, and it is a version-specific gap,
not a settled "yes."** Azure's own changelog draws an explicit before/after line between the two
`gpt-realtime-mini` versions:

> **"Realtime-mini (speech-to-speech) model update — `gpt-realtime-mini-2025-12-15`**
> - Feature parity with full `gpt-realtime` model in instruction-following and function-calling.
> - Input and output are both audio, and deployment is API-only."
— [What's new in Azure OpenAI in Microsoft Foundry Models? (classic)](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/whats-new), "December 2025" section, fetched 2026-08-29

Read plainly, this changelog entry states that **function-calling *parity* with the full
`gpt-realtime` model was a `2025-12-15`-version improvement** — which only makes sense as an
improvement if the earlier `2025-10-06` version (the one this project has deployed) did **not** have
that parity. The changelog does not use the words "added function calling" or "did not previously
support function calling" verbatim, so this is Microsoft's own wording read at face value, not a
paraphrase claiming more precision than the source offers.

This is independently consistent with an external, non-primary report: an OpenAI Developer Community
thread titled *"Function calling support for gpt-realtime-mini,"* posted 2025-10-08 (days after the
`2025-10-06` version's release), asserting plainly that the newly-released `gpt-realtime-mini` lacked
function calling and was "unusable for any serious application" without it. No official OpenAI staff
reply confirming or denying this was visible in the thread as fetched. This is a community claim, not
a primary source, and is cited here only as corroborating context for the timeline, not as proof on
its own.
— [Function calling support for gpt-realtime-mini](https://community.openai.com/t/function-calling-support-for-gpt-realtime-mini/1361464), fetched 2026-08-29

**Counter-signal, also from a primary-ish source, that complicates a clean "no" answer**: OpenAI's own
current model page for `gpt-realtime-mini` lists `function_calling` under "Supported features" with no
caveat:
— [GPT-Realtime Mini Model | OpenAI API](https://developers.openai.com/api/docs/models/gpt-realtime-mini), fetched 2026-08-29

**Why this doesn't resolve the question**: that OpenAI model page is not version-pinned — it
documents whatever `gpt-realtime-mini` currently means on OpenAI's own platform (api.openai.com),
which by 2026-08-29 likely already reflects the `2025-12-15`-parity behavior or later, not the
`2025-10-06` snapshot this project's Azure deployment is actually pinned to (B3: `NoAutoUpgrade`, so
this deployment stays on `2025-10-06` regardless of what OpenAI's page says about the model family
today). It also documents OpenAI's own realtime API, not Azure's — and this project runs on Azure.

**OPEN QUESTION 5 (the central one) — RESOLVED 2026-08-29, see the callout above this section.**
Answer: **yes**, confirmed by a live probe against the actual deployment, not by further doc
inference. The reasoning below is retained as the trail that motivated the check, not as the
project's current belief.

No primary source fetched during the doc-research pass stated, in so many words, "the
`gpt-realtime-mini` model at model version `2025-10-06`, on Azure specifically, does or does not
support function/tool calling." The strongest evidence available at the time — Azure's own changelog
wording about `2025-12-15` reaching "feature parity... in function-calling" — pointed toward
`2025-10-06` having weaker or absent function-calling support relative to the full `gpt-realtime`
model, but that was an inference from changelog phrasing, not a direct statement. The live probe
above settled it empirically instead of resolving the ambiguity by further reading.

---

## Summary of open questions for a future session

1. **(1a) Session shape ambiguity**: Azure docs show both an older flat `session.update` shape
   (`input_audio_format`, `output_audio_format`, `modalities`) and a newer GA nested shape
   (`session.type`, `output_modalities`, `audio.input.format`, `audio.output.format`) without stating
   which the live GA `/openai/v1/realtime` endpoint actually requires or whether both are accepted.
   Needs a live probe against `aoai-azure-banking-voice-cc`.
2. **(1b)** Which session fields (`temperature`, `tool_choice`, `modalities`,
   `max_response_output_tokens`) are settable via `session.update` vs. response-time-only via
   `response.create` is not enumerated in any doc fetched.
3. **(2) Input/output format symmetry**: no doc states as a hard rule that `audio.input.format` and
   `audio.output.format` must match; only an example that happens to set both to the same value.
4. **(3) Streaming of function-call argument deltas on Azure**: an unverified community report claims
   Azure's realtime endpoint never emits `response.function_call_arguments.delta` (only
   `response.text.delta`) for a function call, unlike api.openai.com. Not confirmed against this
   project's deployment.
5. **(4) `semantic_vad` reliability on Azure**: an unverified community report claims Azure silently
   drops `input_audio_buffer.speech_started` events and ignores `interrupt_response` when
   `semantic_vad` is configured, despite `session.updated` echoing the setting back successfully.
   Not confirmed; recommend defaulting to `server_vad` until checked live.
6. ~~**(5) THE central open question**~~ — **RESOLVED 2026-08-29 by live probe: YES**,
   `gpt-realtime-mini` `2025-10-06` supports function/tool calling on Azure. See the resolution
   callout in section 5. No pin change needed; Phase 1's tool-calling scope is buildable as-is.

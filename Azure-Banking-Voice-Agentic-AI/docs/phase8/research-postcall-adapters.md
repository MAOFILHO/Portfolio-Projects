# Phase 8 research — post-call adapters: Language PII redaction and `gpt-5.4-mini` summary

Pure documentation research gating the two real adapters behind `postcall/pipeline.py`'s `Redactor` and
`Summarizer` protocols. **No application code was written or changed.** All claims come from primary
sources fetched or queried **2026-09-19**: Microsoft Learn, the OpenAPI specs in
`Azure/azure-rest-api-specs` (main @ `36632f0a92117a10cc543283143be6c663d15f75`), the Azure SDK for Python
(main @ `6723f2d15aa589fdd2a6f1140ccba179069dcddf`), `openai/openai-python` (tag `v3.6.0`, main @
`69a2c1db6feacf32be6693809e7cab1c3b49cad7`), PyPI JSON, the Azure Retail Prices API, and **read-only**
`az` calls against this subscription (no keys listed, nothing created or changed). Where no primary
source settles a point it is marked **UNVERIFIED**. This note does not repeat
`research-language-pii-quota.md` (no F0 tier, Canada Central available, $1.00 per 1,000 text records,
1000 rps / 1000 rpm).

Method note: the fetch tool summarises pages with a small model and **mangled two role GUIDs**. Every GUID
below was re-checked against the raw built-in-roles HTML (`curl`) and against live ARM
(`az role definition list`); the two agree.

---

## Answer up front

| Decision needed | Answer | Confidence |
|---|---|---|
| Language API for the agent's turns | **Conversation PII job API**, GA `2024-11-01`: `POST /language/analyze-conversations/jobs`, poll `Operation-Location`. Redacted text is `redactedContent.text`. The GA sync **Text PII** API (`2026-05-01`, `redactedText` per document) also exists, but caps at 5 docs/request and, per Microsoft's own transparency note, detects worse one turn at a time | Medium-high. Both are documented; the choice is a trade-off (Q1a) |
| Language auth | Entra bearer, scope `https://cognitiveservices.azure.com/.default`; role **Cognitive Services Language Reader** `7628b7b8-a8b2-4cdc-b46f-e9b35248918e` (its dataActions include `analyze-conversations/jobs/action` and `analyze-text/action`). Custom subdomain **already set** | High |
| SDK vs REST for Language | **Raw REST via `httpx`.** Stable `azure-ai-language-conversations` 1.1.0 *removed* Conversation PII; only 2.0.0b2 (beta) has it. `azure-ai-textanalytics` 5.4.0 tops out at api-version `2023-04-01` | High |
| Bare digit string reliably redacted? | **No, not documented.** Microsoft: "without context, a ten-digit number is just a number". Closest category is Conversation `NumericIdentifier`. Add a deterministic digit-run scrub and fail closed | High that it is not guaranteed |
| Model API surface | `gpt-5.4-mini` `2026-03-17` supports **both Chat Completions and Responses**, plus structured outputs. Docs recommend Responses; endpoint is the v1 path `/openai/v1/` with no `api-version` | High |
| Parameters | Send `max_completion_tokens` and optionally `reasoning_effort`, `verbosity`. **Never** `max_tokens`, `temperature`, `top_p`, penalties, `logprobs`, `logit_bias` | High (documented list). `reasoning_effort` default and whether `none` is allowed for *mini*: UNVERIFIED |
| OpenAI auth | Role **Cognitive Services OpenAI User** `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`. Client: `AsyncOpenAI(base_url=".../openai/v1/", api_key=<async token provider>)`. **Token scope conflict**: Learn v1 pages say `https://ai.azure.com/.default`; the v1 OpenAPI spec and azure-identity say `https://cognitiveservices.azure.com/.default` | High on role and client. **Scope: UNVERIFIED** until one live call |
| Read model version back from a response | Do not rely on it. `model` is documented only as "the model used"; Learn examples show base-model-plus-date strings. B3's ARM read (`boot.py`) stays the authority | Medium |
| Price | Global Standard meters: **$0.75 / 1M input, $4.50 / 1M output** ($0.075 cached input). No `canadacentral` row exists in the Retail Prices API | High for the Global meter; canadacentral billing UNVERIFIED |
| **Live blocker** | The `gpt-5.4-mini` deployment has capacity 1: ARM reports `request 1 / 60 s`, `token 1000 / 60 s`. The docs count *prompt + `max_completion_tokens`* against the token limit, so a realistic summary request will 429 | High (raw ARM values). Interpretation derived |
| **B3 gap** | Text deployment is `OnceNewDefaultVersionAvailable`; the realtime deployment is `NoAutoUpgrade` | High (live ARM) |

---

## Q1 — Azure AI Language PII redaction

### 1a. Endpoints, verbs, api-versions, and which API fits

**Conversation PII job API (asynchronous only).**

- `POST {endpoint}/language/analyze-conversations/jobs?api-version=2024-11-01` returns **202** and an
  `Operation-Location` header ("The location for monitoring the operation state").
- `GET {endpoint}/language/analyze-conversations/jobs/{jobId}?api-version=2024-11-01[&showStats=true]`
  returns **200** `AnalyzeConversationJobState`.
- `POST {endpoint}/language/analyze-conversations/jobs/{jobId}:cancel` returns 202.
- Source: `specification/cognitiveservices/data-plane/LanguageAnalyzeConversations/stable/2024-11-01/analyzeconversations.json`
  (paths, `x-ms-long-running-operation`). The stable directory holds `2022-05-01, 2023-04-01, 2024-05-01,
  2024-11-01`; preview holds `2025-05-15-preview, 2025-11-15-preview`. **Latest GA: `2024-11-01`.**
  Learn agrees: "Stable: 2024-11-01 (GA) / Preview: 2025-11-15-preview" —
  https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/concepts/conversations-entity-categories
- Two doc quirks: the how-to page's banner says "Conversation PII API (2026-11-15-preview)" (contradicts
  the concepts page), and its curl examples use `api-version=2024-05-01`. The spec's own example shows
  `Operation-Location` as `.../analyze-conversation/jobs/...` (singular). **Follow the header verbatim;
  never rebuild the poll URL.**
  https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/how-to/redact-conversation-pii

**Text PII API (synchronous).** `POST {endpoint}/language/:analyze-text?api-version=2026-05-01`, body
`kind: "PiiEntityRecognition"`, returns 200 with `kind: "PiiEntityRecognitionResults"`. The same spec also
has async `POST /language/analyze-text/jobs` (up to 25 documents). Stable dir: `2022-05-01, 2023-04-01,
2024-11-01, 2025-11-01, 2026-05-01`; preview `2026-05-15-preview`. **Latest GA: `2026-05-01`.**
Sources: `.../LanguageAnalyzeText/stable/2026-05-01/analyzetext.json`;
https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/how-to/redact-text-pii
("Stable 2026-05-01: Generally Available").

**Which fits.**

- The sync Text API is the natural fit for independent strings. It returns `redactedText` per document
  (`required` in the GA `PiiEntitiesDocumentResult`), and it is stateless.
- But Microsoft's own guidance says single-turn submission hurts detection: "For conversational data,
  consider sending more than a single turn ... if you send a single row at a time, the passport number
  doesn't have any context associated with it and the ... category isn't recognized" —
  https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/language-service/transparency-note-personally-identifiable-information
- The Conversation API takes the whole call as one conversation (one job, one poll), which matches
  `Redactor.redact(turns)`. It costs latency and a poll loop.

**Limits** (https://learn.microsoft.com/en-us/azure/ai-services/language-service/concepts/data-limits, `ms.date 2026-04-03`):

| | Conversation PII | Text PII (sync) |
|---|---|---|
| Per unit | 1,000 chars per conversation item; **one conversation per request** | 5,120 chars per document (`StringInfo.LengthInTextElements`) |
| Per request | Items per conversation: **UNVERIFIED** | **5 documents** (30 turns = 6 requests) |
| Request size | 1 MB (all preconfigured features) | 1 MB |
| Oversize behaviour | not stated | Sync: that document gets an invalid-document error, the rest continue. Async: whole request 400 |
| Rate (S tier) | 1000 rps / 1000 rpm per feature | same |

### 1b. Request and response shapes

**Conversation PII request** (spec `AnalyzeConversationJobsInput`, `TextConversation`,
`TextConversationItem`, `ConversationPiiTaskParameters`, 2024-11-01):

- Top level: `displayName`, `analysisInput.conversations[]`, `tasks[]`.
- Conversation: `id`, `language` (BCP-47), `modality` (`text` | `transcript`), optional `domain`,
  `conversationItems[]`.
- Item: required `id`, `participantId`, `text`; optional `role` (`customer` | `agent` | `generic`) and
  per-item `language`.
- Task: `kind: "ConversationalPIITask"`, optional `taskName`, and `parameters`:
  - `modelVersion` (default `latest`)
  - `piiCategories[]`
  - `excludePiiCategories[]`
  - `redactionCharacter` (one of `! # $ % & * + - = ? @ ^ _ ~`, default `*`)
  - `redactionSource` (`lexical` | `itn` | `maskedItn` | `text`; transcripts)
  - `redactAudioTiming`
  - `loggingOptOut` (**default `false`** here; the text task defaults `true`)
- **There is no `redactionPolicy` in the GA schema.** The how-to describes `redactionPolicy` /
  `noMask` / `entityMask` as "version 2024-11-15-preview only", and its snippet is not valid JSON, so
  treat that section as preview-only.

**Job state** (`AnalyzeConversationJobState`):

- Fields: `jobId`, `displayName`, `createdDateTime`, `lastUpdatedDateTime`, `expirationDateTime`,
  `status`, `errors[]`, `nextLink`, `tasks`, `statistics`.
- `tasks` = `{completed, failed, inProgress, total, items[]}`.
- `status` enum: `notStarted, running, succeeded, partiallyCompleted, failed, cancelled, cancelling`.
  Terminal (derived): `succeeded, partiallyCompleted, failed, cancelled`. Non-terminal: `notStarted,
  running, cancelling`.
- Results live at `tasks.items[i]` with `kind: "conversationalPIIResults"`, `taskName`, `status`,
  `lastUpdateDateTime`, and `results = {conversations[], errors[], modelVersion}`.
- Per conversation: `id`, `warnings[]`, `conversationItems[]`. Per item: `id`, **`redactedContent`**
  (`{text, itn, maskedItn, lexical, audioTimings[]}`), `entities[]` (`text, category, subcategory?,
  offset, length, confidenceScore`).
- Results are kept **24 hours** (Learn how-to, "Submitting data").
- Per-conversation failures are `results.errors[] = {id, error}`; job-level failures are `errors[]`.
  The error object is `{code, message, target, details[], innererror}`; the HTTP error body is
  `{error: {...}}` with an `x-ms-error-code` header.
- Error codes: `InvalidRequest, InvalidArgument, Unauthorized, Forbidden, NotFound, TooManyRequests,
  InternalServerError, ServiceUnavailable, Timeout, QuotaExceeded, Conflict, ...`. Inner codes include
  `InvalidDocument, InvalidDocumentBatch, EmptyRequest, MissingInputDocuments, UnsupportedLanguageCode,
  ModelVersionIncorrect, ExtractionFailure`.
- **UNVERIFIED for `modality: "text"` specifically:** no primary example shows which `redactedContent`
  keys are populated. The spec describes `text` as "Redacted output for input in text ... format" and
  the only worked example is a transcript. Read `redactedContent.text`, and treat a missing key as a
  failed redaction.

**Text PII request/response** (`analyzetext.json` 2026-05-01, examples `SuccessfulPiiEntityRecognition*.json`):

- Request: `{kind, parameters: {modelVersion, piiCategories[], excludePiiCategories[], domain, loggingOptOut
  (default true), redactionPolicies[]: {policyKind: characterMask|entityMask|noMask|syntheticReplacement,
  redactionCharacter?, entityTypes[]?, isDefault?}, confidenceScoreThreshold, disableEntityValidation},
  analysisInput: {documents: [{id, language, text}]}}`.
- Response: `{kind: "PiiEntityRecognitionResults", results: {documents: [{id, redactedText, entities[
  {text, category, type, offset, length, confidenceScore, tags[]}], warnings[]}], errors: [{id, error}],
  modelVersion}}`.
- `redactedText` is absent under `noMask`. Warning codes: `LongWordsInDocument, DocumentTruncated`.

### 1c. Entra ID, roles, custom subdomain

- **Supported.** Both specs declare `OAuth2Auth` with scope `https://cognitiveservices.azure.com/.default`
  next to the `Ocp-Apim-Subscription-Key` scheme. The SDK's default credential scope is the same
  (`azure/ai/textanalytics/_generated/_configuration.py:51` @ `6723f2d`).
- **Custom subdomain is mandatory:** "Microsoft Entra authentication always needs to be used together
  with custom subdomain name ... Regional endpoints do not support Microsoft Entra authentication" —
  https://learn.microsoft.com/en-us/azure/ai-services/authentication
- **Live (read-only `az cognitiveservices account list`):** `lang-azure-banking-voice-cc`, kind
  `TextAnalytics`, SKU `S`, `canadacentral`, `customSubDomainName = lang-azure-banking-voice-cc`,
  endpoint `https://lang-azure-banking-voice-cc.cognitiveservices.azure.com/`, provisioning `Succeeded`.
  `disableLocalAuth` is null, so keys still work; the project simply must not use them.
- **Role: "Cognitive Services Language Reader", `7628b7b8-a8b2-4cdc-b46f-e9b35248918e`.** Despite the
  name, its dataActions include `Language/analyze-text/action`, `Language/analyze-text/jobs/action`,
  `Language/analyze-conversations/action`, `Language/analyze-conversations/jobs/action`,
  `Language/analyze-conversations/jobscancel/action` and `Language/*/read` (the GET poll). It is the
  least-privilege choice.
  - Sources: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/ai-machine-learning
    (raw HTML) and live `az role definition list --name "Cognitive Services Language Reader"`.
  - **Verify** with that command, then `az role assignment list --scope <lang account id> --assignee <MI principalId>`.
  - "Cognitive Services User" (`a97b65f3-24c7-4388-baec-2e87135dc908`) is broader; the docs list
    `accounts/listkeys/action` on it, which cuts against the no-keys stance. Assignments can take up to
    ~5 minutes (Learn managed-identity how-to).

### 1d. SDK or raw REST

| Package | Latest stable (PyPI) | Async + AAD | PII method | Verdict |
|---|---|---|---|---|
| `azure-ai-textanalytics` | **5.4.0** (2026-03-05); betas 6.0.0b1/b2 exist | Yes: `azure.ai.textanalytics.aio.TextAnalyticsClient`, token credential accepted | `recognize_pii_entities(documents, *, categories_filter, disable_service_logs, domain_filter, language, model_version, show_stats, string_index_type)`; result has `.redacted_text` | `_version.py`: `DEFAULT_API_VERSION = "2023-04-01"`, `VERSIONS_SUPPORTED = ["v3.0","v3.1","2022-05-01","2023-04-01"]`. Cannot reach GA `2026-05-01`; sync Text only. Its `_policies.py` even ships a `QuotaExceededPolicy` |
| `azure-ai-language-conversations` | **1.1.0** (2023-06-14); betas 2.0.0b1 (2025-08-27), 2.0.0b2 (2025-11-12) | 2.0.0b1: `AnalyzeConversationAsyncLROPoller` | 2.0.0b1: `begin_analyze_conversation_job` | **CHANGELOG 1.1.0: "Removed support for `ConversationalPIITask`".** Conversation PII exists only in the betas. Not usable on a stable pin |

Sources: PyPI JSON for both; CHANGELOGs at
`sdk/textanalytics/azure-ai-textanalytics/CHANGELOG.md` and
`sdk/cognitivelanguage/azure-ai-language-conversations/CHANGELOG.md` @ `6723f2d`.

**Recommendation: raw REST with `httpx.AsyncClient`.**

- The only stable SDK cannot call the API we want; the API we want has no stable SDK.
- `httpx>=0.27` is already a direct, declared dependency and `boot.py` already imports it. `aiohttp`
  is pinned only because `azure-data-tables` / `azure-storage-blob` need it.
- `azure-identity==1.19.0` (pinned) already has `azure.identity.aio.get_bearer_token_provider`
  (tag `azure-identity_1.19.0`, `azure/identity/aio/__init__.py:25`), so the bearer header needs no new
  dependency. The wire shapes in 1b are small enough to hand-roll and pin with fixtures.
- Housekeeping: PyPI latest `httpx` is 0.28.1. The project pins exact versions everywhere except this
  one line. `openai==3.6.0` depends on **`httpx2`**, not `httpx` (PyPI `requires_dist`), so the
  `pyproject.toml` comment "httpx is already present transitively via openai" is stale; the explicit
  declaration is what keeps `httpx` installed.

### 1e. Failure and edge behaviour

- **Empty strings: UNVERIFIED.** No primary source states what an empty `text` does (the spec has
  `InvalidDocument`, `EmptyRequest`, `MissingInputDocuments` codes but no rule). Do not send empties:
  filter them client-side and re-insert `""` at the same index so `_valid_redaction`'s count/order
  check holds.
- **Unsupported language:** the error code `UnsupportedLanguageCode` exists. Learn: "currently the
  service only supports English text" (transparency note). Always send `"en"`.
- **429 / 5xx:** error codes `TooManyRequests`, `InternalServerError`, `ServiceUnavailable`, `Timeout`
  exist. The S-tier rate limit is 1000 rps / 1000 rpm per feature. A Language-specific `Retry-After`
  contract is **UNVERIFIED** (the SDK's `_policies.py:34-51` special-cases 429 but the doc does not).
- **Job latency: UNVERIFIED.** The how-to says only "there may be a delay". No figure or polling
  interval is documented. `pipeline.py` gives each step 60 s, so measure before trusting it.
- **Logging:** `loggingOptOut` defaults differ (Conversation `false` in 2024-11-01, Text `true` in
  2026-05-01). Set `true` explicitly on both; a banking transcript should not sit in service logs by
  default.
- **Residual risk:** "false negatives could lead to personal information leakage. For redaction
  scenarios, consider a process for human review"; "Avoid high-risk automatic redaction ... without
  careful human oversight" (transparency note). This supports keeping ADR-007's fail-closed stance plus
  a second, deterministic scrub.

### 1f. PII categories

- **Conversation, GA `2024-11-01`** (spec enum `ConversationPiiCategories`): `Address, CreditCard, Email,
  Person, NumericIdentifier, Phone, USSocialSecurityNumber, All, Default`.
  - **`NumericIdentifier`** "Covers numeric or alphanumeric identifiers such as case numbers, member
    numbers, ticket numbers, **bank account numbers**, IP addresses, product keys, serial numbers, and
    shipping tracking numbers."
  - Preview-only there: `BankAccountNumber, CASocialInsuranceNumber, CVV, ABARoutingNumber,
    InternationalBankingAccountNumber, SWIFTCode, DateOfBirth, PassportNumber, HealthCardNumber, ...`.
  - Source: the concepts page above (per-category "(preview)" tags).
- **Text, GA `2026-05-01`:** `Person`, `PhoneNumber`, `CreditCardNumber`, `CABankAccountNumber`,
  `CASocialInsuranceNumber`, `USBankAccountNumber`, `InternationalBankingAccountNumber`,
  `ABARoutingNumber`, `Address`, `Email` and ~150 country-specific ids. Tagged preview on the page:
  generic `BankAccountNumber`, `SortCode`, `CVV`, `Password`, `DateOfBirth`, `ExpirationDate`,
  `PassportNumber`, `DriversLicenseNumber`. Source:
  https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/concepts/entity-categories
  and the spec's `PiiCategory` enum, which lists the preview names too. Which model actually honours
  them under the GA api-version is **UNVERIFIED**.
- **Bare account number / arbitrary digit string: not reliably detected, per docs.** "Context is
  important for all entity categories ... without context, a ten-digit number is just a number, not a
  PII entity" (transparency note). No document claims arbitrary digit strings are caught. Conclusion:
  add a deterministic masking pass (digit runs of 4+, with optional spaces or hyphens) on the redactor's
  *output*, and treat the Language call as one layer, not the only one.

---

## Q2 — Azure OpenAI `gpt-5.4-mini` chat completion

### 2a. Model, API surface, endpoint, api-version

- **Exists.** Learn model table: `gpt-5.4-mini` (2026-03-17) — Reasoning, Responses API, Chat Completions
  API, Structured outputs, Functions/tools; context 400,000 (input 272,000 / output 128,000); training
  data to August 2025 —
  https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure
  The reasoning page's feature matrix shows ✅ for both APIs and `max_completion_tokens` —
  https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning
- **Live catalog** (`az cognitiveservices model list -l canadacentral`, model `gpt-5.4-mini` `2026-03-17`):
  `lifecycleStatus: GenerallyAvailable`, `deprecation.inference: 2027-09-21`, `chatCompletion: true`,
  `responses: true`, SKUs offered: **`GlobalStandard`** (default capacity 10) and `GlobalProvisionedManaged`
  only. There is no regional `Standard` SKU for this model in canadacentral.
- **Endpoint (recommended): v1.** `POST https://aoai-azure-banking-voice-cc.openai.azure.com/openai/v1/chat/completions`
  (or `/openai/v1/responses`). `model` is the **deployment name**. "`api-version` is no longer a required
  parameter with the v1 GA API" —
  https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle. The structured-outputs
  page calls `v1` "the latest GA API".
- **Dated GA versions stop at `2024-10-21`** (spec dir `AzureOpenAI/inference/stable`: `2022-12-01,
  2023-05-15, 2024-02-01, 2024-06-01, 2024-10-21`), which predates this model. Use v1.
- **Docs' recommendation:** "For Azure OpenAI models we recommend using the Responses API" (same page).
  Chat Completions remains a supported ✅ for this model, and `response_format` json_schema works on it
  (`max_completion_tokens` there; `max_output_tokens` on Responses). Either is defensible; the
  examples below use Chat Completions to match the request.

### 2b. Parameters

- **Rejected for reasoning models other than GPT-6 Astra:** "`temperature`, `top_p`, `presence_penalty`,
  `frequency_penalty`, `logprobs`, `top_logprobs`, `logit_bias`, `max_tokens`" (reasoning page,
  "Unsupported parameters"). `gpt-5.4-mini` is in that table, so all of these are rejected.
- **Accepted:** `max_completion_tokens` ("Reasoning models will only work with `max_completion_tokens`
  when using the Chat Completions API"); `reasoning_effort`; `verbosity` (`low|medium|high`); `response_format`.
- **`reasoning_effort` values are model-dependent.** Documented set is `none, minimal, low, medium, high,
  xhigh, max`; `minimal` only for original GPT-5, `xhigh` works with GPT-5.4. Footnote 7 says `none` is
  supported for "`gpt-5.4`" and does **not** name the mini. **UNVERIFIED for mini:** whether `none` is
  accepted, and the default effort (the v1 spec says `gpt-5.1` defaults to `none`, older models to
  `medium`; nothing states the 5.4-mini default). Set it explicitly; `low` is a documented value.
- **Structured outputs: supported.** The models page and the reasoning matrix both list it for
  `gpt-5.4-mini`. The structured-outputs how-to's own "Supported models" list stops at `gpt-5.1` and never
  names 5.4, so that list is stale, not a denial.
  - Schema rules: every field `required`, `additionalProperties: false`, root cannot be `anyOf`, ≤100
    properties, ≤5 nesting levels, no `minLength/maxLength/pattern/format`, no `minimum/maximum`, no
    `minItems/maxItems`.
  - Source: https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs
- Use a `developer` (or `system`) message, not both (reasoning page, matrix footnote 3).

### 2c. Managed identity

- **Role:** "Cognitive Services OpenAI User" **`5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`** ("Make inference
  API calls with Microsoft Entra ID": ✅ in the RBAC how-to summary table; "Cognitive Services
  Contributor" ❌).
  - Sources: built-in roles page (raw HTML) and live `az role definition list --name "Cognitive Services
    OpenAI User"`. Live dataActions include `OpenAI/deployments/chat/completions/action` and
    `OpenAI/responses/*`, plus `deployments/completions`, `embeddings`, `realtime`.
  - **Verify:** that command, then `az role assignment list --scope <aoai account id>`.
  - RBAC how-to: https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/role-based-access-control
- **Custom subdomain required** for Entra (Learn managed-identity how-to: 401 if absent). Live:
  `aoai-azure-banking-voice-cc`, kind `OpenAI`, SKU `S0`, `customSubDomainName = aoai-azure-banking-voice-cc`,
  endpoint `https://aoai-azure-banking-voice-cc.openai.azure.com/`, `disableLocalAuth: false` (keys exist;
  none were listed).
- **Token scope: conflicting primary sources, UNVERIFIED which is authoritative.**
  - `https://ai.azure.com/.default`: Learn v1 page, structured-outputs page, and managed-identity
    how-to (its `az account get-access-token --resource https://ai.azure.com` verification snippet).
  - `https://cognitiveservices.azure.com/.default`: the v1 OpenAPI spec (`azure-v1-v1-generated.json`,
    `securitySchemes.OAuth2Auth`), the Language specs, and the docstring in
    `azure/identity/aio/_bearer_token_provider.py`.
  - Verify with one token request plus one one-token call before shipping. Keep the scope in a single
    constant.
- **`openai` package.**
  - Latest stable: **3.16.2** (2026-09-18). **The project pins 3.6.0** (2026-08-28).
  - `AsyncAzureOpenAI` supports `azure_ad_token_provider: AsyncAzureADTokenProvider =
    Callable[[], str | Awaitable[str]]` (`src/openai/lib/azure.py` @ `v3.6.0`, lines 39, 537, 792-805; it
    awaits an awaitable token). But it **requires `api_version`** (lines 658-663 raise without it), i.e.
    a dated version, which cuts against the v1 path.
  - `AsyncOpenAI` accepts `api_key: str | Callable[[], Awaitable[str]]` (`src/openai/_client.py` @
    `v3.6.0`, line 902), so `AsyncOpenAI(base_url="https://.../openai/v1/", api_key=<async provider>)`
    is the v1 shape the Learn page shows (its example is the sync client; the async variant is derived
    from source).
  - `azure.identity.aio.get_bearer_token_provider(credential, *scopes)` returns a coroutine function.
    Present in `azure-identity==1.19.0` (pinned).
  - `httpx` is declared; `openai` 3.6.0 itself depends on `httpx2` (see Q1d).
  - SDK default `max_retries=2` honours `retry-after` (Learn quota page); make that explicit against the
    60 s step deadline.

### 2d. Reading the model back

- **Response `model` field:** the v1 spec says only "The model used for the chat completion." Learn
  examples show `"model": "gpt-5-2025-08-07"` and `"gpt-4o-2024-08-06"`, i.e. base model plus date, not
  the deployment name. That is example output, not a contract for a parseable (name, version) pair, so
  B3 must not lean on it. Log it, don't gate on it.
- **ARM read path (already in `boot.py`, `read_live_model` / `parse_deployment_response`):**
  `GET https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{account}/deployments/{deployment}?api-version=2023-05-01`
  → `properties.model.{name,version}`. Both deployments live on the same account, so the same reader
  works by passing `gpt-5.4-mini` as `deployment_name`.
- **Live confirmation** (`az cognitiveservices account deployment list`): the text deployment is named
  `gpt-5.4-mini`, `model.name = gpt-5.4-mini`, `model.version = 2026-03-17`, SKU `GlobalStandard`,
  capacity 1, `provisioningState Succeeded`, RAI `Microsoft.DefaultV2`. **`versionUpgradeOption:
  OnceNewDefaultVersionAvailable`**, whereas `gpt-realtime-mini` is `NoAutoUpgrade`. The text pin has no
  runtime guard yet (ADR-006 Decision 4), so a silent upgrade would land unnoticed. Changing it is a
  control-plane change for Marco to approve.

### 2e. Error and edge shapes

- **`finish_reason` enum** (v1 spec): `stop, length, tool_calls, content_filter, function_call`.
- **Reasoning tokens eat the cap.** "Both limits cover reasoning tokens, visible output tokens, and
  formatting tokens ... This condition can occur before the model produces any visible output. You pay
  for input and reasoning tokens but receive no answer. Check `status` on every response" (reasoning
  page; that text is written for Responses' `status: "incomplete"`). On Chat Completions the analogue is
  `finish_reason: "length"` with empty or truncated `content` (derived). The page suggests reserving
  ≥25,000 tokens for reasoning plus output while calibrating. Reasoning usage is
  `usage.completion_tokens_details.reasoning_tokens`.
- **Content filter** (https://learn.microsoft.com/en-us/azure/foundry-classic/foundry-models/concepts/content-filter):
  - Filtered prompt → HTTP **400** `{"error":{"message":"The response was filtered","type":null,"param":"prompt","code":"content_filter","status":400}}`.
  - Filtered completion → 200, `finish_reason: "content_filter"`, non-streaming returns no content.
  - Filter unavailable → 200 with `content_filter_results.error.code = "content_filter_error"`.
  - Structured outputs can also return `message.refusal` (handled in the Learn JS example).
- **429** (https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/quota): body is the default error
  `{code, message, param, type, inner_error}`; headers `retry-after-ms`, `x-ratelimit-{limit,remaining,reset}-{requests,tokens}`.
  The TPM estimate = "prompt text and count + the max_tokens parameter" at request time, "not the same as
  the token count used for billing".
- **Other:** 401 = no custom subdomain; 403 = role missing or <5 min old; 404 = `model` is not a
  deployment name (managed-identity how-to).
- **The deployed limit is tiny.** `az cognitiveservices account deployment show` reports for `gpt-5.4-mini`
  `sku.capacity = 1` and `rateLimits = [{key: request, count: 1, renewalPeriod: 60}, {key: token, count:
  1000, renewalPeriod: 60}]`. That is 1,000 tokens per minute and 1 request per minute. The catalog
  default capacity is 10. Derived: a 30-turn redacted transcript (~1,000 tokens) plus any sensible
  `max_completion_tokens` exceeds 1,000 on the first request, so it will 429 on the estimate alone. The
  Learn quota table does not list this model's RPM:TPM ratio (o3 / o4-mini are 1 RPM : 1,000 TPM per
  unit), so the ARM values are the evidence. A capacity increase is Marco's call; GlobalStandard is
  pay-per-token, so capacity is a rate limit, not a reservation.

### 2f. Pricing

Query (Azure Retail Prices API, no auth):
`https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&$filter=contains(meterName,'5.4 mini')`
(372 items, `serviceName` "Foundry Models", `productName` "Azure OpenAI GPT5").

The same filter with `armRegionName eq 'canadacentral'` returns **Count 0**. There is no canadacentral
row for this model.

| Raw meter (`meterName`) | Unit price USD / 1M tokens | Regions carrying it |
|---|---|---|
| `5.4 mini Inp Gl 1M Tokens` | **0.75** | 25 (all same price) |
| `5.4 mini Opt Gl 1M Tokens` | **4.50** | 25 |
| `5.4 mini cd Inp Gl 1M Tokens` | 0.075 | 25 |
| `5.4 mini Batch Inp Gl` / `Batch Opt Gl` | 0.375 / 2.25 | 24 |
| `5.4 mini pp Inp Gl` / `pp Opt Gl` | 1.50 / 9.00 | 25 |
| `5.4 mini Inp Dz` / `Opt Dz` | 0.825–0.90 / 4.95–5.40 | 23 |

- The abbreviation decoding (`Inp` = input, `Opt` = output, `Gl` = Global, `Dz` = Data Zone, `cd` =
  cached, `pp` = priority) is inferred from price ratios; the API does not document it.
- The deployment is `GlobalStandard`, so the Global meters apply; billing against a Global meter for a
  canadacentral account is **UNVERIFIED** (no region row).
- Derived cost: 2,000 in + 1,500 out (reasoning included) ≈ $0.0083 per call, ≈ $0.55 at 67 calls/month.
- Language for comparison (same API, `armRegionName eq 'canadacentral' and productName eq 'Azure Language'`):
  `Standard Text Records` is **$1.00 / 1K** (tier 0), $0.75 (≥500K). A "text record" = 1,000 characters
  (data-limits page). Whether a Conversation item or the whole conversation counts as the record is
  **UNVERIFIED**; worst case 30 records ≈ $0.03/call.

### 2g. What exists on `aoai-azure-banking-voice-cc` (read-only `az`, 2026-09-19)

| Deployment | Model / version | SKU / capacity | Upgrade option | Capabilities |
|---|---|---|---|---|
| `gpt-realtime-mini` | `gpt-realtime-mini` / `2025-10-06` | GlobalStandard / 1 | `NoAutoUpgrade` | realtime |
| `gpt-5.4-mini` | `gpt-5.4-mini` / `2026-03-17` | GlobalStandard / 1 | `OnceNewDefaultVersionAvailable` | chatCompletion, responses, assistants, agentsV2 |

Both accounts (`aoai-…`, `lang-…`) have `customSubDomainName` set. Data residency: "Global types: May be
processed in any Azure region" while "data stored at rest remains in the designated Azure geography"
(https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/deployment-types). Prompts
containing (redacted) call text may therefore be processed outside Canada, which is worth reading against
ADR-001. No regional SKU exists for this model in canadacentral (2a).

---

## UNVERIFIED / could not confirm

1. Which `redactedContent` keys the Conversation API populates for `modality: "text"` (no primary example).
2. Maximum conversation items per Conversation PII request.
3. What an empty or whitespace `text` does on either Language API.
4. Language `Retry-After` semantics; typical Conversation PII job latency or recommended poll interval.
5. Whether `piiCategories: ["All"]` on GA `2024-11-01` includes the preview-tagged categories, and whether
   the Text API's preview-tagged categories work under GA `2026-05-01`.
6. Whether a Conversation "text record" is per item or per 1,000 characters (cost only).
7. Entra token scope for `*.openai.azure.com` v1: `https://ai.azure.com/.default` (Learn) versus
   `https://cognitiveservices.azure.com/.default` (spec, azure-identity docstring). Never exercised.
8. `gpt-5.4-mini`: default `reasoning_effort`, and whether `none` is accepted (footnote names `gpt-5.4`,
   not the mini).
9. Billing meter for a canadacentral GlobalStandard deployment (no canadacentral row in the Retail API).
10. Whether the `model` field of a real `gpt-5.4-mini` response reads `gpt-5.4-mini-2026-03-17` or
    something else (only examples for other models exist). No inference call was made.
11. Whether the v1 `chat/completions` route maps onto the `OpenAI/deployments/chat/completions/action`
    dataAction under the OpenAI User role (Learn says the role suffices; not exercised).

---

## Recommended adapter shape

All JSON below is **derived** from the cited specs and examples, not captured from a live call.

### Language: Conversation PII (primary)

Flow: acquire a token (`azure.identity.aio` provider), `POST` the job, take `Operation-Location`
verbatim, `GET` it with the same bearer until a terminal status or the step deadline, then map items
**by `id`**, never by position, and fail closed on any `errors`.

```http
POST https://lang-azure-banking-voice-cc.cognitiveservices.azure.com/language/analyze-conversations/jobs?api-version=2024-11-01
Authorization: Bearer <token>
Content-Type: application/json
```
```json
{
  "displayName": "postcall-pii <correlation_id>",
  "analysisInput": {
    "conversations": [{
      "id": "<correlation_id>",
      "language": "en",
      "modality": "text",
      "conversationItems": [
        {"id": "0", "participantId": "agent", "role": "agent", "text": "Your balance is ..."},
        {"id": "1", "participantId": "agent", "role": "agent", "text": "..."}
      ]
    }]
  },
  "tasks": [{
    "taskName": "pii",
    "kind": "ConversationalPIITask",
    "parameters": {
      "modelVersion": "latest",
      "piiCategories": ["All"],
      "redactionCharacter": "*",
      "loggingOptOut": true
    }
  }]
}
```
Response: `202`, header `Operation-Location: <poll url>`. Poll `GET <poll url>`:
```json
{
  "jobId": "…", "status": "succeeded",
  "expirationDateTime": "…", "errors": [],
  "tasks": {
    "completed": 1, "failed": 0, "inProgress": 0, "total": 1,
    "items": [{
      "kind": "conversationalPIIResults", "taskName": "pii", "status": "succeeded",
      "results": {
        "modelVersion": "…", "errors": [],
        "conversations": [{
          "id": "<correlation_id>", "warnings": [],
          "conversationItems": [{
            "id": "0",
            "redactedContent": {"text": "Your balance is ********"},
            "entities": [{"category": "NumericIdentifier", "text": "…", "offset": 16, "length": 8, "confidenceScore": 0.9}]
          }]
        }]
      }
    }]
  }
}
```
Rules for the adapter (from 1b/1e): accept only `status == "succeeded"` with `errors == []`,
`results.errors == []`, every submitted id present exactly once, and `redactedContent.text` a string;
otherwise raise (ADR-007). Skip empty turns before submitting and re-insert `""`. Then apply the
deterministic digit-run scrub to every returned string.

### Language: Text PII (fallback, or per-turn cross-check)

```http
POST https://lang-azure-banking-voice-cc.cognitiveservices.azure.com/language/:analyze-text?api-version=2026-05-01
```
```json
{
  "kind": "PiiEntityRecognition",
  "parameters": {"modelVersion": "latest", "loggingOptOut": true,
                 "redactionPolicies": [{"policyKind": "characterMask", "redactionCharacter": "*"}]},
  "analysisInput": {"documents": [{"id": "0", "language": "en", "text": "…"}]}
}
```
Batch ≤5 documents per request; response documents carry `redactedText` (see 1b).

### OpenAI: summary + intent

Client (derived from `openai` v3.6.0 source and the Learn v1 page): `AsyncOpenAI(base_url="https://aoai-azure-banking-voice-cc.openai.azure.com/openai/v1/",
api_key=<azure.identity.aio.get_bearer_token_provider(cred, SCOPE)>, max_retries=…)`; `SCOPE` per
UNVERIFIED #7.

```http
POST https://aoai-azure-banking-voice-cc.openai.azure.com/openai/v1/chat/completions
Authorization: Bearer <token>
```
```json
{
  "model": "gpt-5.4-mini",
  "messages": [
    {"role": "developer", "content": "Summarise this redacted call transcript in two sentences and label the caller's intent."},
    {"role": "user", "content": "<redacted turns, one per line>"}
  ],
  "max_completion_tokens": 800,
  "reasoning_effort": "low",
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "call_summary",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "summary": {"type": "string"},
          "intent": {"type": "string", "enum": ["balance_enquiry", "transfer", "escalation", "general_enquiry", "unknown"]}
        },
        "required": ["summary", "intent"],
        "additionalProperties": false
      }
    }
  }
}
```
(`max_completion_tokens` and the intent enum are illustrative; the deployment's 1,000-TPM cap in 2e must be
lifted first.) Expected shape:
```json
{
  "model": "…",
  "choices": [{"index": 0, "finish_reason": "stop",
               "message": {"role": "assistant", "refusal": null,
                           "content": "{\"summary\":\"…\",\"intent\":\"general_enquiry\"}"}}],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0,
            "completion_tokens_details": {"reasoning_tokens": 0}}
}
```
Accept only `finish_reason == "stop"`, `message.refusal is None`, and `content` that parses to the two
fields, else raise. Do not send `max_tokens`, `temperature`, `top_p`, penalties or `logprobs`. Handle the
400 `content_filter` body and 429 `retry-after-ms`. Log `response.model` but never gate on it; the B3
non-fatal guard should reuse `boot.read_live_model("gpt-5.4-mini")` against `ALLOWED_TEXT_MODELS`.

### Decisions this note surfaces for Marco

1. Raise `gpt-5.4-mini` capacity above 1 (1 RPM / 1,000 TPM as deployed) before any live summary call.
2. Set the text deployment to `NoAutoUpgrade`, matching the realtime pin (B3).
3. Accept or reject Global processing for the summary call against ADR-001, since no regional SKU exists.
4. Confirm Entra scope (`ai.azure.com` vs `cognitiveservices.azure.com`) with a single live call.
5. Confirm the Conversation PII path with a small measured trial (latency, empty-turn handling, `text`
   modality result keys) before wiring it under the 60 s step deadline.

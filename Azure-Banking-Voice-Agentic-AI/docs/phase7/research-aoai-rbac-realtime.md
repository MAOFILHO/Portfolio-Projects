# Phase 7 research — AOAI realtime API + Entra ID / managed-identity auth (D2)

Pure documentation research for Phase 7 decision D2 (retire `AOAI_KEY`, move the voice-agent's Azure
OpenAI realtime-API data-plane auth onto its Container App's system-assigned managed identity). No
Bicep or application code was written for this task. All claims below are sourced from live fetches
of primary docs performed **2026-09-16** (URL + fetch date next to every claim), per `docs/PLAN.md`'s
rule to never answer a factual unknown from memory. Where a primary source did not answer a question
clearly, that is marked **OPEN QUESTION** rather than filled in by inference.

Deployment this research is scoped to: AOAI resource `aoai-azure-banking-voice-cc`, model deployment
`gpt-realtime-mini`, model version `2025-10-06`, SKU `GlobalStandard`, region **Canada Central** (per
`PROJECT_STATE.md` / `docs/PLAN.md` / `docs/phase1/research-aoai-realtime-wire-format.md`). Every
finding below notes explicitly whether it is version/region-pinned or general.

---

## 1. Does the Realtime API (`/realtime` WebSocket) support Microsoft Entra ID auth?

**Yes — confirmed for the WebSocket realtime endpoint specifically, not inferred from the general
REST API.** Microsoft's own WebSockets how-to page for the GPT Realtime API has a dedicated
**"Microsoft Entra ID prerequisites"** section:

> "For the recommended keyless authentication with Microsoft Entra ID, you need to:
> - Install the Azure CLI used for keyless authentication with Microsoft Entra ID.
> - Assign the `Cognitive Services OpenAI User` role to your user account. You can assign roles in
>   the Azure portal under **Access control (IAM)** > **Add role assignment**."
> — [Use the GPT Realtime API via WebSockets](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio-websockets), fetched 2026-09-16

This is not a generic REST-API auth statement carried over by assumption — it is written into the
WebSocket-specific how-to guide, alongside a worked code sample (section 3 below) that builds the
realtime WebSocket client with a bearer token, not an `api-key` header.

**This general "yes" is not the same as "yes" for every kind of Entra ID token.** Section 4 below
draws a sharp, sourced distinction between this (a standard, longer-lived Entra ID access token —
what a `ManagedIdentityCredential` on a Container App produces) and *ephemeral* tokens (short-lived,
purpose-built for exposing to a browser client), which a Microsoft moderator states are **not**
supported on this same `/openai/realtime` endpoint. D2's scenario (server-side Container App, system-
assigned identity) needs the former, which is documented as supported — the ephemeral-token gap does
not block D2.

Not stated as version- or region-pinned in this doc — the guide is written against the GA
`/openai/v1` endpoint form generally, the same endpoint shape Phase 1's research
(`docs/phase1/research-aoai-realtime-wire-format.md`, section 5) confirmed `aoai-azure-banking-
voice-cc` uses.

---

## 2. Exact RBAC role required

**`Cognitive Services OpenAI User`** — built-in role ID `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`.

Confirmed as the role named by the WebSocket realtime how-to's own Entra ID prerequisites (quoted in
section 1), and cross-checked against Microsoft's dedicated RBAC reference page, which lists the same
role ID for "Chat completions" data-plane inference use:

> "| Use case | Role name | Role ID |\n| Assistants | `Cognitive Services OpenAI Contributor` |
> `a001fd3d-188f-4b5d-821b-7da978bf7442` |\n| Chat completions | `Cognitive Services OpenAI User` |
> `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` |"
> — [Use keyless connections with Azure OpenAI](https://learn.microsoft.com/en-us/azure/developer/ai/keyless-connections), fetched 2026-09-16 (`ms.date: 2026-03-19`)

Microsoft's Azure-OpenAI-specific RBAC page (foundry-classic) confirms what this role does and does
not grant, distinguishing it precisely from the similarly-named roles the task asked about:

> **Cognitive Services OpenAI User** — "✅ ... Make inference API calls with Microsoft Entra ID." /
> unable to: "❌ Create new Azure OpenAI resources ❌ View/Copy/Regenerate keys ... ❌ Create new
> model deployments or edit existing model deployments ..."
>
> **Cognitive Services OpenAI Contributor** — "has all the permissions of Cognitive Services OpenAI
> User and is also able to ... Create new model deployments or edit existing model deployments
> [Added Fall 2023]" — a **superset**, control-plane-plus-data-plane role, not a narrower alternative.
>
> **Cognitive Services Contributor** — "This role is typically granted access at the resource group
> level ... Create new Azure OpenAI resources within the assigned resource group. ... View/Copy/
> Regenerate keys ..." Explicitly **excluded** from inference: "A user with only this role assigned
> would be unable to: ... ❌ Make inference API calls with Microsoft Entra ID."
>
> Summary table row: "Make inference API calls with Microsoft Entra ID | ✅ (OpenAI User) | ✅ (OpenAI
> Contributor) | ❌ (Cognitive Services Contributor)"
— [Role-based access control for Azure OpenAI (classic)](https://learn.microsoft.com/en-us/azure/foundry-classic/openai/how-to/role-based-access-control), fetched 2026-09-16 (`ms.date: 2026-09-10`, updated 2026-09-11 — this is a current page, not stale)

**So, precisely for the three roles the task asked to distinguish:**
- **`Cognitive Services OpenAI User`** — the correct, minimal role for D2. Data-plane inference only
  (including realtime, per section 1); cannot touch keys, deployments, or resource creation.
- **`Cognitive Services OpenAI Contributor`** — a strict superset (adds deployment/fine-tuning
  management). Works for inference too, but grants control-plane capability D2 doesn't need —
  broader than the least-privilege goal implied by "managed identity end-to-end."
- **`Cognitive Services Contributor`** — a **resource-group-level, provisioning-oriented** role
  (create/delete Cognitive Services resources, read/regenerate keys). Explicitly documented as
  **unable** to make Entra-ID-authenticated inference calls at all — wrong role family for D2 despite
  the similar name.

No primary source fetched gives the role's `Actions`/`DataActions` as a raw JSON policy document (the
RBAC page directs users to read them live via Azure Portal → **Access control (IAM)** → **Roles** →
**View**, rather than publishing the list in the doc itself) — **OPEN QUESTION**: the exact
`DataActions` string(s) this role carries (e.g. whether it is scoped as
`Microsoft.CognitiveServices/accounts/OpenAI/realtime/action` or a broader
`Microsoft.CognitiveServices/accounts/OpenAI/*` wildcard) was not independently confirmed against the
Azure REST role-definition API in this task — only against prose descriptions and one secondary
aggregator (`azadvertizer.net`, not fetched as primary evidence here). If exact `DataActions` strings
are needed for a security review, pull them live: `az role definition list --name "Cognitive Services
OpenAI User" --query "[].permissions"`.

Not version/region-pinned — RBAC role assignment is a control-plane concept independent of the
deployed model version or region.

---

## 3. How the bearer token is obtained and presented on the realtime WebSocket

**Obtaining the token** — Microsoft's own WebSocket-realtime how-to shows `DefaultAzureCredential` +
`get_bearer_token_provider`:

```python
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
token = token_provider()
```
— [Use the GPT Realtime API via WebSockets](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio-websockets), fetched 2026-09-16 (`ms.date: 2026-07-13`)

**Presenting it on the WebSocket handshake** — not a header the app sets by hand; it's passed as the
SDK client's `api_key`, and the SDK puts it on the wire:

```python
client = AsyncOpenAI(
    websocket_base_url=base_url,
    api_key=token,   # the Entra ID bearer token, not an AOAI key
)
```
— same source. This matches this project's own current connection code shape almost exactly (see
"For D2's implementation" below) — only the *source* of the `api_key` value changes, not the SDK call
shape.

**Token scope — an unreconciled discrepancy across Microsoft's own docs, flagged rather than
guessed:**

- The WebSocket-realtime how-to (quoted above) uses scope **`https://ai.azure.com/.default`**.
- Microsoft's general "keyless connections with Azure OpenAI" reference page, and the **official
  `openai-python` repo's own Azure realtime example**, both use
  **`https://cognitiveservices.azure.com/.default`**:
  > (Python) `token_provider = get_bearer_token_provider(DefaultAzureCredential(),
  > "https://cognitiveservices.azure.com/.default")`
  — [Use keyless connections with Azure OpenAI](https://learn.microsoft.com/en-us/azure/developer/ai/keyless-connections), fetched 2026-09-16; and
  [`openai/openai-python` — `examples/realtime/azure_realtime.py`](https://github.com/openai/openai-python/blob/main/examples/realtime/azure_realtime.py), fetched 2026-09-16 — the SDK-maintainer-endorsed realtime-specific sample, using the `cognitiveservices.azure.com` scope, not `ai.azure.com`.

**OPEN QUESTION**: no primary source fetched states outright that these two scopes are interchangeable
for an AOAI resource, or explains the split (rebrand-in-progress artifact between "Microsoft Foundry"
naming and the underlying Cognitive Services resource provider is the likely explanation, but that is
this document's inference, not a sourced claim). Before Phase 7 implementation ships, request a token
with `https://cognitiveservices.azure.com/.default` (the scope independently corroborated by two
sources, one of them the SDK's own maintainer-published example) against the live
`aoai-azure-banking-voice-cc` deployment and confirm the realtime WebSocket handshake accepts it; if
time allows, also test `https://ai.azure.com/.default` and record which one (or both) the live
resource actually honors, rather than trusting either doc's scope string blind.

**Does Microsoft's own sample show this working with a system-assigned managed identity, not just
interactive login?** Partially. The `DefaultAzureCredential`/`get_bearer_token_provider` pattern shown
in the realtime-specific how-to and in `openai-python`'s `azure_realtime.py` sample is written for
*local, interactive* development (its accompanying "Microsoft Entra ID prerequisites" section says to
install the Azure CLI and sign in). No realtime-specific Microsoft doc fetched shows a
managed-identity-flavored version of that exact snippet. However, the general (non-realtime-specific)
"Use keyless connections with Azure OpenAI" and "Authenticate Azure-hosted Python apps ... using a
system-assigned managed identity" pages do show the managed-identity path explicitly, and it composes
with the same `DefaultAzureCredential`/`get_bearer_token_provider` call used by the realtime sample —
`DefaultAzureCredential`, run inside an Azure-hosted app such as a Container App, automatically falls
through its credential chain to `ManagedIdentityCredential`, which **defaults to the resource's
system-assigned identity when no client ID is configured** (a user-assigned identity requires setting
`AZURE_CLIENT_ID` or `managed_identity_client_id` explicitly — this project's Container App uses only
a system-assigned identity per `PROJECT_STATE.md`, so the no-argument default path applies):

> "**Azure-hosted apps**: When your app is running in Azure, use `ManagedIdentityCredential` to safely
> discover the managed identity configured for your app." / example: `credential =
> ManagedIdentityCredential()` authenticating a client with "system-assigned managed identity"
> — [Authenticate Azure-hosted Python apps to Azure resources using a system-assigned managed identity](https://learn.microsoft.com/en-us/azure/developer/python/sdk/authentication/system-assigned-managed-identity), fetched 2026-09-16 (`ms.date: 2026-01-26`)

> "Take one of the following approaches to set the user-assigned managed identity's client ID: ...
> Set environment variable `AZURE_CLIENT_ID`. **The parameterless constructor of
> `DefaultAzureCredential` uses the value of this environment variable, if present**" (implying: if
> absent, it does not scope to a user-assigned identity, and falls through to system-assigned)
> — [Use keyless connections with Azure OpenAI](https://learn.microsoft.com/en-us/azure/developer/ai/keyless-connections), fetched 2026-09-16

**OPEN QUESTION**: no single fetched page shows the *exact* combined snippet — realtime WebSocket
client construction *and* an explicit `ManagedIdentityCredential()`/no-`AZURE_CLIENT_ID` system-
assigned path — in one place. The composition above is this project's own combination of two
independently-sourced, non-contradictory Microsoft pages (one realtime-specific for the client-
construction shape, one managed-identity-specific for the credential shape), not a single quickstart
Microsoft published pre-combined. Recommend validating the combined path with a real token request
from inside the deployed Container App before relying on it in production, consistent with this
project's "verify live state" discipline.

Not version/region-pinned — this is Entra ID / Azure Identity SDK behavior, generic across regions and
model versions.

---

## 4. Known limitations / gotchas

**(a) Ephemeral tokens are NOT supported on `/openai/realtime` specifically — distinct from the
standard bearer-token auth this project needs.** A Microsoft moderator, after an initial incorrect
answer was corrected in the same thread, stated:

> "Ephemeral token authentication is currently **not supported for the `/openai/realtime` WebSocket
> endpoint specifically**, as confirmed in [Azure-Samples/aoai-realtime-audio-sdk#123]." Recommendation:
> "use WebRTC instead" for scenarios that need ephemeral, browser-exposable tokens.
> — [Does Azure support OpenAI realtime API with websockets and ephemeral tokens? — Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2279844/does-azure-support-openai-realtime-api-with-websoc), answered by Microsoft external staff/moderator "santoshkc", fetched 2026-09-16

This is a Microsoft Q&A moderator answer, not a Microsoft Learn doc page — weaker sourcing tier than
the how-to guides above, and the GitHub issue it cites (`#123`, fetched 2026-09-16) does not itself
contain a maintainer statement confirming the gap; it's an open, unanswered feature question as
fetched. **Flagged as an OPEN QUESTION on the ephemeral-token claim's own strength**, but it does not
matter for D2: D2's architecture is a server-side Container App holding its own credential and calling
the realtime endpoint directly — it never needs to mint an ephemeral, browser-exposable token in the
first place. This limitation would only matter if a future phase added a browser-side voice client
talking to Azure OpenAI directly (out of scope today).

**(b) C# / .NET: Entra ID auth not supported for the realtime WebSocket scenario as of this fetch:**

> "Currently Microsoft Entra ID authentication isn't supported for .NET scenario. You need to use API
> Key authentication."
> — [Use the GPT Realtime API via WebSockets](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/realtime-audio-websockets), fetched 2026-09-16

Not relevant to this project (the voice agent is Python, confirmed by
`voice-agent/azbank_voice_agent/realtime/client.py` using `openai.AsyncOpenAI`), but recorded since it
is a real, sourced, language-specific carve-out on the same page that documents Python/JS support —
evidence the feature is uneven across SDKs, not a uniform "Entra ID works everywhere on realtime."

**(c) No region- or API-version-specific incompatibility was found for `gpt-realtime-mini`
`2025-10-06` / Canada Central / `GlobalStandard` specifically.** Every source fetched describes Entra
ID realtime auth as a general GA-endpoint capability, not gated by model version, SKU, or region. This
is an absence of a documented gotcha, not a fetched confirmation that none exists — **OPEN QUESTION**
in the weak sense: no source was fetched that enumerates region/version restrictions for this feature
at all, so there was nothing to positively confirm either way beyond "no source raised one."

---

## For D2's implementation

**RBAC**: grant the voice-agent Container App's system-assigned identity the
**`Cognitive Services OpenAI User`** role (ID `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`) on the
`aoai-azure-banking-voice-cc` resource — not `Cognitive Services OpenAI Contributor` (broader than
needed) and not `Cognitive Services Contributor` (documented as *unable* to make Entra-ID-
authenticated inference calls at all, per section 2). `PROJECT_STATE.md` already records the identity
holding `Reader` on the AOAI resource; `Reader` does not grant `DataActions` and must stay or be
replaced by this role addition, not relied on for inference. In Bicep, this is a
`Microsoft.Authorization/roleAssignments` resource scoped to the AOAI account, `principalId` =
the Container App's system-assigned identity principal ID, `principalType: 'ServicePrincipal'`,
`roleDefinitionId` referencing `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` (matching the pattern
`infra/modules/aoai.bicep`'s header already anticipates for the D2 gate).

**App code change** — `voice-agent/azbank_voice_agent/realtime/client.py`, `connect_realtime()`,
currently:

```python
api_key = os.environ["AOAI_KEY"]
endpoint = os.environ["AOAI_ENDPOINT"]
deployment = os.environ["AOAI_DEPLOYMENT"]
base_url = endpoint.replace("https://", "wss://").rstrip("/") + "/openai/v1"
client = AsyncOpenAI(api_key=api_key, websocket_base_url=base_url)
return client.realtime.connect(model=deployment)
```

becomes (pattern, pending the live scope check flagged in section 3 — try
`https://cognitiveservices.azure.com/.default` first, the scope corroborated by two independent
sources including the SDK's own maintainer sample):

```python
from azure.identity import ManagedIdentityCredential, get_bearer_token_provider

endpoint = os.environ["AOAI_ENDPOINT"]
deployment = os.environ["AOAI_DEPLOYMENT"]
token_provider = get_bearer_token_provider(
    ManagedIdentityCredential(),  # system-assigned: no client_id argument
    "https://cognitiveservices.azure.com/.default",
)
token = token_provider()
base_url = endpoint.replace("https://", "wss://").rstrip("/") + "/openai/v1"
client = AsyncOpenAI(api_key=token, websocket_base_url=base_url)
return client.realtime.connect(model=deployment)
```

Notes for whoever implements this:
- `ManagedIdentityCredential()` (not `DefaultAzureCredential()`) is deliberate for the deployed-in-
  Azure path — `DefaultAzureCredential`'s broader fallback chain is meant for local dev, and this
  project's `boot.py` already uses `DefaultAzureCredential` elsewhere (line 173) for a
  `management.azure.com` token; using the narrower, explicit `ManagedIdentityCredential` here avoids
  silently picking up a developer's local Azure CLI login in a container that should only ever
  authenticate as its own system-assigned identity.
- A bearer token is time-limited; unlike the current static `AOAI_KEY` read, `token_provider()` should
  be called freshly per connection (or the token cached with its own expiry respected) rather than
  fetched once at import/boot time — no primary source fetched in this task states the token's TTL,
  so treat this as a correctness requirement to verify, not assume, when the code is written.
- `scripts/check_aoai_key_migration_consistency.py` already gates `disableLocalAuth: true` in
  `infra/modules/aoai.bicep` on `AOAI_KEY` being fully gone from `voice-agent/azbank_voice_agent/**/*.py`
  — this change (removing the `os.environ["AOAI_KEY"]` line) is exactly what that check is waiting on
  before the Bicep property can safely flip.
- Per this research's open questions: before flipping `disableLocalAuth: true` for real, confirm live
  against `aoai-azure-banking-voice-cc` that (1) the `cognitiveservices.azure.com` scope token is
  accepted on the realtime WebSocket handshake, and (2) `ManagedIdentityCredential()` with no
  `client_id` resolves to the Container App's system-assigned identity as expected, not an error —
  both are OPEN QUESTIONs in this document, not yet empirically verified against the live deployment.

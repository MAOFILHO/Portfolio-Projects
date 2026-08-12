[← Back to README](../README.md)

# Troubleshooting — Known Issues & Workarounds

Everything below was found by actually running this project against live
Azure, not by inspection — mock mode's fixtures are always "nice" data
(completed runs, real numbers everywhere), so none of these surfaced until
real Azure responses hit real edge cases.

### 1. Terraform: Hub-based Foundry project resource is the wrong architecture
**Symptom:** `azurerm_ai_foundry_project.ai_services_hub_id` — "Expected a
Workspace ID that matched .../Microsoft.MachineLearningServices/workspaces/…"
**Root cause:** That resource expects a Machine Learning Workspace-based
"Hub" — the older Foundry architecture. This project's Foundry project sits
directly under an `azurerm_cognitive_account` (AIServices kind), a flatter,
modern layout the Hub resource doesn't support.
**Fix:** Switched to `azurerm_cognitive_account_project`, which also requires
its own `identity { type = "SystemAssigned" }` block (discovered via
`terraform providers schema -json`, since docs across API versions were
inconsistent).

### 2. Fine-tuning silently trains on the unsupported "Standard" tier
**Symptom:** `create_sft_job` fails with a generic `"The fineTuningJob field
is required"` error that has nothing to do with the actual problem.
**Root cause:** The GA API version (`2024-10-21`) has no `trainingType` field
at all — it silently defaults to `"Standard"`, which `gpt-4.1` doesn't
support for Supervised fine-tuning. The next API version
(`2025-04-01-preview`) does support it, but **only** with the exact string
`"developerTier"` (camelCase, "Tier" suffix) — any other casing or value
(`"Developer"`, `"GlobalStandard"`, nesting under `model_settings`, all
suggested by secondary docs during research) reproduces the same confusing
error.
**Fix:** Pin `api_version = "2025-04-01-preview"` and pass
`extra_body={"trainingType": "developerTier"}` explicitly. Root-caused by
testing raw REST payloads with `httpx` directly against Azure, bypassing the
`openai` SDK — the only way to isolate SDK behaviour from the actual API
contract. This accidentally created a real (harmless, $0-spend) test job
during that experimentation; cancelled after user confirmation via `az rest`.

### 3. `deploy_finetuned_model`'s live branch was a stub — it never called Azure
**Symptom:** A fine-tuning job reaches `succeeded`, but Workflow 3 keeps
reporting "no completed, deployed fine-tuned model available yet" forever.
**Root cause:** The live code path claimed `"note": "Auto-deployment is
enabled on the job, so Terraform/Foundry creates this deployment on
completion"` — but `create_sft_job` never actually sets auto-deploy. The
function returned a fabricated success payload without making any Azure
call.
**Fix:** Rewrote it to make a real ARM `PUT` against the Cognitive Services
deployments API (`azure_foundry.deploy_model`), gated on the job actually
having a `fine_tuned_model` (i.e. genuinely `succeeded`).

### 4. The whole backend freezes during any long-running workflow
**Symptom:** Clicking "Run Workflow 1" appears to hang — no response, no
error, page looks frozen for 30-60 minutes.
**Root cause:** The Azure OpenAI SDK calls inside the async MCP tool handlers
were **synchronous**, executed directly on the single asyncio event loop.
Workflow 1's evaluation makes ~700+ sequential calls; each one blocked the
*entire* backend process — not just that request, every request, including
unrelated health checks — for as long as it ran.
**Fix:** Wrapped every blocking Azure SDK call in `asyncio.to_thread(...)` at
the MCP server boundary, in both `foundry_inference/server.py` and
`foundry_finetune/server.py`. Verified by polling a live job's progress
endpoint *while* a chat-completion call was mid-flight — confirmed the
server stayed responsive.

### 5. A page refresh loses a run forever, even though it keeps billing
**Symptom:** A 45-minute live run completes successfully server-side, but if
the browser tab is refreshed (or the request otherwise dropped) before the
response arrives, the result is gone — unrecoverable, even though the run
already spent real tokens.
**Root cause:** `POST /agent/invoke` was a single blocking request/response —
the result only ever existed in that one HTTP round-trip. Nothing persisted
it server-side.
**Fix:** Added an in-process job registry (`src/app/jobs.py`, contextvar-based
so deeply-nested service code can report progress without threading a job
object through every function signature) plus `POST /agent/invoke/start` +
`GET /agent/jobs/{id}`. The frontend stores the job id in `localStorage` on
start and reconnects to it on mount — a refresh (or reopening the tab later)
resumes the same job instead of losing it.

### 6. `upload_training_file` races Azure's async file processing
**Symptom:** `create_sft_job` fails with `{'code': 'invalidPayload',
'message': 'The specified file reference must point to a completed file
import.'}` — reproduces on essentially every run.
**Root cause:** Azure's file upload API returns synchronously as soon as the
bytes are received, but validates the file *asynchronously* in the
background. Referencing the file id immediately (the natural thing to do
with a synchronous-looking API) races that background step.
**Fix:** `upload_training_file` now polls `client.files.retrieve(id).status`
until it reaches `processed` (bounded at 60s) before returning the id.

### 7. Deploying immediately after submitting a job always fails, and crashed the whole run
**Symptom:** `Blocked: 'deployment_type'` — the whole Workflow 2 run fails
right after a real fine-tuning job is successfully submitted.
**Root cause:** `run_finetune` chains `deploy_finetuned_model` immediately
after job submission in the same request. Since training takes ~60 minutes,
that deploy call is *always* too early and returns a graceful `{"error":
...}` dict (see #3's fix) — but the calling code indexed straight into
`deployment['deployment_type']` without checking for that key first, turning
an expected, recoverable state into an unhandled `KeyError` that crashed the
entire run (losing the job-submission results that *had* succeeded).
**Fix:** Check for `deployment.get("error")` and degrade gracefully — keep
every result that did succeed (validation, cost estimate, upload, job
status, logs) and simply note that deployment isn't ready yet.

### 8. Frontend crashes to a blank page on any partial/failed result
**Symptom:** Page goes fully blank (white screen) partway through a run, no
visible error, no console message shown to the user.
**Root cause:** Every workflow page rendered its results unconditionally on
`{result && (...)}`, assuming any truthy `result` has the full expected
shape. A run that fails mid-way (see #7) can leave `result` truthy but
missing fields the JSX indexes into unconditionally (e.g.
`result.validation.is_valid` on an object with no `validation` key) — React
has no error boundary configured, so one bad property access unmounts the
entire tree. Reproduced and root-caused with a real headless browser
(Playwright), not by reading code — the actual stack trace pointed at the
exact line.
**Fix:** Guard on a field that only exists once the run has genuinely reached
that stage (`result && result.validation`, `result && result.catalog`,
`result && result.report`), and surface `blockedError` visibly on every
workflow page instead of only one of them.

### 9. `null` metrics on a freshly-submitted job crash the render
**Symptom:** Same blank-page symptom as #8, on a *successful* run this time.
**Root cause:** `result.status.metrics.trained_tokens.toLocaleString()` — a
job that's a few seconds old legitimately has `trained_tokens: null` (no
training steps have run yet). Calling a method on `null` throws. This was
invisible in mock mode because its fixture is always a *completed* run with
real numbers — the TypeScript interface declared these fields as plain
`number`, which was simply inaccurate for live data, and `tsc` had no way to
catch a lie in a hand-written type.
**Fix:** Declared the metrics fields honestly as `number | null` and used
optional chaining / nullish coalescing at every call site.

### 10. A backend restart makes a real, working deployment invisible
**Symptom:** Workflow 3 fails with "no completed, deployed fine-tuned model
available yet" even though a fine-tuned deployment is live and serving
requests on Azure right now.
**Root cause:** The mapping from "which deployment is the fine-tuned one" was
kept only in an in-process module-level cache (`_last_live_job_id` /
`_last_live_deployment`) — correct within one process's lifetime, but wiped
by every backend restart (and this session needed several, chasing other
fixes).
**Fix:** Added `azure_foundry.list_finetuned_deployments()`, an ARM query
that finds real Cognitive Services deployments whose model name contains
`.ft-` (Azure's fine-tuned-model naming convention). `get_job_status` now
falls back to this when it has no cached job to work from, instead of
reporting nothing is available.

### 11. `tsc --noEmit -p .` was silently checking nothing
**Symptom:** Multiple frontend bugs (#8, #9) shipped despite "clean" `tsc`
output immediately beforehand.
**Root cause:** The project uses TypeScript's composite/project-references
setup (`tsconfig.json` → references `tsconfig.app.json` +
`tsconfig.node.json`). Running `tsc --noEmit -p .` against the root config
without `-b` (build mode) is a silent no-op — it doesn't check anything, and
exits 0 regardless of real errors.
**Fix:** Point directly at the leaf config: `tsc --noEmit -p
tsconfig.app.json`. Re-running this way immediately surfaced a real error
(`is_terminal` missing from a hand-written interface) that the broken command
had been hiding.

### 12. Container Apps Easy Auth 401s the browser's own CORS preflight
**Symptom:** Every API call from the hosted SPA fails with a generic
"Request failed. Is the API running?" — no CORS error surfaced in the
console, just a failed `fetch()`.
**Root cause:** `curl -X OPTIONS ... -H "Origin: ..."` against the
Easy-Auth-protected backend returned **401** — Easy Auth authenticates the
preflight `OPTIONS` request too, and a preflight structurally never carries
credentials (that's the entire point of a preflight), so it always fails
before the browser ever sends the real request. This is a confirmed,
unresolved Container Apps platform limitation, not a config mistake — see
[microsoft/azure-container-apps#359](https://github.com/microsoft/azure-container-apps/issues/359).
**Fix:** Stopped using Easy Auth entirely for this SPA + separate-origin-API
shape. The backend validates Entra bearer tokens itself (`auth_entra.py`)
behind its own `CORSMiddleware`, which answers `OPTIONS` correctly since
Starlette handles preflight before any route dependency (including the auth
check) ever runs.

### 13. A hand-rolled `loginRedirect()`-in-a-`useEffect` raced MSAL's own redirect handling
**Symptom:** Picking an account on the Microsoft sign-in screen just bounced
back to the same sign-in screen, repeatedly.
**Root cause:** `useMsal()`'s `inProgress` value has a real window, on the
very first render after Microsoft redirects back with an auth code, where a
naive "if idle, start a new login" check reads `None` before MSAL's own
redirect-handling effect has updated it — so a second, competing
`loginRedirect()` fires and cancels the one already in flight.
**Fix:** Replaced the hand-rolled state machine with `MsalAuthenticationTemplate`
from `@azure/msal-react` — the library's own purpose-built component for
exactly this race, rather than continuing to patch a bespoke one.

### 14. `azuread_application_identifier_uri` as a separate resource drifted repeatedly
**Symptom:** Sign-in itself worked, but every API call failed with
`AADSTS500011: The resource principal ... was not found in the tenant` —
reproduced **twice**, independently, after unrelated `terraform apply` runs.
**Root cause:** `identifier_uris` can't be set directly on `azuread_application`
when the value needs the app's own `client_id` (a same-resource
self-reference cycle), so it's normally managed via a separate
`azuread_application_identifier_uri` resource. In practice, Microsoft
Graph's PATCH on the parent application appeared to reset `identifierUris`
to empty whenever that parent resource was modified for *any other* reason
afterward — confirmed by checking Graph directly
(`az rest ... applications/{id}?$select=identifierUris`) each time.
**Fix:** Declared a **static** App ID URI directly on the same resource
instead (`api://{tenant_id}/{name}-signin` — the tenant's default policy
requires the URI to contain a verified domain, tenant ID, or app ID, so a
fully arbitrary string wasn't accepted either, confirmed live via
`InvalidUniqueTenantIdentifierAsPerAppPolicy`). No separate resource means
no drift window.

### 15. The `aud` claim isn't what the docs/assumptions suggested — decode a real token
**Symptom:** `invalid token: Invalid issuer`, then (after fixing that)
`invalid token: Audience doesn't match` — both against a token that *looked*
like it should validate.
**Root cause, part 1:** the app's `api` block defaulted to
`requestedAccessTokenVersion = 1`, issuing v1.0-format tokens
(`iss: https://sts.windows.net/{tenant}/`) against a backend that validated
the v2.0 issuer format. **Part 2:** even after forcing v2 tokens, the actual
`aud` claim (decoded straight out of `sessionStorage` in the browser — see
below) was the resource app's **client ID GUID**, not its App ID URI — the
opposite of what's assumed for a resource with a registered identifier URI.
**Fix:** Set `requested_access_token_version = 2` explicitly. Validate
`audience` against `entra_client_id`, not the identifier URI — established
by decoding a real issued token, not by re-reading docs a third time:
```js
// Paste in the browser console — decodes MSAL's cached access token
// without sending it anywhere.
Object.keys(sessionStorage).filter(k => k.toLowerCase().includes('accesstoken')).forEach(k => {
  const v = JSON.parse(sessionStorage.getItem(k));
  console.log(k, JSON.parse(atob(v.secret.split('.')[1])));
});
```

---

[← Back to README](../README.md)

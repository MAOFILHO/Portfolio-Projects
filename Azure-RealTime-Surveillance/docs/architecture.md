# Architecture

## Lineage: what came from where

This project fuses two prior prototypes (both in a sibling `Project1/` directory during development):

- **`Ai-Detect-Video-Alert`** (Blazor Server, .NET 7): the only *working* code was the browser capture pipeline — `getUserMedia` -> `<canvas>` `drawImage` -> `canvas.toDataURL("image/jpeg")` -> base64 upload to Blob Storage, either on-demand (`WebCam.razor`) or on a 3-second loop (`VideoStream.razor`). Its README described an AI-detection Function App and alerting, but neither existed in the repository — only Blob upload was implemented, and the storage account key was hardcoded in `appsettings.json`.
- **`Video-Agents-Foundry-Solution`** (Bicep + `azd` + bash hooks): an enterprise accelerator for Azure Video Indexer on Arc-enabled AKS with GPU node pools (up to an H100 VM) and AI Foundry. The actual resources are far too expensive for a personal-scale demo and were dropped entirely. What was reused: the subscription-scoped `main.bicep` pattern that creates its own resource group and fans out to small single-purpose modules, the `storage.bicep` and `managed-identity.bicep` module shapes (near-verbatim), and the descriptive terminal-output vocabulary from `hooks/ui.sh` (`log_step`, health-check rows, pass/fail summary blocks) — ported to Python/Rich in `src/surveil_deploy/console.py`.

## Why a hybrid compute model

- **FastAPI on Container Apps** owns everything synchronous and stateful-in-memory: frame ingest (fast, just lands a blob), the event history read API, and the WebSocket connection pool for live alert fan-out.
- **Azure Function (Consumption)** owns the actual AI analysis, triggered per-frame. Keeping this separate means the ingest path never blocks on a Vision API call, and the analysis worker scales independently (and to zero) from the API.
- **Decoupled by a Storage Queue, not a direct call**: the Function enqueues an `AlertMessage` on the `alerts` queue; a background task in the FastAPI process polls that queue and broadcasts to connected WebSocket clients. This means the Function has zero knowledge of how many dashboards are watching, and the API doesn't need to expose any callback endpoint for the Function to hit.

## Why a native blob trigger, not Event Grid

Azure Functions supports two ways to react to a new blob: a native `blob_trigger` binding (polling-based under the hood on Consumption, but typically fires within seconds), or an Event Grid subscription pushed to the function's own extension webhook. Event Grid is lower-latency at scale, but wiring it via Bicep creates a circular dependency for a pure-IaC pipeline: the Event Grid subscription needs to point at the function app's runtime extension endpoint, which only exists *after* the function code has been deployed — you can't create the subscription in the same Bicep deployment that creates the (as-yet-empty) Function App. Rather than split infrastructure across two deploy phases just to shave off some latency, this project uses the native blob trigger, which needs zero additional resources and no ordering dependency between "infra deployed" and "code deployed."

## Why the shared `surveil_core` package

Both the FastAPI backend and the Function need identical detection, alert-rule, and storage logic — duplicating it would risk the two drifting out of sync (e.g. a bug fix landing in one place and not the other). `shared/surveil_core/` is the single source of truth, installed into the backend's Docker image directly (`pip install ./shared`), and vendored (copied) into `function/` immediately before publish because Azure Functions' remote (Oryx) build only sees files inside the function app's own deployment package — a relative path reference outside that package doesn't survive the zip/build step. See `shared/README.md` and `src/surveil_deploy/steps/s07_deploy_function.py`.

## Why keyless (managed identity) everywhere

The original Blazor prototype committed a live storage account connection string (with account key) directly in `appsettings.json`. This project replaces that entirely: one user-assigned managed identity is shared by the Container App and the Function App, granted exactly the RBAC roles it needs (Storage Blob/Queue/Table Data Contributor, Cognitive Services User, Log Analytics Reader) and nothing else. The only actual secret in the whole system is the Azure Communication Services connection string, used solely to send alert email/SMS, injected as a Container App / Function secret sourced from a Bicep output — never written to a file or committed.

## Why Static Web Apps built-in auth, not a custom login form

The dashboard needed to be gated behind sign-in without this project taking on the job of storing and verifying credentials itself. Azure Static Web Apps ships pre-configured identity providers (Microsoft/GitHub/etc.) that work with zero app registration — `staticwebapp.config.json` just declares `allowedRoles: ["authenticated"]` on every route and a `responseOverrides` redirect to `/.auth/login/aad` for anonymous requests. The tradeoff: this only protects the *frontend's* routes. The backend Container App is a separate origin with its own public URL, so it isn't covered by SWA's auth at all — it still relies on the pre-existing `X-Api-Key` anti-abuse gate on write endpoints (frame upload, on-demand analysis, audit writes), not real per-user authorization. Extending real auth to the backend would mean it validating a token SWA issues, which it doesn't do today.

One thing this surfaced that's easy to get wrong: gating the nav bar and header on `user` isn't the same as gating the page content. The dashboard's main content must itself check `user` (or a fresh reload must occur) after `/.auth/logout` — otherwise an already-loaded SPA just keeps running with whatever was in memory, and only the header visibly changes.

## Why query Log Analytics directly instead of just linking to the Portal

The Observability page originally just linked out to the Application Insights blade in the Azure Portal. Querying it directly (`azure-monitor-query`'s `LogsQueryClient`, against the Log Analytics workspace `AppRequests`/`AppExceptions` tables — Application Insights is configured with `IngestionMode: 'LogAnalytics'`, so those are the real table names, not the classic `requests`/`exceptions`) means the request-volume chart and recent-exceptions list render inside the app itself, no context switch to the Portal required. The Portal link is kept as a secondary option for anyone who wants the full query surface. This needed a new RBAC role (`Log Analytics Reader`) granted to the shared managed identity, scoped to the workspace.

## Why the audit trail is client-reported, not server-verified

`POST /api/v1/audit` records whatever `actor` the frontend sends, sourced from `/.auth/me`'s `userDetails` — it is not cryptographically re-verified server-side. The backend Container App has no way to validate a Static Web Apps identity token (see above: it's a separate origin, outside SWA's auth boundary), so building real verification would mean either the backend independently validating Microsoft Entra ID tokens, or SWA forwarding a signed principal header the backend can check — neither exists here. Acceptable for this project's stated demo/portfolio scope; a real production system would need one of those.

## Improvements over the originals

| Issue in the source projects | Fix here |
|---|---|
| No AI detection or alerting was ever implemented (Blazor) | Full detection (Azure AI Vision) + alert-rule engine + dual-channel alerting (WebSocket + ACS email/SMS) implemented |
| Storage account key hardcoded in `appsettings.json` | Fully keyless — managed identity + RBAC everywhere except the ACS connection string |
| JPEG frames uploaded with a `.png` blob name, no content-type set | `_blob_name()` always produces `.jpg`; uploads always set `content_type="image/jpeg"` (regression-tested in `tests/test_frame_codec.py`) |
| Two near-duplicate Blazor capture paths (`WebCam.razor` manual, `VideoStream.razor` looped) | One `useCamera` + `useCaptureLoop` hook pair reused by both `LiveCamera` and `VideoFileMode` components |
| AKS + GPU node pools + Azure Arc + Video Indexer (expensive, unrelated to this use case) | Dropped entirely; replaced with Container Apps (scale-to-zero) + Consumption Functions + pay-per-call Vision |

## Phase-2 extension seam

See [extending-phase2.md](extending-phase2.md) for how a Custom Vision or YOLOv4-based detector plugs into `FrameAnalyzer` without touching capture, alerting, or the deployment pipeline.

## Additional capture sources: `ingestors/`

`frontend/` (browser webcam / demo video) isn't the only way frames can reach the pipeline -- anything that can `POST` a JPEG to `/api/v1/frames` is a valid capture source. `ingestors/nest/` is the first example: an event-driven process that subscribes to Google Nest camera motion/person events over Cloud Pub/Sub and forwards a snapshot per event. It requires zero changes to the backend, Function, or alerting -- see `ingestors/nest/README.md`.

It can run two ways: locally (a laptop/Pi/NAS, zero Azure cost, the original design) or as an opt-in, always-on Azure Container App (`NEST_INGESTOR_ENABLED=true`) deployed alongside the backend in the same Container Apps environment. Unlike the backend and Function (both scale-to-zero), the ingestor holds a persistent Pub/Sub streaming-pull connection with no inbound HTTP traffic at all, so its Container App is fixed at `minReplicas: 1, maxReplicas: 1` -- it can never scale to zero (would drop the subscription) and never scale out (would create a competing consumer double-processing events). `POST /api/v1/frames` is gated behind a shared-secret `X-Api-Key` header (`FRAME_UPLOAD_API_KEY`/`BACKEND_API_KEY`, generated deterministically in Bicep) whenever the ingestor is enabled, closing what would otherwise be an open, internet-facing upload endpoint.

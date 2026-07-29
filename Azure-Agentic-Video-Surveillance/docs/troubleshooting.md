# Troubleshooting

### 1. `surveil-deploy deploy` fails at `s03_deploy_infra` with a region/SKU availability error

**Cause:** Azure AI Vision Image Analysis 4.0 or Container Apps may not be available in every region. **Fix:** set `AZURE_LOCATION` to `eastus2` or `eastus` in `.env` (the validated defaults) and re-run.

### 2. `s03_deploy_infra` fails with an RBAC/authorization error

**Cause:** the deploying identity lacks permission to create role assignments scoped to the resources this template creates (Storage, Cognitive Services, Log Analytics, etc. — `main.bicep` grants its managed identity access to each of these via `Microsoft.Authorization/roleAssignments`). **Correction from an earlier version of this entry:** plain **Contributor is NOT sufficient** — Contributor explicitly excludes `Microsoft.Authorization/roleAssignments/write` by design. This was only confirmed once the CI/CD `deploy.yml` workflow ran under a dedicated OIDC service principal (Contributor-only) instead of a human subscription-Owner account, and failed with `AuthorizationFailed` on every role assignment the template creates. **Fix:** the deploying identity needs Contributor **plus User Access Administrator** (or just Owner) at a scope covering the resource group these resources live in — e.g. `az role assignment create --assignee <principal-id> --role "User Access Administrator" --scope /subscriptions/<sub-id>`. Confirm current roles with `az role assignment list --assignee <principal-id> -o table`.

### 3. `s05_build_backend` fails with an ACR build error

**Cause:** Usually a Dockerfile path issue — the build context must be the repo root (so `shared/` and `backend/` are both visible), not the `backend/` directory. **Fix:** already handled by `s05_build_backend.py`, which runs `az acr build` from `config.source_dir` (repo root) with `--file backend/Dockerfile .` If you're invoking `docker build` manually, do the same: `docker build -f backend/Dockerfile .` from the repo root.

### 4. `s07_deploy_function` fails with a missing-dependency error during Oryx build

**Cause:** `function/requirements.txt` must list every dependency of `shared/surveil_core` explicitly (Azure Functions' remote build has no visibility into `shared/pyproject.toml`). **Fix:** if you've added a new dependency to `shared/surveil_core`, add the pinned version to `function/requirements.txt` too — see the comment at the top of that file.

### 5. Backend `/api/v1/health` returns `degraded`

**Cause:** the backend can't reach Blob/Queue/Table storage — usually a managed identity RBAC propagation delay (can take a few minutes after first deploy) or `AZURE_CLIENT_ID`/`STORAGE_BLOB_ENDPOINT` misconfigured. **Fix:** wait 2-3 minutes and re-run `surveil-deploy smoke-test --stage post`; if it persists, check the Container App's env vars with `az containerapp show`.

### 6. No alerts appear on the dashboard even though the Function is analyzing frames

**Cause:** the WebSocket connection may have dropped, or the detected tags don't match `ALERT_WATCH_TAGS`. **Fix:** check the browser console for WebSocket errors (auto-reconnects every 3s); check `GET /api/v1/events` — if `IsAlert` is `false` for your frames, your `ALERT_WATCH_TAGS`/`ALERT_MIN_CONFIDENCE` may be too strict for what's actually in frame.

### 6b. Nothing gets analyzed at all — uploaded frames never produce an event, no matter how long you wait

**Cause:** `s03_deploy_infra` was re-run (e.g. to pick up an infra-only change) without immediately re-running `s07_deploy_function` afterward. `functionapp.bicep`'s `siteConfig.appSettings` is a full replace on every deploy, and it deliberately excludes `WEBSITE_RUN_FROM_PACKAGE`/`WEBSITE_RUN_FROM_PACKAGE_BLOB_MI_RESOURCE_ID` (those are set separately by `s07`) — so a bare `s03` rerun silently deletes the Function's code package reference. The Function App still shows `state: Running` and the deploy reports success; it just has no code to run. **Fix:** `az functionapp config appsettings list --name <func-app> --resource-group <rg> --query "[?name=='WEBSITE_RUN_FROM_PACKAGE']"` — if empty, re-run `s07_deploy_function` (or the full `surveil-deploy deploy`, which always runs `s07` right after `s03`). Any frames uploaded while the Function was broken get picked up automatically once it's fixed — the native blob trigger's catch-up scan processes them retroactively, no re-upload needed.

### 7. Frontend build fails with a TypeScript error

**Cause:** Node.js version too old. **Fix:** `nvm install --lts` or `brew install node` (requires 20+ LTS).

### 8. `--purge` on teardown reports no soft-deleted accounts found

**Fixed** in `src/surveil_deploy/steps/s12_teardown.py` — `--purge` now blocks, polling `az group exists` every 15s (up to 15 minutes), until the resource group actually finishes deleting before checking for soft-deleted Cognitive Services accounts. Previously this check ran immediately after `az group delete --no-wait` returned, before the group (and the accounts inside it) had actually finished deleting, so it always reported nothing to purge — confirmed live, then fixed. If the 15-minute wait is exceeded (an unusually slow subscription/region), teardown logs a warning and exits; just re-run `surveil-deploy teardown --purge` once `az group exists --name <rg>` returns `false`.

### 9. `func azure functionapp publish` prompts for confirmation or hangs

**Cause:** Functions Core Tools sometimes prompts interactively about worker runtime mismatches. **Fix:** ensure `function/host.json`'s extension bundle and `FUNCTIONS_WORKER_RUNTIME=python` (set by Bicep) match; re-run with `func azure functionapp publish <name> --python --build remote --force` if needed.

### 10. `s11_validate_e2e` fails with "No analysis event appeared for `<blob>` within `<N>`s"

**Cause:** the Function App's blob trigger is the classic polling-based kind (not Event Grid) — Azure documents discovery as taking up to 10 minutes in the worst case, and it really is that variable: two consecutive test uploads during initial rollout took 4.5 and 6.5 minutes respectively. `s11_validate_e2e.py`'s wait window is `MAX_WAIT_SECONDS = 600` to cover the documented ceiling with headroom. **This is not a code bug** — the frame is still analyzed correctly, just later than the smoke test waited. **Fix:** just re-run `surveil-deploy deploy` (it resumes at `s11`); the analysis event will already be sitting in Event History from the previous attempt, or a fresh one will land well within 600s. If 600s genuinely isn't enough on your subscription/region, the real fix is switching the Function's blob binding from the classic polling trigger to an Event Grid-based one (near-instant, no polling latency) — a Bicep + Function binding change, not a timeout tweak.

### 11. CI's `python-tests` job fails on a fresh clone with `FileNotFoundError: .../tests/fixtures/person_test_frame.jpg`

**Cause:** `tests/test_ssd_analyzer.py` requires `tests/fixtures/person_test_frame.jpg`, but that file is deliberately gitignored (licensing on the source clip is unconfirmed for redistribution — see `tests/fixtures/README.md`). Anyone who ran `surveil-deploy smoke-test`/`s11_validate_e2e` locally already has it sitting in their working tree (generated once via the `ffmpeg` command below), so this only surfaces the first time CI actually runs on a clean checkout. **Fix:** `ci.yml`'s `python-tests` job now installs `ffmpeg` (`sudo apt-get install -y ffmpeg` — not preinstalled on the current `ubuntu-latest` image) and generates the fixture before running pytest: `ffmpeg -i sample_videos/swat-soldier-with-weapon-13884574-720p.mp4 -vframes 1 tests/fixtures/person_test_frame.jpg`. If you see this locally instead, just run that same command from the repo root (install `ffmpeg` first if you don't already have it, e.g. `brew install ffmpeg`).

The same gap exists in `deploy.yml`: without this fixture, `s11_validate_e2e` just logs "not found — skipping the live E2E detection check" and the deploy still reports success — it silently never tests the alert/email/SMS path at all. `deploy.yml` now generates the fixture the same way, right before the `Deploy` step.

### 12. `deploy.yml`'s `Deploy` step fails with `ValidationError: nest_ingestor_enabled — Input should be a valid boolean ... input_value=''`

**Cause:** `deploy.yml` set `NEST_INGESTOR_ENABLED: ${{ vars.NEST_INGESTOR_ENABLED }}` unconditionally. When that repo variable isn't configured, GitHub Actions still sets the env var — just to an empty string, not "unset" — and Pydantic's boolean parser rejects `""`. This only ever showed up in Actions, never locally, because a local `.env` simply omits the key entirely when Nest isn't in use, which pydantic-settings treats as its `False` default rather than an explicit empty string. **Fix:** `deploy.yml` now uses `${{ vars.NEST_INGESTOR_ENABLED || 'false' }}` so an unconfigured repo variable falls back to the literal string `false` instead of empty.

### 13. `s07_deploy_function` fails with `az ad signed-in-user show` erroring out

**Cause:** `_ensure_own_blob_data_access()` used `az ad signed-in-user show` to find the currently-logged-in identity's object ID so it could self-grant `Storage Blob Data Contributor`. That command only works for an interactive/human user login — it errors outright under a service-principal login, which is exactly what GitHub Actions' OIDC-based `azure/login` action uses. This never surfaced locally because every dry-run so far authenticated as a real human account. **Fix:** `_current_principal_object_id()` now checks `az account show`'s `user.type` first and calls `az ad sp show --id <appId>` for a `servicePrincipal` login, falling back to `az ad signed-in-user show` only for a genuine user login.

### 14. `s03_deploy_infra` fails: `Destination endpoint not found ... Resource should pre-exist` on an Event Grid event subscription

**Cause:** switching the blob trigger to Event Grid (see #10) initially added both the Event Grid System Topic *and* its event subscription to `functionapp.bicep`. The System Topic doesn't reference the Function, so it's fine at infra-deploy time — but the event subscription's `azurefunction` destination type validates that `<functionAppId>/functions/AnalyzeFrame` already exists, and the Function's code hasn't been published yet at that point in the pipeline (`s03_deploy_infra` runs before `s07_deploy_function`). **Fix:** the System Topic stays in `functionapp.bicep`; the event subscription itself is created imperatively in `s07_deploy_function.py`, right after the function code is published and the app is restarted, with a retry loop (`FUNCTION_READY_RETRIES`/`FUNCTION_READY_DELAY_SECONDS`) since the function can take a little while to finish cold-starting and register itself even then.

### 15. `az eventgrid event-subscription create` fails: `Unsupported Azure Function Trigger ... Azure Event Grid supports EventGrid Trigger type only`

**Cause:** the `azurefunction` Event Grid destination type only accepts a genuine Event Grid *trigger* function (`@app.event_grid_trigger`) — it rejects a blob-trigger function outright, even one configured with `source="EventGrid"`. Confirmed by reproducing the exact `az eventgrid event-subscription create` call from `s07_deploy_function.py` directly. **Fix:** for an Event-Grid-sourced *blob* trigger specifically, the real mechanism is a `webhook` destination pointed at the Function's built-in blob-extension endpoint (`https://<funcapp>.azurewebsites.net/runtime/webhooks/blobs?functionName=Host.Functions.AnalyzeFrame&code=<system-key>`), authenticated with the `blobs_extension` system key from `az functionapp keys list`. Both the function app's hostname and that system key are only available once the function is deployed and running, which is exactly why this subscription is created in `s07_deploy_function.py` rather than Bicep.

### 16. ACS email fails: `(BadRequest) Request body validation error. See property 'senderAddress'`

**Cause:** `communication.bicep`'s `senderEmail` output returned `azureManagedDomain.properties.mailFromSenderDomain` directly — that property is just the domain (e.g. `<guid>.azurecomm.net`), not a full email address, so the ACS email API rejected it as an invalid `senderAddress`. **Fix:** prefix it with `DoNotReply@`, Azure-managed domains' fixed (non-customizable) sender username: `output senderEmail string = 'DoNotReply@${azureManagedDomain.properties.mailFromSenderDomain}'`. Confirmed by patching the live Function App setting and re-testing: the same alert that previously failed with this error sent successfully afterward.

### 17. `s05_build_backend` fails with `(ContainerAppOperationInProgress) Cannot modify a container app while ...`

**Cause:** two `deploy.yml` runs executing concurrently, both trying to update the same Container App at once — Azure rejects the second write outright while the first is still in flight. Reproduced for real: two pushes landed close together (no `concurrency` guard existed yet), both triggered their own `workflow_run`-based deploy, and the second one failed with exactly this error while the first completed successfully. **Fix:** `deploy.yml` now has a `concurrency: group: deploy-to-azure-<env>` block with `cancel-in-progress: false`, so a second deploy queues behind the first instead of racing it. (`cancel-in-progress` is deliberately `false` — cancelling a live infra/Function deploy mid-flight risks leaving Azure resources half-applied, which is worse than making the next push wait a few minutes.)

### 18. A purchased ACS toll-free number can't send SMS yet: "SMS verification for toll-free is now mandatory"

**Cause:** since this project's `docs/deployment.md` was written, US/Canada carriers made toll-free SMS verification mandatory — buying a toll-free number in the Portal now provisions it successfully (billing starts immediately, `$2/month`), but it cannot actually send SMS until a **regulatory documents application** (Communication Service resource -> "Regulatory Documents" -> "Add") is submitted and approved. This is a carrier anti-spam compliance review, not something Azure or this pipeline can skip or expedite. **Also note:** `az communication phonenumber` (the CLI extension) can only list/show numbers already owned -- it cannot search availability, purchase, or submit this verification; all of that is Portal-only. **Fix:** none needed code-wise -- `ACS_SMS_FROM`/`ALERT_SMS_TO` are already wired through `deploy.yml` (see below) and will work as soon as verification clears. Budget for the real approval timeline: Microsoft's own docs cite **5-6 weeks typically, up to 8 weeks** during high application volume -- this is not a same-day or same-week turnaround.

### 19. `Timeout value of 00:05:00 was exceeded by function: Functions.AnalyzeFrame` (or the same invocation completes, but consistently near a timeout ceiling)

**Cause — three distinct, stacked bugs found by reproducing this live, not by inspection:**

1. **A blocking SDK call inside an `async def` blocks every *other* concurrent invocation, not just its own.** `analyze_frame` is `async def` so multiple blob-trigger invocations share one event loop per warm worker instance. Calling the Vision SDK, Table Storage, or ACS SDK directly (all synchronous) freezes that shared loop for the call's entire duration. Under a burst (e.g. a video upload firing many blob triggers at once), invocations queue up behind each other's blocking I/O — some get delayed past the 5-minute cap even though each call is individually fast. **Fix:** every blocking call goes through `_run_blocking()`, which offloads to a thread pool via `loop.run_in_executor()`.
2. **`asyncio.to_thread()`'s default executor is far smaller than this workload needs.** Offloading to a thread only helps if a thread is actually available. Python's default executor sizes to `min(32, os.cpu_count() + 4)` — on this Function App's Y1 Consumption plan (1 vCPU), that's **5 threads for the entire worker process**. Each invocation makes several sequential blocking calls (detect, save_event, upload_annotated_frame, enqueue_alert, notify); a handful of concurrent invocations alone exhausts that pool. Confirmed live: Azure AI Vision's own metrics showed 100% success and sub-second latency for every call it actually received, while invocations still timed out at the full bound — proving the bottleneck was queuing for a free thread, not the downstream service. **Fix:** a dedicated `ThreadPoolExecutor(max_workers=64)` for these calls (`_BLOCKING_CALL_EXECUTOR` in `function_app.py`), sized for the expected concurrency rather than relying on the tiny default.
3. **A blocking call with no timeout at all can hang forever, and offloading it to a thread doesn't fix that.** Even with (1) and (2) fixed, nothing bounded *how long* any single blocking call was allowed to take — a slow/rate-limited dependency could still run out the Function's entire 5-minute execution budget on its own. Confirmed live twice, independently: ACS email hit `TooManyRequests` (429) and the send call hung; separately the OpenAI/Vision path hit the same class of issue. **Fix:** `_run_blocking()` wraps every call in `asyncio.wait_for(..., timeout=_IO_CALL_TIMEOUT_SECONDS)` (60s) — a call that doesn't respond in time raises promptly and the blob trigger's own retry policy handles it, instead of the whole invocation blocking silently for 5 minutes.

**A fourth, related but separate issue** also surfaced under the same load: ACS's own SDK retries on 429 with backoff before raising, so even with (3) in place a rate-limited email/SMS send could eat most of its timeout budget silently retrying. **Fix:** `AcsNotifier` constructs its `EmailClient`/`SmsClient` with `retry_total=0` so a 429 fails immediately. Combined with a per-(camera, matched_tags) notification cooldown (`NOTIFICATION_COOLDOWN_SECONDS`, default 60s, bypassed for `critical` severity) that throttles the *volume* of sends in the first place — the cooldown never affects whether the event/alert itself is recorded, only whether ACS is attempted again for a near-duplicate detection.

**Verification:** confirmed on live traffic after each fix, not just unit tests — Application Insights query timeline showed the exact failure signature at each stage (300000ms-duration failures → then IO-timeout-duration failures with Vision showing 100% success/sub-second latency at the same time → then clean 5-12s successful completions once all four fixes were deployed together), with zero recurrences of the original 5-minute timeout afterward.

### 20. Langfuse traces show up mixed with other, unrelated projects

**Cause:** a Langfuse project is identified entirely by which API key pair authenticates a trace — there is no other routing (see `shared/surveil_core/agents/tracing.py`'s `auth = base64.b64encode(f"{public_key}:{secret_key}".encode())`). Reusing the same `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` pair across multiple unrelated codebases means every one of those codebases' traces lands in that same single Langfuse project, indistinguishable by default. **Fix:** either mint a dedicated Langfuse project + key pair for this system (cleanest separation, its own dashboards), or — if reusing one key pair across projects is a deliberate choice — rely on the `service.name` OTel resource attribute this project's `tracing.py` sets (`azure-agentic-video-surveillance` by default, overridable via `OTEL_SERVICE_NAME`) to filter/search for just this system's spans inside the shared project. Note this resource attribute only applies when this process creates its own `TracerProvider` (the Function App, and the local `diagnose_webrtc.py` CLI) — the backend Container App's provider is already created by `configure_azure_monitor()` before Langfuse tracing is configured, and a `Resource` can't be amended after a `TracerProvider` is constructed, so its Langfuse spans keep whatever cloud role name Azure Monitor's OTel distro assigned by default unless `OTEL_SERVICE_NAME` is set as an app setting before that call.

### Rebuilding after a backend or Function code change

`surveil-deploy deploy` skips any step already marked complete in `deployment_state.json` — that's what makes resuming a *failed* deployment fast, but it also means re-running `deploy` after editing `backend/` or `function/` code does nothing by default, since `s05_build_backend`/`s07_deploy_function` are already marked done. Two options:

```bash
surveil-deploy deploy --fresh    # re-runs the full 12-stage pipeline (safe: infra provisioning is idempotent, ~10-20 min)
```

or, for a faster iteration loop, invoke the underlying `az`/`func` commands directly the same way the step does:
```bash
# Backend:
az acr build --registry <registry-name> --image surveil-backend:dev --file backend/Dockerfile .
az containerapp update --name <container-app-name> --resource-group <rg> --image <registry>.azurecr.io/surveil-backend:dev

# Function:
cp -r shared/surveil_core function/surveil_core   # vendor (see shared/README.md)
cd function && func azure functionapp publish <function-app-name> --python --build remote
rm -rf surveil_core                                # clean up the vendored copy
```

# Troubleshooting

### 1. `surveil-deploy deploy` fails at `s03_deploy_infra` with a region/SKU availability error

**Cause:** Azure AI Vision Image Analysis 4.0 or Container Apps may not be available in every region. **Fix:** set `AZURE_LOCATION` to `eastus2` or `eastus` in `.env` (the validated defaults) and re-run.

### 2. `s03_deploy_infra` fails with an RBAC/authorization error

**Cause:** Your account lacks permission to create role assignments scoped to the resources this template creates (Storage, Cognitive Services, Container Registry). **Fix:** Contributor role on the resource group/subscription is sufficient for this template (it does not need Owner, unlike accelerators that assign roles on pre-existing resources) — confirm your role with `az role assignment list --assignee <your-email> -o table`.

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

**Cause:** resource group deletion (`az group delete --no-wait`) hasn't finished yet — soft-deleted Cognitive Services accounts are only discoverable once the parent resource group is actually gone. **Fix:** wait a few minutes (`az group exists --name <rg>` to check), then re-run `surveil-deploy teardown --purge`.

### 9. `func azure functionapp publish` prompts for confirmation or hangs

**Cause:** Functions Core Tools sometimes prompts interactively about worker runtime mismatches. **Fix:** ensure `function/host.json`'s extension bundle and `FUNCTIONS_WORKER_RUNTIME=python` (set by Bicep) match; re-run with `func azure functionapp publish <name> --python --build remote --force` if needed.

### 10. `s11_validate_e2e` fails with "No analysis event appeared for `<blob>` within `<N>`s"

**Cause:** the Function App's blob trigger is the classic polling-based kind (not Event Grid) — Azure documents discovery as taking up to 10 minutes in the worst case, and it really is that variable: two consecutive test uploads during initial rollout took 4.5 and 6.5 minutes respectively. `s11_validate_e2e.py`'s wait window is `MAX_WAIT_SECONDS = 600` to cover the documented ceiling with headroom. **This is not a code bug** — the frame is still analyzed correctly, just later than the smoke test waited. **Fix:** just re-run `surveil-deploy deploy` (it resumes at `s11`); the analysis event will already be sitting in Event History from the previous attempt, or a fresh one will land well within 600s. If 600s genuinely isn't enough on your subscription/region, the real fix is switching the Function's blob binding from the classic polling trigger to an Event Grid-based one (near-instant, no polling latency) — a Bicep + Function binding change, not a timeout tweak.

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

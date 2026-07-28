# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## What this project is

An end-to-end Azure video surveillance pipeline: browser/webcam or Nest camera frames get captured, uploaded to Blob Storage, analyzed by Azure AI Vision via an Event Grid-triggered Function, and fanned out as live alerts (dashboard WebSocket + email/SMS via Azure Communication Services). Infra is deployed via a custom Python CLI (`surveil-deploy`) wrapping plain Azure CLI/Bicep — not azd.

This repo is part of the `Portfolio-Projects` monorepo (this folder is one project within it). GitHub Actions workflows for this project live at the **monorepo root** (`../.github/workflows/azure-realtime-video-surveillance-{ci,deploy}.yml`), scoped to this folder via `paths:`/`working-directory` — they are not inside this folder.

## Layout

- `backend/` — FastAPI app (dashboard API, WebSocket alert fan-out, polls the `alerts` Storage Queue).
- `frontend/` — Vite + TypeScript dashboard, deployed as an Azure Static Web App, gated by SWA's built-in Azure AD auth.
- `function/` — Azure Function (`function_app.py`), Event Grid-triggered blob trigger on `frames/{name}`, calls Azure AI Vision, enqueues `AlertMessage` on the `alerts` queue, sends email/SMS via ACS.
- `shared/surveil_core/` — code shared between backend and function; the Function's remote build only sees its own package, so shared code is vendored into `function/` at publish time by the deploy CLI (not referenced by relative path).
- `ingestors/nest/` — Google Nest camera ingestor (WebRTC-based frame capture from Nest cameras, alternate capture source to the browser webcam).
- `infra/` — Bicep, `main.bicep` + `modules/` (one file per resource: AKS-adjacent resources aren't here — this is Function/Storage/ACS/Vision/Event Grid/managed identity/Static Web App).
- `src/surveil_deploy/` — the deployment CLI itself (`surveil-deploy`), 12 numbered steps (`s00_preflight.py` … `s11_validate_e2e.py` etc.), each independently callable; checkpointed via `deployment_state.json` (gitignored) so a failed `deploy` resumes from the failed step.
- `docs/` — `deployment.md`, `troubleshooting.md` (numbered, keep adding entries for every real bug found), `lessonslearned.md`, `design-decisions.md`. README links out to these rather than inlining them.
- `memory/MEMORY.md` — plain-text project status notes (current deployment state, standing rules), kept for human/AI reference; not the same as Claude Code's own memory system.

## Commands

```bash
make install          # creates .venv, installs CLI + shared package
cp .env.example .env  # set AZURE_SUBSCRIPTION_ID at minimum

.venv/bin/surveil-deploy deploy              # full 12-stage deploy (~10-20 min)
.venv/bin/surveil-deploy deploy --fresh      # ignore prior state, start over
.venv/bin/surveil-deploy status              # which steps have completed
.venv/bin/surveil-deploy smoke-test --stage pre|post
.venv/bin/surveil-deploy teardown [-y] [--purge]   # -y skips confirm; --purge also purges soft-deleted Cognitive Services accounts

make test              # pytest
make lint              # ruff check src tests shared backend/app function
make bicep-validate    # az bicep build --file infra/main.bicep --stdout > /dev/null
make backend-dev       # uvicorn on :8000
make frontend-dev      # vite dev server on :5173, proxies to :8000
```

`surveil-deploy` is not on PATH — always invoke via `.venv/bin/surveil-deploy` (or `source .venv/bin/activate` first, within the same shell call).

## Key architectural facts (see docs/design-decisions.md for full rationale)

- **Keyless everywhere**: all Blob/Queue/Table/Vision access goes through one user-assigned managed identity with scoped RBAC. The only secret in the system is the ACS connection string (email/SMS sending).
- **Event Grid blob trigger, not classic polling**: the Function's blob trigger uses `source="EventGrid"`. The Event Grid System Topic is provisioned in Bicep; the actual event subscription is created *imperatively* in `s07_deploy_function.py` right after function code publish (avoids a circular dependency — the webhook destination requires the function to already exist). Destination type must be `webhook` (pointed at the blob-extension endpoint + `blobs_extension` system key), not `azurefunction` (that only supports genuine Event Grid trigger functions, not blob triggers with an EventGrid source).
- **Deploy identity needs Contributor + User Access Administrator** (or Owner) — plain Contributor excludes `Microsoft.Authorization/roleAssignments/write`, and the Bicep creates role assignments.
- **Container Apps must be deployed from a unique per-build tag, never `:latest`** — pointing `az containerapp update --image` at an unchanged tag string can report success without actually creating a new revision.
- **Bicep `siteConfig.appSettings` is a full replace, not a merge** — `WEBSITE_RUN_FROM_PACKAGE` is deliberately set outside Bicep (by `s07`) after every infra deploy; re-running `s03` (infra) without `s07` (function publish) right after silently wipes the Function's code reference.
- **Decoupled by a queue**: the Function never calls the FastAPI backend directly — it enqueues `AlertMessage` on the `alerts` Storage Queue; a background task in FastAPI polls it and fans out over WebSocket.

## Standing rules

- **Never overwrite or clobber content the user manually added to README.md** (screenshots section, hand-edited prose added via the GitHub web UI) when syncing changes from the standalone testing repo (`/Users/marco/Documents/Training/K21/Temp/Azure/ComputerVision/Azure-RealTime-Surveillance`, if it still exists) into this repo. Only add specific delta content explicitly requested.
- Before pushing: `git fetch origin` + `git log HEAD..origin/main --oneline` (the user often edits README.md directly on GitHub in parallel); rebase if diverged.
- After pushing: verify actual committed content with `git show HEAD:<path>`, not just pre-commit `git status`/diff.
- A screenshot in this repo's docs/README history shows a real Google OAuth client secret and refresh token in plaintext. The owner was informed and explicitly declined to rotate it — do not raise this again or act on it unilaterally.
- As of 2026-07-28 all Azure resources for this project have been torn down (see `memory/MEMORY.md` for full status, including the SMS/toll-free verification being reset).

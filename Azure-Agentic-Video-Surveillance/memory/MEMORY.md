# Project Memory

Notes on project status and standing rules, kept alongside the code for reference. Last updated: 2026-07-28.

## Repo locations

- Standalone testing repo: `/Users/marco/Documents/Training/K21/Temp/Azure/ComputerVision/Azure-RealTime-Surveillance` (local folder name never renamed), remote `https://github.com/MAOFILHO/Azure-RealTime-Video-Surveillance.git`.
- Portfolio repo (this one): `/Users/marco/Documents/Training/K21/Real-world/Azure-RealTime-Video-Surveillance`, part of monorepo `Portfolio-Projects` (remote `git@github.com:MAOFILHO/Portfolio-Projects.git`). Root-level GitHub Actions workflows live at the monorepo root: `.github/workflows/azure-realtime-video-surveillance-{ci,deploy}.yml`, scoped to this folder via `paths:`/`working-directory`.
- CLI in the standalone repo: `.venv/bin/surveil-deploy` (not on PATH — invoke via full path, or `source .venv/bin/activate` within the same shell invocation).

## Current status (as of 2026-07-28)

**Fully torn down.** `az group delete` on `surveil-rg` completed, and `surveil-deploy teardown --purge -y` purged the leftover soft-deleted Cognitive Services account (`vis-trttpmvolg6lu`, eastus). No Azure resources remain; billing has stopped.

**SMS alerting: externally blocked, not abandoned.** A toll-free number (`+18337939667`) was purchased and a carrier verification application was submitted, but the teardown released the number and voided that pending application (accepted tradeoff to stop all spend). Resuming SMS later requires purchasing a new number and resubmitting verification from scratch — Portal-only, not automatable, typically 5-8 weeks turnaround.

**Email alerting: confirmed fully working** via Azure Communication Services (verified via real Gmail inbox delivery) before teardown.

## Standing rules for editing README.md in this repo

- **Never overwrite or clobber manually-added content** — the screenshots section and prose the user hand-edited via the GitHub web UI. Only add specific delta content explicitly requested; otherwise merge around existing content.
- **Always check for divergence before pushing**: `git fetch origin` + `git log HEAD..origin/main --oneline`, rebase if needed — the user frequently edits README.md directly on GitHub in parallel with local work.
- **Verify after every push**: `git show HEAD:<path>` to confirm actual committed content, not just `git status`/diff pre-commit (a real bug once had `git mv` stage a rename using stale pre-edit content after a `sed` edit).
- **Known plaintext secret in README/docs history**: a screenshot in this repo's docs shows a real Google OAuth client secret and refresh token in plaintext. The owner was informed and explicitly declined to rotate it for now — do not raise this again or take unilateral action on it.

## To redeploy from scratch

```bash
cd /Users/marco/Documents/Training/K21/Temp/Azure/ComputerVision/Azure-RealTime-Surveillance
.venv/bin/surveil-deploy deploy
```

See `docs/deployment.md` and `docs/troubleshooting.md` for the full guide and known gotchas.

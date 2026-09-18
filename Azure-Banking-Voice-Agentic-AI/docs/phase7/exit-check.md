# Phase 7 — exit check, against `docs/phase7/exit-criteria.md`

**Status, 2026-09-18: all 9 proposed criteria met — 2 with a stated limit**, both accepted by Marco
the same day, both recorded as Phase 7 debt rather than silently absorbed. Nothing in this table is a
projection: the live-run criteria (4, 5) are read from real `make deploy`/`make teardown` runs against
`rg-azure-banking-voice-agentic-ai` and a real phone call, not from code inspection alone.

**Closure sign-off**: Marco, 2026-09-18, typed verbatim: "APPROVED: Phase 7. Let's close this out."

| | |
|---|---|
| Commits closing this phase | `fd1da9b`, `11ca61d`, `ce77da4`, `e61f217`, `53f868b`, `d7c6b14`, `d89efbb` |
| `make lint` | clean, `src/azbank_deploy` included |
| `make test` | 625 pass (535 voice-agent + 90 mock-core-banking, unchanged) + 14 new (`azbank_deploy`) |
| `/code-review` | ran on `53f868b` (Standards + Spec axes) — 0 hard violations, 1 real bug fixed (`d7c6b14`) |
| Live runs | `make deploy` (no-op resume) → `make teardown` (full) → `make deploy` (from empty) → 1 live smoke call |

---

## Criterion by criterion

| # | criterion | evidence |
|---|---|---|
| 1 | Every live Azure resource has a Bicep module | ✅ `infra/modules/*.bicep`, 7 modules for the 7 resources this project owns. The phone number needs none — verified live 2026-09-16, ARM registers no `phoneNumbers` resource type for `Microsoft.Communication` at all; it's managed exclusively via ACS's data-plane REST API. |
| 2 | Bicep deploys in `Incremental` mode only; `Complete` mode never used | ✅ `az_cli.py`'s `deploy_bicep()` hardcodes `--mode Incremental`. Grepped `src/azbank_deploy/` and `infra/` for `Complete` — the only two hits are comments stating it's forbidden, no code path invokes it. |
| 3 | The phone number is never a create/delete target in any Bicep module or CLI command | ✅ `scripts/check_no_phone_number_release.py` (D5) extended to scan `src/azbank_deploy/**/*.py`, blocking in `make lint`. Live-verified twice: a real `make teardown` today left `acs-azure-banking-voice` and `+17059100383` untouched, confirmed via `az resource list` before and after. |
| 4 | `make deploy` on a clean subscription reaches a working system, evidenced by a smoke call | ✅ **with a stated limit.** A full teardown-then-redeploy today rebuilt all 7 resources from empty; a live call reached the agent, PIN was accepted, and the balance check succeeded. **Limit found and fixed same day**: tearing down and recreating the Container Apps environment gives Azure a new random default-domain suffix, changing the voice agent's FQDN — but ACS (never torn down, by design) still held the *old* webhook URL, so the first redial after redeploy rang unanswered. The CLI has no step that re-validates a dependency's *value* (the domain) against an "already deployed" resource (`acs`) it otherwise skips. Fixed live via `az eventgrid event-subscription update`; the CLI itself was not changed. Carried as Phase 7 debt (below). |
| 5 | `make teardown` reaches zero billable spend, phone number excluded | ✅ **with a stated limit.** All 7 teardown-eligible resources removed live, soft-deleted AOAI account purged, ACS + phone number untouched. **Limit, accepted 2026-09-18 (Option A)**: 3 auto-created Log Analytics workspaces and 2 Application Insights alert artifacts are outside the CLI's 8-node resource graph and survive teardown. Checked live: `PerGB2018` SKU, no active ingestion, 30-day retention inside Azure's free window — **$0 ongoing cost**, confirmed by resource-list + pricing-tier read, not assumed. |
| 6 | No long-lived Azure secret in the repo or GitHub Actions settings | ✅ Both new workflows authenticate via `azure/login@v2` OIDC — only `AZURE_CLIENT_ID`/`AZURE_TENANT_ID`/`AZURE_SUBSCRIPTION_ID` (IDs, not credentials) are read from GitHub secrets. `DOCKERHUB_PASSWORD` is a Docker Hub token, not an Azure secret — out of this criterion's scope, but still needs adding to GitHub before the workflows are runnable (unrelated to this criterion; tracked below). |
| 7 | `deploy` and `teardown` workflows are manual-dispatch only | ✅ Both `.github/workflows/azure-banking-voice-agentic-ai-{deploy,teardown}.yml`: `on: workflow_dispatch` only, no `push`/`schedule` trigger. `teardown` additionally gates on a typed `confirm: TEARDOWN` input. |
| 8 | `ci` workflow needs no Azure credentials | ✅ Unchanged this phase. `azure-banking-voice-agentic-ai-ci.yml` triggers on `push`/`paths`, grepped for `azure/login`/`secrets.AZURE_*` — zero matches. |
| 9 | AOAI data-plane auth migrated off `AOAI_KEY` onto managed identity (D2) | ✅ Closed 2026-09-17 (`fd1da9b`). `realtime/client.py` uses `DefaultAzureCredential` only, no key fallback in code. Live-verified by a real call reaching a spoken balance — `docs/phase7/d2-live-call-result.md`. |

**9 of 9 met. 2 carry a stated limit** — same convention as Phase 5's B5: accepted explicitly by
Marco, not silently absorbed.

---

## Phase 7 debt (both accepted 2026-09-18, tracked for a future session)

1. **The deploy CLI models resource state as boolean ("deployed: yes/no"), not value-current.** A
   resource whose *dependency's value* changed (here: the Container Apps environment's domain
   suffix, after being torn down and recreated) is silently skipped on redeploy if it was never
   itself torn down, because the CLI only ever asks "does this exist," never "does this still match
   what it depends on." `acs` was the one case that hit this today; nothing else in the 8-node graph
   currently has an equivalent live-computed dependency value, but the same class of bug could recur
   if one is added. No code fix applied — recorded as the real gap it is rather than special-cased for
   `acs` alone.
2. **`make teardown` doesn't clean up 3 auto-created Log Analytics workspaces or 2 Application
   Insights alert artifacts.** Confirmed $0 ongoing cost. Extending the CLI's graph to cover these is
   the eventual fix; not done today.
3. The deferred Bicep-file split (`aoai.bicep`, `call-records-store.bicep` into resource-only and
   RBAC-only modules) from the CLI's own design phase — `docs/phase7/deploy-teardown-cli.md`, Option
   B, still not done.

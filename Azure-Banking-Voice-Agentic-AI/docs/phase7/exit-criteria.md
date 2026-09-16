# Phase 7 — IaC completion & CI/CD: design and exit criteria

> **APPROVED. Phase 7 is open.**
>
> This started as a first-pass draft, not the output of a design session with Marco (no
> `/grill-with-docs` round happened). It surfaced 5 open questions; Marco answered all of them, then
> approved the doc and the phase itself, both 2026-09-16 -- corrected here from this file's own
> earlier "NOT APPROVED" banner, which a code-review Standards-axis pass (2026-09-16) flagged as
> stale against real commits already landed under this phase's name.
>
> | approval | state |
> |---|---|
> | The 5 design questions below (Q1-Q5) | **Given 2026-09-16**, question by question |
> | D4's manual OIDC setup (app registration, federated credential, RBAC, 3 GitHub secrets) | **Done 2026-09-16**, Marco, live in Azure AD + GitHub |
> | The design doc as a whole | **Approved 2026-09-16**, Marco |
> | Begin Phase 7 | **Given 2026-09-16**, Marco |
> | `APPROVED: Phase 7` for billable resources | **Given 2026-09-16**, Marco (typed verbatim, twice) |

---

## Entry conditions

| condition | state |
|---|---|
| Phase 6's exit criteria written | Satisfied — `docs/phase6/exit-criteria.md` |
| Phase 6's exit criteria met | Satisfied — all 14 criteria, `docs/phase6/exit-check.md`, 2026-09-15 |
| Marco's sign-off on Phase 6 | **Not recorded as a separate step in this draft — flagged, not assumed** |
| Marco's approval to begin Phase 7 | **Not given** |

---

## What Phase 7 is, in one paragraph

Everything a caller-facing resource needs today exists in Azure, but it was built by hand, one `az`
command and one Bicep module at a time, across six phases. Phase 7 makes that reproducible: every
resource this project owns gets a Bicep module, a Typer command line tool can stand the whole system
up on a clean subscription or tear it down to zero billable spend, and three GitHub Actions workflows
(`ci`, `deploy`, `teardown`) run that tooling with no long-lived Azure secret stored anywhere in the
repo or its GitHub settings — authentication is via GitHub's `OIDC` (a short-lived, per-run login
token GitHub and Azure exchange directly, replacing a stored password).

---

## Current state — what already exists vs. what Phase 7 adds

| resource | Bicep today | gap |
|---|---|---|
| Application Insights | `infra/modules/app-insights.bicep` | none |
| Call-records table storage | `infra/modules/call-records-store.bicep` | none |
| Mock core-banking Container App | `infra/modules/mock-core-banking.bicep` | none |
| Azure OpenAI resource | **`infra/modules/aoai.bicep`**, added 2026-09-16 | Account + deployment match live. `disableLocalAuth` is checked in as `false` (matches the live, safe value) — **`true` (D2's `AOAI_KEY` retirement) is now enforced by a real blocking check** (`scripts/check_aoai_key_migration_consistency.py`, added 2026-09-16 after a code-review finding that D2 had only a comment, unlike D5's real check), not just by header prose. Still not deployed. |
| ACS resource + Event Grid wiring | **`infra/modules/acs.bicep`**, added 2026-09-16 | none. **The phone number itself needs no module and can have none** — verified live (`az provider show --namespace Microsoft.Communication`): ARM registers no `phoneNumbers`/`phoneNumberOrders` resource type for this provider at all. It is managed exclusively via ACS's data-plane REST API, outside Bicep's reach entirely. See the module's own header for the full finding. |
| Container Apps environment | **none** | needs a module |
| Voice-agent Container App | **none** | needs a module |
| `ci` GitHub Actions workflow | **`.github/workflows/azure-banking-voice-agentic-ai-ci.yml`** (monorepo root, correctly `paths`-scoped) | none — corrected 2026-09-16; the earlier "`.github/workflows/` is empty" line above was wrong, checked only this project's own subfolder, not the monorepo root where GitHub Actions actually reads from |
| `deploy`/`teardown` GitHub Actions workflows | **none exist** | this phase's main deliverable |
| Deploy/teardown CLI | **none exists** | this phase's main deliverable |
| AOAI data-plane auth | Still the `AOAI_KEY` secret (`PROJECT_STATE.md`, "Live Azure state") | conflicts with this phase's "managed identity end-to-end" goal — open question 2 below |

---

## Settled decisions — given 2026-09-16

**D1 (Q1) — `Incremental` deploy mode only.** Stated explicitly in the CLI. `Complete` mode (deletes
anything not in the template) is never used against the live resource group.

**D2 (Q2) — AOAI's key-to-managed-identity migration is in scope for this phase.** `AOAI_KEY` is
retired; the voice agent's system-assigned identity (already holding `Reader` on the AOAI resource,
per `PROJECT_STATE.md`) is extended to the data-plane role AOAI's realtime API needs, and the app's
config path is updated to stop reading the key secret. "Managed identity end-to-end, no Key Vault" is
true at this phase's close, not deferred as Phase 6's D10 was.

**D3 (Q3) — `deploy` and `teardown` are `workflow_dispatch` only.** Manual trigger, run by a person
clicking a button in GitHub's UI, never on push. `ci` (lint + test, no Azure credentials needed) is
the only one of the three safe to run automatically on every push.

**D4 (Q4) — the GitHub OIDC federated credential is a manual, one-time setup Marco performs in the
Azure and GitHub portals.** Step-by-step instructions are below, given directly rather than through
`/wizard` — this is a single one-time portal walkthrough, not a repeatable script. `/wizard` remains
the right tool for a *repeated* human-in-the-loop procedure; this isn't one.

**D5 (Q5) — hard "no", enforced by a CI check.** No Bicep module or CLI command may create, delete,
or replace a `Microsoft.Communication/communicationServices/phoneNumbers` resource, under any flag or
mode. A blocking CI grep/static check (same shape as the B3 allowlist check) asserts this across the
whole `infra/` tree and the CLI source, not just the ACS module — so a future module that
re-provisions the parent ACS resource wholesale is caught too.

---

## D4 — GitHub OIDC federated credential setup (manual, one-time)

This creates a trust relationship between this GitHub repo and Azure — GitHub proves its identity
with a short-lived token on every workflow run, Azure accepts it for exactly the scope granted below.
**No password or secret is created or stored.**

1. **Create an app registration** (an identity Azure recognizes, separate from any person's login).
   Azure Portal → **Microsoft Entra ID** → **App registrations** → **New registration**.
   - Name: `azure-banking-voice-agentic-ai-deploy` (or similar — the name doesn't matter functionally).
   - Supported account types: **single tenant**.
   - Redirect URI: leave blank.
   - Click **Register**. On the resulting page, note two values: **Application (client) ID** and
     **Directory (tenant) ID**.

2. **Add a federated credential** trusting GitHub for this repo and branch.
   Same app registration → **Certificates & secrets** → **Federated credentials** tab → **Add
   credential**.
   - Federated credential scenario: **GitHub Actions deploying Azure resources**.
   - Organization: `MAOFILHO`
   - Repository: `Portfolio-Projects`
   - Entity type: **Branch**
   - Branch name: `main`
   - Name: `github-actions-azure-banking-deploy` (or similar).
   - Save. This is the credential — no secret value to copy anywhere.

3. **Grant the app registration access, scoped to this project's resource group only** — not the
   subscription. The app registration is repo-wide (GitHub doesn't scope by folder), so this is what
   actually limits the blast radius to this one project even if another workflow in the monorepo
   later tried to reuse it.
   Azure Portal → resource group `rg-azure-banking-voice-agentic-ai` → **Access control (IAM)** →
   **Add** → **Add role assignment**.
   - Role: **Contributor**.
   - Assign access to: the app registration created in step 1 (search by its name).
   - Save.

4. **Store 3 GitHub repository secrets** — these are IDs, not credentials; nothing long-lived or
   secret-valued.
   GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**,
   one per value:
   - `AZURE_CLIENT_ID` = the Application (client) ID from step 1.
   - `AZURE_TENANT_ID` = the Directory (tenant) ID from step 1.
   - `AZURE_SUBSCRIPTION_ID` = the subscription ID this project's resources live in.

Once all three secrets are set, tell me — I don't need the values themselves, just confirmation it's
done, and I'll wire `${{ secrets.AZURE_CLIENT_ID }}` etc. into the `deploy`/`teardown` workflow YAML
when this phase is built.

**Done, 2026-09-16.** App registration `Azure-Banking-AI` created, federated credential added
(`repo:MAOFILHO/Portfolio-Projects:ref:refs/heads/main`), `Contributor` granted scoped to
`rg-azure-banking-voice-agentic-ai` only, and `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` /
`AZURE_SUBSCRIPTION_ID` are set as GitHub repository secrets.

> **Found during setup, resolved 2026-09-16.** The repo already carried a secret named
> `AZURE_CREDENTIALS` (GitHub → Settings → Secrets and variables → Actions). Confirmed by Marco: it
> belongs to a different project in the monorepo, not this one. No action needed here — this
> phase's exit criterion 6 (no long-lived Azure secret for *this* project) is unaffected.

---

## Proposed exit criteria (draft — not in force)

| # | criterion | how it is proved |
|---|---|---|
| 1 | Every live Azure resource has a Bicep module | `infra/modules/*.bicep`, one per resource in the inventory above |
| 2 | Bicep deploys in `Incremental` mode only; `Complete` mode never used | CLI source + a code-review check |
| 3 | The phone number is never a create/delete target in any Bicep module or CLI command | Grep-based CI check, blocking — same spirit as the B3 static check |
| 4 | `make deploy` on a clean subscription reaches a working system | A real run, evidenced by a smoke call (same shape as Phase 6's D16) |
| 5 | `make teardown` reaches zero billable Azure spend, phone number excluded | A real run, evidenced by a billing/resource-list check afterward |
| 6 | No long-lived Azure secret in the repo or GitHub Actions settings | Repo scan + GitHub settings screenshot/read |
| 7 | `deploy` and `teardown` workflows are manual-dispatch only | Workflow YAML |
| 8 | `ci` workflow needs no Azure credentials | Workflow YAML |
| 9 | AOAI data-plane auth migrated off `AOAI_KEY` onto managed identity (D2) | Config diff + a live call using the new auth path |

---

## What this phase must not do

- Provision or modify anything before `APPROVED: Phase 7` is typed verbatim.
- Write any Bicep or CLI path capable of deleting or replacing the phone number, under any flag or
  mode.
- Wire `deploy` or `teardown` to run on push or on any automatic trigger.
- Store an Azure service-principal secret in GitHub Actions secrets — OIDC only.
- Run a real `make teardown` against the live resource group without a human watching it happen.

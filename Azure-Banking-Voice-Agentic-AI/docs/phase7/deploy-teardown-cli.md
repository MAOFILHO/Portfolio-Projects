# Phase 7 deploy/teardown CLI -- design and build record

2026-09-18. Covers `src/azbank_deploy/` (the Typer CLI) and `.github/workflows/azure-banking-voice-
agentic-ai-{deploy,teardown}.yml` -- Phase 7's two main deliverables (`docs/phase7/exit-
criteria.md`).

## Design process

1. **`/prototype`**, per `CLAUDE.md`'s Skill discipline (Marco invoked it): a logic prototype
   (`infra/PROTOTYPE-deploy-teardown-ordering.html`) tested whether "deploy in dependency order,
   tear down in reverse" actually holds, before any real code was written. Committed to its own
   throwaway branch, `throwaway/phase7-deploy-teardown-prototype`, out of `main`.
2. Marco confirmed 2026-09-18: yes, the CLI's `deploy`/`teardown` commands should auto-compute the
   legal order, not leave sequencing to whoever runs them.
3. Tracing the actual Bicep modules' params (not the prototype's simplified graph) surfaced two real
   circular-looking dependencies:
   - `acs.bicep` needs the voice agent's future public URL; `voice-agent.bicep` needs ACS's
     connection string. **Resolves for free** -- Container Apps FQDNs are deterministic
     (`<app-name>.<environment's default domain>`), so the CLI computes the voice agent's future URL
     from the environment alone, no bootstrap needed. No graph change.
   - `call-records-store.bicep` bundles the storage account with a role assignment that needs the
     voice agent's identity, in one file with one required param -- so the file can't be deployed at
     all until the voice agent exists. But `voice-agent.bicep` does an `existing`-resource lookup on
     that same account, which fails if it isn't there yet. A real deadlock, not resolvable by
     ordering alone.
4. Proposed fix for the second case: split `call-records-store.bicep` (and, for the same reason,
   `aoai.bicep`) into an account/deployment-only module and a role-assignment-only module. **Marco's
   call, 2026-09-18 (Option B): defer the split, ship the CLI now with a documented workaround.**
   Tracked as Phase 7 debt -- the split is still the right eventual fix.
5. **The workaround, and only this one** (aoai needed no equivalent, since nothing else requires it
   to pre-exist): `call_records_account` is its own graph node, created by a plain `az storage
   account create` that bypasses `call-records-store.bicep` for just the account. The voice agent
   depends on that node. `call_records_rbac` is the real `call-records-store.bicep` deploy (account
   properties are then a no-op under `Incremental` mode; the table and role assignment are new),
   depending on both `call_records_account` and `voice_agent`.

## Two other decisions Marco made, and how they're built

**"Auto-increment resource names on collision" -- rejected (Option A instead).** Every Bicep module
here uses a fixed name matching the live resource on purpose: it's what makes `Incremental` mode
against an already-running system a safe no-op, and several modules hardcode those names as literal
strings elsewhere (`voice-agent.bicep`'s env vars). Auto-renaming on collision would silently break
those references and risk paying for duplicate resources. Instead: "already exists, same name we
expect" is treated as success (the existing design already does this), and the rare genuine
global-uniqueness collision fails loudly rather than being silently worked around. No renaming
anywhere in `src/azbank_deploy/`.

**Soft-deleted AOAI account purge -- accepted, and load-bearing.** Verified against the installed
`az` CLI (`az cognitiveservices account list-deleted` / `purge`) rather than assumed: a deleted
Cognitive Services account is only soft-deleted, and a name collision on the next deploy is a real,
well-documented Azure failure mode. `teardown`'s last step, unconditionally, checks for and purges a
soft-deleted account matching this project's AOAI account name (`actions.purge_soft_deleted_aoai`).

## A real bug the tests caught

Reversing the full deploy graph for teardown looked like the safe, conservative default -- and was
wrong. `acs` depends on `container_apps_env` (a deploy-time *value* dependency: acs.bicep needs the
environment's default domain to compute its webhook URL), but `acs` is also permanently excluded
from teardown (D5). Naively reversing the graph meant `container_apps_env` could never legally tear
down: its "dependent" (`acs`) would never go absent to satisfy the check. `tests/
test_azbank_deploy_resources.py`'s `TeardownToZero` suite caught this as a failing/erroring test
before any of it ran against real Azure. Fix: `can_teardown`'s dependents check now ignores
dependents that are themselves never teardown-eligible -- they were never a real deletion-order
constraint, since ACS isn't actually hosted inside the Container Apps environment; the dependency
edge only ever mattered at deploy time.

## What's built, what isn't run yet

- `src/azbank_deploy/`: `resources.py` (pure graph + legality, 14 unit tests), `az_cli.py` (every
  `az` call this tool makes, one function each), `state.py` (checkpoint + live-state reconciliation,
  resume discipline applied to *whether* a resource is deployed), `actions.py` (per-resource deploy/
  teardown, every cross-step value re-fetched live rather than cached -- so a resumed run can't read
  a stale in-memory value from a process that already exited), `cli.py` (the Typer `deploy`/
  `teardown` commands), `config.py` (the fixed names).
- `.github/workflows/azure-banking-voice-agentic-ai-{deploy,teardown}.yml`: `workflow_dispatch` only
  (D3), OIDC via the three secrets D4 already set up. `teardown`'s workflow adds a typed `confirm:
  TEARDOWN` input as its own gate, on top of GitHub's own dispatch gate -- matching this project's
  standing pattern of a typed confirmation for a consequential action. **`DOCKERHUB_PASSWORD` is a
  new required secret neither workflow's setup created -- still needs adding.**
- `scripts/check_no_phone_number_release.py` (D5) now scans `src/azbank_deploy/**/*.py` too.
- `make lint` and `make test` both clean against the whole tree, 625 tests total (535 voice-agent +
  90 mock-core-banking, unchanged, plus this CLI's 14).
- **Not done**: `/code-review`, a real `make deploy` run against the live resource group, a real
  `make teardown` run with Marco watching (exit-criteria's own rule). Everything above is local
  code, tests, and static checks -- none of it has touched live Azure.

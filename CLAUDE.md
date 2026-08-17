# CLAUDE.md — Portfolio-Projects

This is a monorepo of self-contained portfolio projects. Each top-level folder is its own independent project with no shared code between them; several have their own `CLAUDE.md` with project-specific instructions — read that file when working inside such a folder, in addition to this one.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on `MAOFILHO/Portfolio-Projects` (the `origin` remote), managed via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), used as-is. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: root `CONTEXT-MAP.md` indexes one `CONTEXT.md` per top-level project folder; ADRs live per-project under `<project>/docs/adr/`. See `docs/agents/domain.md`.

# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This is a **monorepo of self-contained projects** — each top-level folder (e.g. `AWS-Insurance-FNOL-Voice-Agentic-AI/`, `Azure-Insurance-Claim-Guard-AI/`) is its own context with no shared code between them. Domain docs are scoped per-project, not per-`src/`-subpackage.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — points at one `CONTEXT.md` per top-level project. Read the entry (and its `CONTEXT.md`) for the project you're about to work in; you don't need the others.
- **`<project>/docs/adr/`** — read ADRs that touch the area you're about to work in, scoped to that project.
- **`docs/adr/`** at the repo root, if it exists — decisions that span multiple projects (tooling, CI conventions, shared conventions). Expect this to stay mostly empty since projects don't share code.

If any of these files don't exist for a given project, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT-MAP.md                          ← index of all project contexts
├── docs/adr/                               ← cross-project decisions (rare)
├── AWS-Insurance-FNOL-Voice-Agentic-AI/
│   ├── CONTEXT.md
│   └── docs/adr/                           ← project-specific decisions
├── Azure-Insurance-Claim-Guard-AI/
│   ├── CONTEXT.md
│   └── docs/adr/
└── ...one folder per project
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in that project's `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids. Terms don't necessarily carry across projects — the same word can mean different things in two unrelated projects in this monorepo.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_

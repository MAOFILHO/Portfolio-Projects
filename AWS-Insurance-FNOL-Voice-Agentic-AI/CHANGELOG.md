# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 0 (repo archaeology, workspace setup, merge strategy)
- `CLAUDE.md` with the STOP CONDITIONS block reproduced verbatim, conventions, commands and verified environment facts.
- `PROJECT_STATE.md` seeded with the 14-phase list, decisions, risks, open questions and Phase 0 exit criteria.
- `docs/phase0/MERGE-MATRIX.md` — 100 modules assessed across eight MIT-0 source repos: 20 KEEP / 22 REFACTOR / 5 REWRITE / 53 DISCARD (~97% discarded by lines of code).
- `docs/phase0/DEPENDENCY-CONFLICTS.md` — ten conflict classes with resolutions; baseline pinned to Python `>=3.12,<3.13`.
- `docs/phase0/DOMAIN-ARTIFACTS.md` — FNOL intake sequences, KABCO injury scale, coverage taxonomy, business rules, PII taxonomy, plus five domain gaps no source repo fills.
- `docs/phase0/SECURITY-FINDINGS.md` — do-not-propagate list, seven critical findings, and the PII gate ruling.
- `docs/phase0/TARGET-LAYOUT.md` — target monorepo layout with an explicit old→new path mapping.
- `.claude/settings.json` auto-approving read-only commands only.
- `.gitignore`, `CHANGELOG.md`, `README.md` stub.

### Notes
- No application code written and no billable AWS resource created in this phase.
- Verified against live AWS rather than the brief: the pre-provisioned DID is a **Canada** number (`PhoneNumberCountryCode: CA`), so US telephony rates do not apply.
- Extracted the modern contact-flow recording-block JSON from the live Connect instance, so the constraint-18 CI check is written against verified schema rather than an assumption.
- Confirmed `amazon.nova-micro-v1:0` is `INFERENCE_PROFILE`-only, making the `us.*` cross-region inference rule mandatory rather than stylistic.

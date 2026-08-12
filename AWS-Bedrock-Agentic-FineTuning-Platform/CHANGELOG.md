# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `data/splitter.py` — leak-free deterministic train/validation splitting. Group-aware for
  generative datasets, stratified for classification, ordered by SHA-256 digest so it stays
  RNG-free and order-independent. Covered by `tests/unit/test_splitter.py` (11 tests).
- `docs/RESULTS.md` — fine-tuning results and error analysis for the pharma scenario.
- `docs/COST-ACTUALS.md` — estimated vs actual spend, including three corrections to the
  original estimate and the non-adjustable 4 req/min throughput ceiling.
- `docs/INCIDENT-LOG.md` — forensics for ten fine-tuning attempts across two Regions.
- `README.md` — project documentation (Task 10.1).
- `ScenarioConfig.base_inference_model_id` — customization model IDs are `PROVISIONED`-only and
  cannot be passed to `Converse`; base-model inference needs a separate on-demand ID.
- `ScenarioConfig.max_output_tokens` — sent explicitly on every `Converse` call.

### Changed

- Migrated from `amazon.nova-2-lite-v1:0:256k` / `us-east-1` to
  `meta.llama3-3-70b-instruct-v1:0:128k` / `us-west-2` after seven consecutive customization
  failures in `us-east-1`. Root cause never identified — see `docs/INCIDENT-LOG.md`.
- S3 data bucket names are now Region-suffixed; bucket names are global while buckets are regional.
- `cost_estimator` derives Price List usage types from `base_model_id` instead of hardcoding one
  model's; unknown models raise `UnknownModelPricingError` rather than pricing the wrong model.
- Terraform `aws_region` validation relaxed from `us-east-1` only to the two Regions that support
  Bedrock model customization.
- Split strategy superseded — see `TASKS.md` **6.1a**. The original "last 10% of records" rule
  leaked: banking's held-out set was 3 distinct questions, all present in training under different
  conversational prefixes, with 23/23 gold answers appearing verbatim in training.

### Fixed

- `aws/session.py` ignored `AWS_REGION` and hardcoded `us-east-1`. The API, pipeline, and teardown
  all resolve their session here — teardown would have reported a clean destroy while an
  out-of-Region custom model kept accruing storage charges.
- `scripts/teardown.py` and `scripts/verify_empty.py` built the data bucket name inline without the
  Region suffix. Both targeted a bucket that never existed; `head_bucket` returned 404 and the
  zero-resource release gate **passed falsely**.
- `Converse` calls omitted `maxTokens`, so Bedrock reserved the model's maximum output quota per
  request — a documented cause of throttling at low request volume.
- Post-run tests rebuilt job names instead of reading the recorded ARN. Bedrock reserves job names
  permanently, so the canonical name resolved to a `Stopped` first attempt.
- Post-provision and pre-provision tests queried regional resources in `us-east-1` regardless of
  the configured Region. The Terraform backend lock table legitimately stays in `us-east-1` and is
  now pinned there explicitly.

## [0.1.0] - 2026-08-02

### Added

- Repository skeleton: directory tree, `pyproject.toml`, pinned `requirements.txt` /
  `requirements-dev.txt`, `Makefile`, `.gitignore`, `.env.example`.
- Planning contract: `PLAN.md`, `TASKS.md`, `COSTS.md`.
- Seven fine-tuning datasets moved into `data/` (three active demos: banking, IT
  helpdesk, pharmacovigilance; four disabled: gardening, support triage, patient
  triage, e-commerce).

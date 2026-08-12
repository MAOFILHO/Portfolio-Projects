# TASKS.md — AWS-Bedrock-Agentic-FineTuning-Platform

**This file is the execution contract.** Work the phases in order. Check boxes off as you complete them.
**Do not add scope that is not in this file.** If something here is wrong or impossible, stop and ask.

---

## Read this first — you may have never seen the planning conversation

Everything you need is in this file. Context you must not re-derive:

- **Goal:** automate a hands-on guide (`UserGuide - Create Bedrock Custom Model with Fine-tuning and Inference.pdf`)
  into a production Python project. Pipeline: **S3 upload → Bedrock fine-tune → deploy for on-demand
  inference → validate → teardown.**
- **Region:** `us-west-2`. **Revised during Phase 6** — originally `us-east-1`, where seven consecutive
  customization jobs failed across two Nova base models without ever reaching training. Root cause never
  identified; see [`docs/INCIDENT-LOG.md`](docs/INCIDENT-LOG.md). Bedrock model customization exists in
  **only** these two Regions — there is no third option.
- **Base model for fine-tuning:** `meta.llama3-3-70b-instruct-v1:0:128k` (**revised during Phase 6**;
  originally `amazon.nova-2-lite-v1:0:256k`). It is the only Custom-Model-on-Demand-capable fine-tunable
  model outside `us-east-1`, and it has **no Provisioned Throughput SKU at all**, making the $60.50/hr
  failure mode structurally impossible. It consumes the same `bedrock-conversation-2024` record format,
  so no dataset changes were required.
- **Inference mode:** **Custom Model on-Demand (CMoD)** — `CreateCustomModelDeployment`. Token-billed, $0 when
  idle.
- **⛔ NEVER use Provisioned Throughput.** It costs $60.50/hr/model = **$130,680/month** for three models.
  The strings `ProvisionedThroughput`, `aws_bedrock_provisioned_model_throughput`, and
  `create_provisioned_model_throughput` are forbidden in `src/`, `infra/`, `scripts/`. A unit test enforces it.
- **7 scenarios, 3 active.** Active: `banking`, `it_helpdesk`, `pharma`. Disabled: `gardening`,
  `support_triage`, `patient_triage`, `ecommerce`. Scenarios are **YAML data**, never code. Adding one must
  cost one config file.
- **Teardown order is mandatory:** delete CMoD **deployments** → delete **custom models** → empty **S3** →
  `terraform destroy`. Reversing it hangs the destroy. The post-teardown test is a **P0 release blocker**.
- **`CLAUDE.md` is read-only project law.** Never overwrite, truncate, or regenerate it. Append only, below
  existing content, and never touch its "Project Invariants" section.
- **Cost gate:** never run `terraform apply`, launch a fine-tuning job, or create a deployment without first
  printing a live cost estimate and receiving explicit typed approval.
- **Never claim a step succeeded without running its verification command and showing the output.**

Background detail lives in [`PLAN.md`](PLAN.md); the approved cost record is [`COSTS.md`](COSTS.md).
Read `PLAN.md` §1.9 before deviating from the guide — the deviations are deliberate and documented.

---

## Phase 0 — Gate: approval must exist

Decisions already recorded (`PLAN.md` §9, `COSTS.md` §5). **Use these; do not re-ask and do not substitute
your own defaults:**

| Setting | Value |
|---|---|
| Budget ceiling | **$25/month**, alerts at 50% / 80% / 100% ACTUAL + 100% FORECASTED |
| Epochs | **2** — write explicitly into every `ScenarioConfig` |
| Rollout | **All three demos** (`pharma`, `banking`, `it_helpdesk`) in this build |
| Observability | **Langfuse Cloud** — user-supplied keys, never invented |

- [x] **0.1** Confirm the cost table in `COSTS.md` §8 is accepted by the user. If not, **STOP**.
- [x] **0.2** Confirm the **budget alert email** is recorded in `.env`. It is the one input still outstanding.
      Terraform cannot create the budget without it, and the budget must exist before any billable resource.
      If missing, **STOP and ask** — never invent an email address.
- [x] **0.3** Note that **Langfuse Cloud keys** (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`)
      are required before **Phase 7 only**. Phases 1–6 proceed without them. Do not fabricate placeholder keys.

**Gate:**
```bash
grep -c '^- \[x\]' COSTS.md && grep -E '^BUDGET_(LIMIT_USD|ALERT_EMAIL)=' .env
```
Expected: `6` ticked boxes in `COSTS.md` §8, and `.env` showing `BUDGET_LIMIT_USD=25` plus a real
`BUDGET_ALERT_EMAIL`. Anything less → stop and ask.

---

## Phase 1 — Repository skeleton and tooling (no AWS, no cost)

- [x] **1.1** Create the directory tree exactly as specified in `PLAN.md` §5. Move the seven `.jsonl` files
      from the repo root into `data/`. Leave `CLAUDE.md`, `PLAN.md`, `TASKS.md`, `COSTS.md`,
      `README_Template.md`, and the source guide PDF at the root.
- [x] **1.2** Create `.venv` from Python **3.12** explicitly. The machine's default `python3` is 3.13 —
      that is the wrong version. Use `~/.pyenv/versions/3.12.10/bin/python3.12 -m venv .venv`.
- [x] **1.3** Write `requirements.txt` and `requirements-dev.txt` with the exact pins listed in `PLAN.md` §6.
      Install both. If a pin fails to resolve, report the conflict — do not silently loosen it.
- [x] **1.4** Write `pyproject.toml`: package metadata, `requires-python = ">=3.12,<3.13"`, `ruff` config
      (line length 100), `mypy` config (`strict = true` for `src/bedrock_platform`), `pytest` config
      (testpaths, asyncio mode).
- [x] **1.5** Write `.gitignore`. Must exclude at minimum: `.env`, `.venv/`, `__pycache__/`, `*.pyc`,
      `.terraform/`, `*.tfstate`, `*.tfstate.*`, `.terraform.lock.hcl` is **kept** (commit it),
      `.aws/`, `.azure/`, `node_modules/`, `dist/`, `.DS_Store`, `*.pem`, `credentials`.
- [x] **1.6** Write `.env.example` — **keys only, no values**:
      `AWS_REGION`, `AWS_PROFILE`, `PROJECT_SUFFIX`, `BUDGET_LIMIT_USD`, `BUDGET_ALERT_EMAIL`,
      `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
      `API_PORT`, `FRONTEND_PORT`.
- [x] **1.7** Write the `Makefile` with targets `setup`, `provision`, `run`, `teardown`, `test`, plus
      `test-unit`, `test-pre`, `test-post`, `lint`, `typecheck`, `frontend`. `provision` wraps
      `terraform apply`; `teardown` wraps `scripts/teardown.py` followed by `terraform destroy`.
- [x] **1.8** Write `CHANGELOG.md` at `v0.1.0` (Keep a Changelog format).

**Gate:**
```bash
.venv/bin/python --version && .venv/bin/python -c "import fastapi, pydantic, boto3, langgraph; print('imports ok')" && make --dry-run test
```
Expected: `Python 3.12.10`, then `imports ok`, then the make target echoes without error.

---

## Phase 2 — Config layer: scenarios as data

- [x] **2.1** Write `src/bedrock_platform/config/scenario_config.py` — the Pydantic v2 `ScenarioConfig` and
      `ValidationRule` models exactly as sketched in `PLAN.md` §3.5. `model_config = ConfigDict(extra="forbid")`.
- [x] **2.2** Write `src/bedrock_platform/config/settings.py` — `pydantic-settings` `Settings` reading `.env`.
      **No secret may have a default value.** Region defaults to `us-east-1`; `project_suffix` is **required**
      with no default (stable naming, never random — random suffixes orphan billable resources).
- [x] **2.3** Write the seven YAML files in `configs/scenarios/`. For each, lift `system_prompt` **verbatim**
      from the first record's `system[0].text` in the matching `.jsonl` — do not paraphrase it. Set
      `enabled: true` only for `banking`, `it_helpdesk`, `pharma`. Set `epochs` to the value approved in
      Phase 0.2. Lift `sample_prompts` from the guide's playground steps:
      - banking → `"How do I transfer money to my savings account?"`
      - it_helpdesk → `"My VPN keeps disconnecting every few minutes."`
      - pharma → `"A patient taking the study medication reported seizure; the patient was hospitalized"`
- [x] **2.4** Write `src/bedrock_platform/config/scenario_loader.py` — loads and validates all seven,
      raises on duplicate ids, exposes `enabled_scenarios()`.
- [x] **2.5** Write the output models in `src/bedrock_platform/models/outputs/`. The strict-JSON ones
      (`pharma`, `support_triage`, `patient_triage`) use `extra="forbid"` plus cross-field validators.
      `PharmaTriageOutput` must enforce: `expedited_reporting` may be `true` only when
      `seriousness == "Serious"` (this rule comes from the dataset's own system prompt).
- [x] **2.6** Write `tests/unit/test_scenario_config.py` and `tests/unit/test_output_models.py`.
      Assert: all 7 configs load; exactly 3 enabled; every `dataset_path` exists; every strict-JSON model
      rejects a payload with an extra key, a wrong enum value, and the expedited/seriousness contradiction.

**Gate:**
```bash
make test-unit
```
Expected: all tests pass; output includes a line confirming `7 scenarios loaded, 3 enabled`.

---

## Phase 3 — Deterministic AWS layer (no LLM, no agents yet)

Everything in `src/bedrock_platform/aws/` is plain boto3. **No agent, no LLM, ever calls into a mutation here
except via the gated path in Phase 7.**

- [x] **3.1** `aws/session.py` — boto3 session factory pinned to `us-east-1`, with a startup assertion that the
      resolved region is `us-east-1` (raise otherwise).
- [x] **3.2** `aws/guards.py` — a module that raises `ForbiddenResourceError` if any code path attempts
      provisioned throughput. Also export the forbidden-string list used by the CI test.
- [x] **3.3** `aws/cost_estimator.py` — queries the **live** AWS Price List API
      (`pricing` client, `ServiceCode=AmazonBedrock`, `regionCode=us-east-1`) for
      `USE1-Nova2.0Lite-Customization-Training`, `-Customization-Storage`,
      `-input-tokens-custom-model`, `-output-tokens-custom-model`. Never hardcode prices. Returns a
      Pydantic `CostEstimate`. Must degrade with a clear error if the API is unreachable — never fall back to
      a guessed number.
- [x] **3.4** `aws/s3_client.py` — upload training + validation objects, list `output/` artifacts, empty a
      bucket including **all object versions and delete markers**.
- [x] **3.5** `aws/finetune_client.py` — `create_model_customization_job`, `get_model_customization_job`,
      `list_custom_models`, `delete_custom_model`. Deterministic job naming from
      `{project_suffix}-{scenario_id}-ft`. Before launching: refuse if a completed custom model already exists
      for the scenario unless `force_retrain=True` **and** a typed approval token is supplied.
- [x] **3.6** `aws/deployment_client.py` — `create_custom_model_deployment`,
      `get_custom_model_deployment`, `list_custom_model_deployments`, `delete_custom_model_deployment`.
      **Must respect the service quota "In-progress custom model deployments = 2"**: wait for a free slot
      before creating, never fire three in parallel.
- [x] **3.7** `aws/inference_client.py` — Converse API against (a) the base model id and (b) a deployment ARN
      used as `modelId`. Returns text, input/output token counts, and measured latency in ms.
- [x] **3.8** `aws/teardown.py` — the ordered teardown from `PLAN.md` §1.8. Each step waits for the resource to
      actually disappear before proceeding. Idempotent: safe to run twice, safe to run when nothing exists.
- [x] **3.9** `scripts/print_cost_estimate.py` — prints the live cost table and **blocks on typed approval**
      (the user must type the literal word `APPROVE`). Used by `make provision` and by the fine-tune launcher.
- [x] **3.10** `tests/unit/test_cost_estimator.py` (moto/stubbed) and
      `tests/unit/test_no_provisioned_throughput.py` — the latter greps `src/`, `infra/`, `scripts/` for the
      forbidden strings and fails on any hit.

**Gate:**
```bash
make test-unit && .venv/bin/python scripts/print_cost_estimate.py --dry-run
```
Expected: unit tests pass, and the cost script prints a table with live per-1K-token prices for Nova 2 Lite
(training ≈ `$0.00378`, storage ≈ `$1.95/model/month`) and then exits without provisioning anything.

---

## Phase 4 — Terraform (billable — cost gate applies)

- [x] **4.1** `infra/terraform/bootstrap/` — one-time state bucket (versioned) + DynamoDB lock table
      (**`PAY_PER_REQUEST`**, never provisioned capacity). Plus `scripts/bootstrap_state.sh`.
- [x] **4.2** `versions.tf` — `required_version >= 1.9.0`, `hashicorp/aws ~> 6.0`. `backend.tf` — S3 backend
      with DynamoDB lock. `providers.tf` — region from variable, default tags
      (`Project`, `ManagedBy=terraform`, `CostCenter`).
- [x] **4.3** `modules/budget_alerts/` — `aws_budgets_budget` (COST, MONTHLY) with the approved limit and four
      notifications: 50% / 80% / 100% ACTUAL and 100% FORECASTED, all to the approved email.
      **This module must apply before any billable resource** — wire `depends_on` accordingly.
- [x] **4.4** `modules/s3_data/` — the data bucket. **Deviates from the guide deliberately** (see `PLAN.md`
      §1.9 C2): `aws_s3_bucket_public_access_block` with all four flags `true`,
      `aws_s3_bucket_ownership_controls` = `BucketOwnerEnforced`, SSE-S3 (`AES256`, not KMS), a bucket policy
      denying non-TLS access, and a lifecycle rule expiring `output/` after 30 days and aborting incomplete
      multipart uploads after 7. Add a comment in the module explaining why the guide's "allow public access"
      step is not followed.
- [x] **4.5** `modules/iam_bedrock_role/` — role assumable by `bedrock.amazonaws.com` with
      `aws:SourceAccount` and `aws:SourceArn` condition keys. Least privilege: `s3:GetObject`/`ListBucket` on
      the `training-data/` and `validation-data/` prefixes, `s3:PutObject` on `output/` only. No wildcards on
      resource.
- [x] **4.6** `modules/observability/` — CloudWatch log group with **explicit** 7-day retention.
- [x] **4.7** `main.tf`, `variables.tf` (`project_suffix` **required, no default**), `outputs.tf`,
      `terraform.tfvars.example`.
- [x] **4.8** `tests/pre_provision/` — Python 3.12; `sts get-caller-identity` succeeds; region is `us-east-1`;
      Nova 2 Lite `authorizationStatus == AUTHORIZED`; quota *In-progress custom model deployments* ≥ 2;
      all required env vars present.
- [x] **4.9** `tests/post_provision/` — bucket exists **and public access is fully blocked**; DynamoDB is
      `PAY_PER_REQUEST`; budget exists with the approved limit; IAM role trust policy names
      `bedrock.amazonaws.com`; log group retention == 7.

**Gate (run in order; 4.G3 spends money — the cost script must print and be approved first):**
```bash
# 4.G1 — no AWS calls
cd infra/terraform && terraform init -backend=false && terraform validate && terraform fmt -check -recursive
# 4.G2 — pre-provision smoke tests
make test-pre
# 4.G3 — plan, then apply behind the cost gate
make provision
# 4.G4 — post-provision smoke tests
make test-post
```
Expected: `Success! The configuration is valid.` → all pre-provision checks `PASS` → the cost table printed
and `APPROVE` typed → apply completes → all post-provision checks `PASS`, including
`bucket public access: BLOCKED` and `dynamodb billing mode: PAY_PER_REQUEST`.

**After 4.G3 the project is billing. Print the reminder: "Resources are live and billing. Run `make teardown`
when done."**

---

## Phase 5 — Teardown, proven early

Built now, before anything expensive exists, so the escape hatch is verified before it is needed.

- [x] **5.1** `scripts/teardown.py` — orchestrates `aws/teardown.py` then `terraform destroy -auto-approve`.
      Prints each step and what it found. Safe to run against an empty account.
- [x] **5.2** `scripts/verify_empty.py` — asserts zero custom model deployments, zero custom models, data
      bucket absent, IAM role absent, `terraform state list` empty.
- [x] **5.3** `tests/post_teardown/test_zero_resources.py` — **P0 release blocker.** Same assertions as 5.2,
      plus an ordering regression test asserting that attempting to delete a custom model while a deployment
      still references it is detected and handled rather than hanging.

**Gate:**
```bash
make teardown && .venv/bin/python scripts/verify_empty.py
```
Expected: teardown prints the four ordered steps, `terraform destroy` reports
`Destroy complete! Resources: N destroyed.`, and `verify_empty.py` prints `ZERO SURVIVING RESOURCES ✅`.

**Then re-run `make provision` to continue.** Proving teardown works on an empty-ish footprint is cheap;
proving it on a footprint with three custom models is not.

---

## Phase 6 — Runnable end-to-end pipeline (still no agents)

The project must be usable end-to-end at the end of this phase. The agentic layer is additive, not load-bearing.

- [x] **6.1** `scripts/run_pipeline.py` — CLI: `--scenario {id}`, `--skip-training` (reuse an existing model),
      `--force-retrain`. Steps: validate dataset → write the deterministic 90/10 split (see **6.1a**;
      **no RNG**) → upload both to S3 → print live cost estimate → **block on typed
      approval** → launch fine-tune → poll to `Completed` → create CMoD deployment → poll to `Active` →
      run the scenario's sample prompts against base and tuned → validate tuned output through the scenario's
      Pydantic model → write results to `artifacts/{scenario}/`.
- [x] **6.1a** `data/splitter.py` — leak-free deterministic split. **Supersedes the original "last 10% of
      records" rule**, which was wrong for these datasets: they group the same underlying question under
      several conversational prefixes sharing one gold answer, so a positional tail slice cut through groups.
      Measured on `banking_assistant.jsonl`, the old rule yielded a held-out set of **3 distinct questions,
      all present in training under different prefixes, with 23/23 gold answers appearing verbatim in
      training**, and containing **zero instances of either of the scenario's two contract rules**.
      Replacement: group by gold answer for generative datasets (no answer spans the split); stratify by
      label for classification datasets (every label stays represented on both sides — grouping there would
      delete whole classes from training). Ordering from a SHA-256 digest of the group key, so it is
      deterministic, order-independent, and RNG-free. Group indivisibility can overshoot the target ratio by
      at most one group; that is preferred over splitting a group.
      **Known limitation:** a behaviour backed by a single canned answer (banking's advice refusal, 10
      records sharing one string) forms one indivisible group and therefore can never be both trained and
      held out. Such behaviours need a purpose-written eval set, not a positional or grouped split.
- [x] **6.2** `validation/schema_guard.py` + `violation.py` — parse model output against the scenario's output
      model. On `ValidationError`, return a structured `SchemaViolation` (raw text, Pydantic error path,
      expected schema) — **never raise out of the request path**. A caught violation is a successful demo.
- [x] **6.3** FastAPI app: `api/app.py`, `api/deps.py`, `api/insecure_demo_auth.py`
      (hardcoded `demo`/`demo123`, module-level banner comment marking it as a deliberate insecure stub, no
      Cognito, no IAM, no token), and routes `scenarios.py`, `dataset.py`, `finetune.py`, `deploy.py`,
      `infer.py`, `health.py`. Every request and response is a Pydantic model — **no untyped dict crosses a
      boundary**. `/finetune/{id}/status` streams via SSE.
- [x] **6.4** `observability/otel.py` + `console_spans.py` — OTLP exporter to CloudWatch **plus** a console
      span exporter so traces are visible in the terminal during `make run`. Instrument FastAPI.
      Wire this **before** pipeline logic runs, not after.
- [x] **6.5** `tests/post_run/` — job status `Completed`; custom model ARN resolves; deployment `Active`;
      `output/` artifacts non-empty; tuned inference returns non-empty text; strict-JSON scenarios either
      parse cleanly or produce a well-formed `SchemaViolation`.
- [x] **6.6** `Dockerfile` (Python 3.12-slim, non-root user) and `docker-compose.yml` (api + frontend +
      optional self-hosted Langfuse).

**Gate (⚠️ this launches real fine-tuning jobs and bills ~$0.57 total across the three demos):**

Run **all three demos** (the approved rollout), but **sequentially, `pharma` first** — it is the strict-JSON
scenario and therefore the fastest way to shake out the Pydantic validation path before spending on the
other two:

```bash
make run SCENARIO=pharma        # ~4h — verify fully before continuing
make run SCENARIO=banking
make run SCENARIO=it_helpdesk
```
Expected per run: cost estimate printed → `APPROVE` typed → a real `jobArn` echoed → status polls
`InProgress` → `Completed` → a real deployment ARN → `Active` → base and tuned responses side by side with
real latencies → the scenario's Pydantic parse verdict shown. Then:
```bash
make test-post-run
```
Expected: all post-run checks `PASS` for all three scenarios.

> **Note 1:** the guide (§7 step 12) measures training at **~4 hours** per job. Do not treat a long
> `InProgress` as a failure. Do not poll faster than every 60 seconds.
>
> **Note 2:** the service quota ***In-progress custom model deployments* = 2**. Never create three
> deployments in parallel — `deployment_client.py` (Task 3.6) must wait for a free slot. Training jobs may
> queue against the *Scheduled customization jobs* quota of 10.

---

## Phase 7 — Agentic layer (LangGraph + MCP) — added last

- [x] **7.1** `agents/state.py` — the Pydantic graph state, including `approval_token: str | None`.
- [x] **7.2** `mcp/server_dataset.py` — tools `validate_dataset`, `split_dataset`, `estimate_training_cost`.
      All read-only.
- [x] **7.3** `mcp/server_bedrock.py` — tools `start_finetune_job`, `get_job_status`, `read_training_metrics`,
      `invoke_base_model`, `invoke_tuned_model`. **`start_finetune_job` refuses to execute unless
      `approval_token` is present in state and valid.** No delete tool. No IAM tool. No S3 lifecycle tool.
      No deployment-creation tool.
- [x] **7.4** `mcp/server_eval.py` — tool `score_output` (format compliance + schema validity). Read-only.
- [x] **7.5** `mcp/allowlist.py` — per-agent tool allowlist enforced at call time.
- [x] **7.6** The four sub-agents (`dataset_prep`, `finetune_supervisor`, `evaluation`, `inference`) and
      `agents/graph.py` wiring the orchestrator.
- [x] **7.7** `observability/langfuse_setup.py` — trace every agent step via **Langfuse Cloud** (the approved
      mode). Reads `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` from `.env`.
      **If those keys are absent, STOP and ask the user for them — never invent or placeholder them.**
      The app must start cleanly with tracing disabled rather than crash on missing keys.
- [x] **7.8** `tests/unit/test_agent_allowlist.py` — assert each agent can call only its allowlisted tools;
      assert no agent has access to any delete, IAM, budget, or teardown tool; assert `start_finetune_job`
      raises without a valid approval token.

**Gate:**
```bash
make test-unit && .venv/bin/python -m bedrock_platform.agents.graph --scenario pharma --dry-run
```
Expected: allowlist tests pass; the dry-run prints the planned node sequence
(`dataset_prep → finetune_supervisor → evaluation → inference`) and **executes no AWS mutation**.

---

## Phase 8 — CI/CD

- [x] **8.1** `.github/workflows/ci.yml` — `ruff check`, `ruff format --check`, `mypy`, `pytest tests/unit`,
      frontend `tsc --noEmit` and `npm run build`. Python 3.12.
- [x] **8.2** `.github/workflows/terraform.yml` — `terraform fmt -check`, `init -backend=false`, `validate`,
      and `plan` on pull requests. **Never `apply`.** No long-lived AWS keys — OIDC role assumption, and if no
      role is configured, the plan step is skipped rather than faked.
- [x] **8.3** Add the forbidden-string scan (`ProvisionedThroughput` et al.) as a required CI step.
- [x] **8.4** *(added beyond the original contract, at the user's request — 2026-08-10)*
      **Monorepo placement.** This project is a folder inside the `MAOFILHO/Portfolio-Projects`
      monorepo. GitHub Actions reads workflows **only** from `.github/workflows/` at the repository
      root — a `.github/workflows/` inside a project folder is silently ignored, so the first
      version of 8.1/8.2 would never have run. Workflows now live in
      `.github/workflows-for-monorepo-root/` (deliberately not a real workflows path, so they cannot
      look installed when they are not), are named `<project-slug>-{ci,terraform}.yml` per the
      monorepo convention, are `paths:`-scoped to this project's folder, and set
      `working-directory` on every job. Repository variables are prefixed `BEDROCK_PLATFORM_*` to
      avoid collisions in shared monorepo settings.
- [x] **8.5** *(added beyond the original contract, at the user's request — 2026-08-10)*
      `modules/github_oidc` — read-only GitHub Actions OIDC role for `terraform plan`. No long-lived
      AWS keys. Trust policy pins **both** `aud` and `sub`
      (`repo:MAOFILHO/Portfolio-Projects:ref:refs/heads/main`); omitting `sub` would let any
      repository on GitHub assume the role. Every allow statement is a read verb, plus an explicit
      `DenyAllMutations` that no later policy attachment can override. Opt-in via
      `enable_github_oidc`, set in `infra/terraform/terraform.tfvars` so a plain plan does not
      propose destroying it. Applied 2026-08-10: 3 resources, $0.00.

**Gate:**
```bash
make lint && make typecheck && make test-unit
```
Expected: `ruff` clean, `mypy` reports `Success: no issues found`, unit tests pass.

---

## Phase 9 — Frontend (built last, once the pipeline is stable)

- [x] **9.1** Scaffold Vite + React 19 + TypeScript 5.9 in `frontend/`. Pin exact versions in `package.json`
      (resolve with `npm view <pkg> version`, no `^` ranges).
      **Before starting: check whether the user supplied the reference screenshots.** If they did, match them.
      If not, build to the layout spec in `PLAN.md` §3.2 and use an inline-SVG Contoso wordmark placeholder.
- [x] **9.2** `theme/contoso.css` — Contoso palette, fixed **18%** left nav, 82% content pane.
- [x] **9.3** `LoginStub.tsx` — `demo` / `demo123`, client-side only, with a visible "Demo credentials —
      not real authentication" note on screen and a comment in the file.
- [x] **9.4** `LeftNav.tsx` — Contoso logo top-left, **Home** button, then the three active demos beneath it,
      rendered from `GET /scenarios` (**never hardcoded** — disabled scenarios must not appear, and enabling
      one in YAML must make it appear with no frontend change).
- [x] **9.5** `DemoScenario.tsx` + `PhaseRail.tsx` — the explicit click-through:
      select Foundation Model → load/inspect dataset → launch fine-tune → poll job status → run inference →
      compare base vs tuned. Surface **real** job ARNs, **real** status strings, **real** latency in ms.
      **No simulated progress bars over fake work.**
- [x] **9.6** `ComparePane.tsx` — base vs tuned side by side, each with its own Pydantic validation verdict.
- [x] **9.7** `SchemaViolationPanel.tsx` — amber panel showing raw model text, the Pydantic error path, and
      the expected schema. Headline it as a caught violation, **not** an error.
- [x] **9.8** `CostBanner.tsx` — persistent banner with live session cost and a teardown reminder.
- [x] **9.9** `api/types.ts` — mirrors the Pydantic API models exactly.

**Gate:**
```bash
cd frontend && npm run build && npm run dev
```
Expected: build succeeds with zero TypeScript errors; `http://localhost:5173` shows the login stub;
`demo`/`demo123` logs in; the left nav lists exactly **three** demos; selecting one renders the phase rail in
the right pane.

---

## Phase 10 — Documentation and handoff

- [x] **10.1** Write `README.md` following the structure of `README_Template.md`. Must include: business case,
      ASCII architecture diagram, prerequisites, quickstart, env var table, **cost table** (from `COSTS.md`),
      teardown instructions with the mandatory ordering, and:
      `## Author **Marcos Oliveira** — [LinkedIn](https://www.linkedin.com/in/mfilho1/) | [GitHub](https://github.com/MAOFILHO)`
- [x] **10.2** Update `CHANGELOG.md` for `v0.1.0`.
- [ ] **10.3** **Do not overwrite `CLAUDE.md`.** If re-entry context is worth adding, append a new section
      below the existing content and leave "Project Invariants" untouched.
- [x] **10.4** Confirm no secrets are committed: `.env` is absent from git, `.env.example` has keys only,
      no account IDs or emails hardcoded in source.
- [x] **10.5** Confirm the folder is self-contained and renameable (no absolute paths in code or config).

**Gate:**
```bash
grep -rEl '(AKIA|aws_secret_access_key|LANGFUSE_SECRET_KEY=.+)' --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=.git . ; echo "exit=$?"
test -f .env && echo "WARNING: .env present — must not be committed"
git check-ignore .env && echo ".env correctly ignored"
```
Expected: the grep matches nothing (`exit=1`), and `.env correctly ignored`.

---

## Phase 11 — Final validation and live-resource warning

- [x] **11.1** `make test` — all four suites (unit, pre-provision, post-provision, post-run).
- [x] **11.2** Confirm the frontend launches locally and completes one full demo click-through.
- [x] **11.3** State out loud to the user: **"Resources are live and billing. Run `make teardown` when done."**
- [x] **11.4** Report the actual session cost from the live cost estimator.
- [x] **11.5** Tell the user: `Project is GitHub-ready. Run git init && git add . && git commit`.

**Final gate — run only when the user confirms they are finished with the live demo:**
```bash
make teardown && .venv/bin/python scripts/verify_empty.py
```
Expected: `ZERO SURVIVING RESOURCES ✅`. **If this fails, the release is blocked.** Do not report success.

---

## Standing rules for whoever executes this file

1. **Work in order.** Later phases assume earlier gates passed.
2. **Show the verification output.** Never assert a step worked without pasting the command's output.
3. **Never provision without the printed cost estimate and a typed `APPROVE`.**
4. **Never use Provisioned Throughput.** $130,680/month for three models.
5. **Never leave a SKU to a provider default.** Set retention, billing mode, encryption, and epochs explicitly.
6. **Scenarios are data.** If you find yourself writing a per-scenario code branch, stop — it belongs in YAML.
7. **Stop and ask** rather than inventing a credential, region, model ID, dataset path, budget number, or
   email address.
8. **Teardown order is not optional:** deployments → custom models → S3 objects → `terraform destroy`.

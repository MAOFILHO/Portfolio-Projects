/*
 * The Lex V2 codehook Lambda.
 *
 * The handler is `src/fnol_voice_agent/api/lex_codehook.py`, deployed at Stage 3 implementing the wire
 * contract and replaced at Stage 4 with the graph invocation. Its own module docstring states exactly
 * what it does and does not do; that boundary is not restated here beyond one consequence that belongs
 * to the infrastructure: **the DID is not pointed at a contact flow until Stage 4** (`connect.tf`).
 *
 * NO SNAPSTART YET, AND THAT IS `ADR-009` BEING FOLLOWED RATHER THAN OVERLOOKED
 *   `ADR-009` fixes the mitigation order: smaller package first, then Python SnapStart, then a scheduled
 *   warmer, and provisioned concurrency last and cost-gated. Phase 9 measures. Turning SnapStart on now
 *   would be step two taken before step one was measured, and it also requires a published version and
 *   an alias, which is a second version-pinning surface of exactly the kind `RESULTS.md` §3.5.1 warns
 *   about. The function is built SnapStart-COMPATIBLE -- no client at module load, nothing captured at
 *   import -- and `tests/unit/test_lex_codehook.py` asserts that property rather than intending it.
 */

# ---------------------------------------------------------------------------------------------------
# Package
# ---------------------------------------------------------------------------------------------------

locals {
  repo_root   = abspath("${path.module}/../../../..")
  package_zip = "${path.module}/.terraform-build/lex-codehook.zip"
}

/*
 * The whole `fnol_voice_agent` package, not just `api/`.
 *
 * Stage 4 imports the graph from `fnol_voice_agent.agents`, so shipping only the entry point would work
 * today and break on the first stage that matters. Nothing outside `api/` is imported at module load, so
 * the extra files cost bytes and not milliseconds -- `ADR-009`'s "smaller package" step is about what is
 * IMPORTED on the init path, not about what is present on disk.
 *
 * Third-party dependencies are NOT in here. `D80`: an earlier version of this comment said Stage 4's
 * langgraph/boto3/pydantic requirements "land as a Lambda layer" while no layer, or any other
 * dependency-bundling mechanism, existed anywhere in this file -- a forward-looking sentence that was
 * never corrected once the thing it described didn't happen, and the deployed function crashed on
 * `ImportModuleError: No module named 'pydantic'` at cold-start import for the entire time it was live.
 * A comment asserting a resource exists is not itself evidence one does; `PROJECT_STATE.md`'s `D80`
 * entry is the fuller account. They land in `aws_lambda_layer_version.codehook_deps` below, now a real
 * resource in this file, not a sentence describing an intention.
 */
data "archive_file" "codehook" {
  type        = "zip"
  source_dir  = "${local.repo_root}/src"
  output_path = local.package_zip

  excludes = [
    "**/__pycache__",
    "**/__pycache__/**",
    "**/*.pyc",
  ]
}

# ---------------------------------------------------------------------------------------------------
# Dependency layer -- `D80`/`D81`. `docs/phase8/STAGE4-LAMBDA-LAYER-PLAN.md` §2-§3 has the full account:
# platform-matched wheels (Linux/`arm64`/`cp312`, not this dev machine's), the two real manylinux-tag
# failures hit building it, and the size measurement (111.7 MiB / 117,101,626 bytes unzipped -- corrected
# 2026-09-02, Phase 14 research pass; this comment previously said 162 MB, which was wrong -- / 54.0 MB
# zipped -- over the 50 MB direct-upload cap, hence S3 rather than `filename` below).
# ---------------------------------------------------------------------------------------------------

/*
 * Pinned to version 2 by a DATA SOURCE, not built and published from this file -- `D160`/`OI78`'s row.
 *
 * `version = 2`, not omitted: the `aws_lambda_layer_version` data source's own docs are explicit that
 * omitting `version` resolves to "the latest available layer version" (registry.terraform.io/providers/
 * hashicorp/aws/latest/docs/data-sources/lambda_layer_version) -- so pinning it here is what stops a
 * layer published later (by hand, out-of-band) from silently becoming what this function ships next
 * `apply`. That is deliberate, not a placeholder to bump without thought.
 *
 * WHY a reference, not a rebuild: `D160`/`OI78` (`docs/evidence/deployed-layer-v2-provenance.md`)
 * established that this layer is NOT currently reproducible from what this repo commits, on three
 * independent, unpinned dimensions -- an unpinned transitive closure (9 of 44 packages drifted version in
 * 8 days), an unexplained fixed `2049-01-01` file mtime nothing in `STAGE4-LAMBDA-LAYER-PLAN.md` §7 sets,
 * and an unpinned build interpreter (v2 was built under cpython-313; this repo's own `.venv` is
 * cpython-312). A fresh `pip install --target` run today produces different bytes and a different hash
 * than what is actually deployed, verified working, and referenced here. Rebuilding and republishing from
 * this file would force-replace a known-good, already-verified layer with an unverified one for no
 * functional reason -- and `PublishLayerVersion` is not an in-place update, so that replacement is a NEW
 * version, immediately live, the moment `apply` runs. Referencing the deployed artifact by version number
 * instead means `terraform plan` never reads `.terraform-build/layer` again and never risks that swap.
 *
 * This pin may change only when ALL of the following are true, not just one:
 *   1. A new layer version has been deliberately published and independently verified working -- built,
 *      alone, is not sufficient (that is exactly `D160`/`OI78`'s own finding about v2 vs. a same-day
 *      rebuild).
 *   2. `D160`/`OI78` has a recorded disposition -- reproducible build, or an accepted-risk decision to
 *      keep pinning by hand across versions. This pin is a symptom of that defect staying open, not a
 *      substitute for closing it.
 *   3. `version` below is updated, and this comment's own history reflects why, not a silent bump.
 */
data "aws_lambda_layer_version" "codehook_deps" {
  layer_name = "${local.name_prefix}-codehook-deps"
  version    = 2
}

/*
 * Detached from Terraform management here, not destroyed -- the layer version and its S3 object stay
 * exactly as deployed; only the *managing* of them moves out of this file, replaced by the data source
 * above reading the same ARN by version number.
 *
 * `removed` blocks, not a bare `terraform state rm`: HashiCorp's own state-removal guidance recommends
 * this ("we recommend using the `removed` block instead... it lets you preview the results of the
 * operation, which makes it a safer way to remove resources" --
 * developer.hashicorp.com/terraform/language/state/remove) specifically because the detach then shows up
 * in `terraform plan` before it happens, rather than taking effect immediately as a CLI side effect with
 * nothing to review first.
 *
 * `lifecycle { destroy = false }` is the documented mechanism for exactly this hand-off:
 * "Set destroy to false to remove the resource from state without destroying the actual resource... This
 * allows you to hand off management responsibilities to another tool or team after using Terraform for
 * the initial provisioning." (developer.hashicorp.com/terraform/language/block/removed)
 *
 * Rollback, if this detach is ever undone: both resource types support `terraform import` --
 * `aws_lambda_layer_version` by ARN (`arn:aws:lambda:us-west-2:759316130780:layer:fnol-codehook-deps:2`
 * as of this change), `aws_s3_object` by `bucket/key`
 * (`fnol-artifacts-759316130780-us-west-2/lambda-layers/codehook-deps-73deb4753ca856a7cc60270092e4be96.zip`).
 * Re-add the two `resource` blocks this change removes, then `terraform import` each -- no AWS resource
 * was ever destroyed by this change, so rollback has no data-loss exposure.
 */
removed {
  from = aws_lambda_layer_version.codehook_deps

  lifecycle {
    destroy = false
  }
}

removed {
  from = aws_s3_object.codehook_deps_layer

  lifecycle {
    destroy = false
  }
}

/*
 * ADOT (AWS Distro for OpenTelemetry) Python Lambda layer -- `ADR-018`, Phase 14. AWS-managed, not built
 * or published by this project: puts `opentelemetry` api/sdk, the OTLP-HTTP exporter, the AWS X-Ray
 * propagator/id-generator, and an X-Ray-exporting OTel collector Lambda extension on `/opt/python` and
 * `/opt/extensions`, with ZERO change to `codehook_deps` above or to `pyproject.toml`'s runtime deps --
 * see `src/fnol_voice_agent/observability/tracing.py`'s own module docstring for what runs on top of it.
 *
 * `layer_name` is given the layer's FULL ARN, not a bare name, because this layer is published in a
 * DIFFERENT AWS account (`901920570463`, AWS's own ADOT distribution account) from this project's
 * (`759316130780`) -- unlike `codehook_deps` above. The underlying `GetLayerVersion` API this data source
 * calls accepts either form in the same parameter: a bare name resolves inside the CALLER's own account
 * (which is what `codehook_deps` above relies on), and a full ARN reads whatever account published it --
 * exactly how every AWS-managed public layer (this one, the Lambda Insights layer, ...) is meant to be
 * referenced cross-account, with no separate cross-account IAM grant needed on this project's side
 * (AWS's own resource policy on the layer is what makes it publicly readable). A same-account-only data
 * source would have needed a hardcoded `local` ARN string instead, with the same reasoning stated inline
 * -- the full-ARN `layer_name` form is used here specifically because it lets this stay a real data
 * source (refreshed against the live API on every plan) rather than an untracked literal.
 *
 * `version = 7`, pinned explicitly -- same reasoning as `codehook_deps`'s own comment: omitting `version`
 * resolves to "the latest available layer version," and this project does not want an AWS-side layer
 * republish to silently change what this function ships on the next `apply`.
 */
data "aws_lambda_layer_version" "adot_python" {
  layer_name = "arn:aws:lambda:${var.region}:901920570463:layer:aws-otel-python-arm64-ver-1-32-0"
  version    = 7
}

# ---------------------------------------------------------------------------------------------------
# Execution role
# ---------------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "codehook" {
  name               = "${local.name_prefix}-codehook"
  description        = "Execution role for the Lex V2 codehook. Phase 8 Stage 3."
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

/*
 * Scoped to named resources, not `Resource: "*"`, with two named exceptions -- stated here plainly rather
 * than left for a reader to discover by grep.
 *
 * `docs/phase0/MERGE-MATRIX.md` records repo 8's IAM as the best example in the corpus and everything
 * else in it as over-broad; this is that example applied. The FIRST wildcard is on the log STREAM under
 * this function's own log group (`WriteOwnLogs` below), which cannot be named in advance because the
 * stream name contains the runtime's instance id. The SECOND, added Phase 14/`ADR-018`, is on
 * `WriteOwnTraceSegments`'s two X-Ray write actions (`xray:PutTraceSegments`/`xray:PutTelemetryRecords`)
 * -- X-Ray's write API supports no resource-level scoping at all (AWS's own `AWSXRayDaemonWriteAccess`
 * managed policy uses `Resource: ["*"]` for exactly these two actions), so there is no named-resource ARN
 * to scope this statement to the way every other statement below is scoped.
 */
data "aws_iam_policy_document" "codehook" {
  statement {
    sid       = "WriteOwnLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.codehook.arn}:*"]
  }

  # `ADR-018`/Phase 14. What actually makes traces show up in X-Ray -- the ADOT collector extension
  # (`data.aws_lambda_layer_version.adot_python`) exports OTLP-HTTP spans out to X-Ray via the classic
  # `PutTraceSegments` API, from inside this same execution role, not a separate one.
  statement {
    sid       = "WriteOwnTraceSegments"
    effect    = "Allow"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"] # X-Ray write actions support no resource-level scoping -- see this policy
    # document's own header comment for why this is the SECOND named exception.
  }

  statement {
    sid    = "AgentCheckpoints"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
    ]
    resources = [aws_dynamodb_table.checkpoints.arn]
  }

  statement {
    sid    = "KnowledgeRetrieval"
    effect = "Allow"
    # Read only. The Lambda answers coverage questions from the corpus; it never ingests. `make ingest`
    # runs under the operator's own credentials, so a prompt injection that reached the tool layer still
    # could not rewrite the knowledge base it is grounded against.
    actions   = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = [aws_dynamodb_table.knowledge_chunks.arn]
  }

  statement {
    sid       = "WriteArtifacts"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }

  /*
   * Bedrock. Scoped to the application inference profiles `ADR-016` created and to the `us.*` system
   * profiles they wrap.
   *
   * BOTH ARE REQUIRED, and the second one is not slack. Invoking through an application inference
   * profile authorises against the profile ARN *and* against the underlying foundation model in each
   * region the system profile routes to, so a policy naming only the application profile fails at
   * runtime with an AccessDenied that names a model nobody wrote down. The three-region set is the one
   * `make verify-inference` checks against `GetInferenceProfile` rather than assumes.
   */
  statement {
    sid       = "InvokeApplicationInferenceProfiles"
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["arn:aws:bedrock:${var.region}:${local.account_id}:application-inference-profile/*"]
  }

  statement {
    sid     = "InvokeModelsBehindThoseProfiles"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:${var.region}:${local.account_id}:inference-profile/us.*",
    ]
  }

  statement {
    sid       = "ApplyGuardrail"
    effect    = "Allow"
    actions   = ["bedrock:ApplyGuardrail"]
    resources = ["arn:aws:bedrock:${var.region}:${local.account_id}:guardrail/*"]
  }
}

resource "aws_iam_role_policy" "codehook" {
  name   = "${local.name_prefix}-codehook"
  role   = aws_iam_role.codehook.id
  policy = data.aws_iam_policy_document.codehook.json
}

# ---------------------------------------------------------------------------------------------------
# Function
# ---------------------------------------------------------------------------------------------------

/*
 * Declared explicitly rather than left to Lambda's implicit creation, for one reason that is not style:
 * an implicitly created log group has NO retention policy and keeps everything forever. That is a
 * slow-growing bill and, per `ADR-011`, an unbounded store of whatever a turn logged.
 */
resource "aws_cloudwatch_log_group" "codehook" {
  name              = "/aws/lambda/${local.name_prefix}-codehook"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "codehook" {
  function_name = "${local.name_prefix}-codehook"
  description   = "Lex V2 codehook. Phase 8 Stage 3 wire contract; Stage 4 adds the graph."
  role          = aws_iam_role.codehook.arn

  filename         = data.archive_file.codehook.output_path
  source_code_hash = data.archive_file.codehook.output_base64sha256

  runtime = "python3.12"
  handler = "fnol_voice_agent.api.lex_codehook.handler"

  memory_size = var.lambda_memory_mb
  timeout     = var.lambda_timeout_seconds

  architectures = ["arm64"]

  # `D80`/`D81`. Without this, `data.archive_file.codehook` (this function's own code zip, `src/` only)
  # is the entire deployed package -- exactly the configuration that crashed 100% of its invocations at
  # cold-start import for as long as it was live.
  #
  # `D160`/`OI78`, amended: this used to read `aws_lambda_layer_version.codehook_deps.arn` -- a managed
  # resource, so a rebuilt layer's new ARN flowed into this function's plan automatically. It no longer
  # does. The layer build was found not to be reproducible (see the data source's own comment above), so
  # this now reads a DATA SOURCE pinned to a fixed version number -- a rebuild no longer flows anywhere
  # near this function's plan at all, on purpose. Bumping the version pin above is the only way this
  # value changes now, and that comment states exactly what must be true before it does.
  #
  # `ADR-018`/Phase 14: ADOT LISTED FIRST, `codehook_deps` SECOND -- a real collision risk, not stylistic
  # ordering. The two layers share roughly a dozen top-level paths under `python/` (`certifi`, `idna`,
  # `charset_normalizer`, `requests`, `packaging`, `typing_extensions`, and their `.dist-info` dirs), and
  # Lambda merges layers in LIST ORDER, with a LATER layer overwriting an earlier one at an identical
  # path. Listing `codehook_deps` second means its own pinned, already-verified dependency versions
  # (`D160`/`OI78`) win on every shared path; ADOT's copies of those same packages exist only to support
  # its own bundled collector/exporter code, never to be what this function's application code imports.
  layers = [
    data.aws_lambda_layer_version.adot_python.arn,
    data.aws_lambda_layer_version.codehook_deps.arn,
  ]

  # `ADR-018`/Phase 14: PassThrough (the prior implicit default) means X-Ray records a trace only if the
  # INCOMING request already carries a sampled trace header -- Lex's own `lambda:Invoke` never does, so
  # PassThrough was functionally equivalent to tracing being off for every real call this function ever
  # serves. Active makes this function itself the one that decides to sample, which is what gives
  # `observability/tracing.py`'s `fnol.turn` root span a real `AWS::Lambda::Function` X-Ray segment to
  # nest under in the first place -- without this, that segment never exists for `_X_AMZN_TRACE_ID` to
  # name in the first place.
  tracing_config {
    mode = "Active"
  }

  /*
   * `ADR-016`: the application inference profile ARNs are supplied here, at deployment time, while
   * `settings.py` keeps the `us.*` literals as its DEFAULTS. That is what lets the simulator, the tests
   * and every Tier A eval run with no provisioned infrastructure, and it is why `make destroy` does not
   * break the local path -- the code falls back to something that still works.
   *
   * The guardrail identifier and version are passed for the same reason and with the opposite failure
   * posture: `BedrockGuardrailClient` takes both as REQUIRED constructor arguments with no default, so a
   * misconfigured deploy fails at construction rather than quietly evaluating against the wrong
   * guardrail. Version, not DRAFT -- `RESULTS.md` §3.5.1 rule 2.
   */
  environment {
    variables = {
      FNOL_AWS_REGION       = var.region
      FNOL_CHECKPOINT_TABLE = aws_dynamodb_table.checkpoints.name
      FNOL_VECTOR_TABLE     = aws_dynamodb_table.knowledge_chunks.name
      FNOL_ARTIFACT_BUCKET  = aws_s3_bucket.artifacts.id

      FNOL_ROUTER_MODEL_ID     = local.model_ids["router"]
      FNOL_GENERATION_MODEL_ID = local.model_ids["generation"]
      FNOL_EMBEDDING_MODEL_ID  = local.model_ids["embedding"]

      FNOL_GUARDRAIL_ID      = data.terraform_remote_state.guardrails.outputs.guardrail_id
      FNOL_GUARDRAIL_VERSION = data.terraform_remote_state.guardrails.outputs.guardrail_version

      # Read by no code in `src/` -- a pure cache-buster. See `variables.tf`'s `cold_probe_marker` for the
      # mechanism this exists to support: bumping it and applying forces a fresh execution environment,
      # Terraform-managed, in place of an out-of-band `update-function-configuration` touch.
      FNOL_COLD_PROBE_MARKER = var.cold_probe_marker
    }
  }

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.codehook.name
  }

  # Terraform infers no dependency on a role policy from a role reference, so without this the first
  # apply can create the function against a role that cannot yet write its own logs.
  depends_on = [
    aws_iam_role_policy.codehook,
    aws_cloudwatch_log_group.codehook,
  ]
}

/*
 * Lex's permission to invoke, scoped to this account. Without it the bot's codehook call fails with an
 * AccessDeniedException that surfaces to the caller as Lex's generic failure message -- a runtime
 * failure for a missing declaration, which is the class of defect an IaC project exists to remove.
 */
resource "aws_lambda_permission" "lex" {
  statement_id  = "AllowLexV2Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.codehook.function_name
  principal     = "lexv2.amazonaws.com"
  source_arn    = "arn:aws:lex:${var.region}:${local.account_id}:bot-alias/*"
}

/*
 * Connect's own association with the function. Distinct from the Lex codehook above and not a duplicate:
 * this is what makes the function selectable from a contact flow's `InvokeLambdaFunction` block, which
 * Stage 4 needs for the escalation path (`NOT-FIXED.md` #2 / `D43`), while the permission above is what
 * lets the BOT call it. Two different callers, two different grants.
 */
resource "aws_connect_lambda_function_association" "codehook" {
  instance_id  = local.instance_id
  function_arn = aws_lambda_function.codehook.arn
}

resource "aws_lambda_permission" "connect" {
  statement_id  = "AllowConnectInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.codehook.function_name
  principal     = "connect.amazonaws.com"
  source_arn    = local.instance_arn
}

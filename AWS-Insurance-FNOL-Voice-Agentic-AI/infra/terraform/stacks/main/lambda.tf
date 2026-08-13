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

  # `D80`/`D81`. Built by `make build-lambda-layer` (`docs/phase8/STAGE4-LAMBDA-LAYER-PLAN.md` §7) --
  # cross-platform pip resolution against Linux/`arm64`/`cp312` wheels, not a bare `pip install` on this
  # (Darwin) dev machine, which would silently produce macOS binaries. `deps_dir` must exist and be
  # populated before `terraform plan` can even read `data.archive_file.codehook_deps` below; an empty or
  # missing directory is a build-step failure, not a Terraform one, and must be diagnosed there first.
  #
  # `D82`. `deps_dir` is the directory pip installs INTO and is named `python/` for exactly one reason:
  # AWS Lambda's Python layer convention requires every package under a `python/<package>` path inside
  # the layer zip, so that unzipping to `/opt` lands them at `/opt/python/<package>` -- the one path
  # Lambda's runtime actually adds to `sys.path` for a layer. `archive_file.source_dir` zips a
  # directory's CONTENTS at the zip's root, not the directory itself -- pointing it AT `deps_dir` (i.e.
  # at `python/`) silently drops that one path component and was `D82`'s exact root cause: a real,
  # correctly-versioned layer that put every package at `/opt/pydantic` instead of `/opt/python/pydantic`,
  # which is never on `sys.path`. `source_dir` below is `deps_root` -- `deps_dir`'s PARENT -- so the zip
  # preserves `python/<package>/...`. `deps_root` contains nothing else, so nothing else ends up in the
  # zip alongside it.
  deps_root = "${path.module}/.terraform-build/layer"
  deps_dir  = "${local.deps_root}/python"
  deps_zip  = "${path.module}/.terraform-build/lex-codehook-deps.zip"
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
# failures hit building it, and the size measurement (162 MB unzipped / 54.0 MB zipped -- over the 50 MB
# direct-upload cap, hence S3 rather than `filename` below).
# ---------------------------------------------------------------------------------------------------

/*
 * `local.deps_dir` is built by `make build-lambda-layer` (plan §7), NOT by this data source -- the
 * cross-platform pip install is not something `archive_file` or any other Terraform data source does.
 * This only zips what is already on disk, deterministically, so the resulting hash is content-addressed
 * the same way `data.archive_file.codehook` already is above.
 *
 * `D82`, corrected: `source_dir` is `local.deps_root` -- `deps_dir`'s PARENT, i.e. the directory that
 * directly contains `python/` -- NOT `local.deps_dir` itself. `archive_file` zips a directory's
 * CONTENTS at the zip's root; pointing it at `deps_root` means the zip's root contains exactly one
 * entry, `python/`, with every package nested under it -- `python/pydantic/...`, `python/boto3/...` --
 * matching AWS Lambda's layer convention exactly. Pointing it at `deps_dir` (the bug this replaces) put
 * every package at the zip's OWN root instead, one path component short of where Lambda's runtime looks.
 * `scripts/verify_layer_contents.py --zip` asserts this structure directly against the built zip, not
 * only against the directory it was built from -- D82 passed every directory-based check that existed
 * before it and still shipped the wrong archive, which is exactly why a directory check alone is not
 * sufficient evidence for what ships.
 */
data "archive_file" "codehook_deps" {
  type        = "zip"
  source_dir  = local.deps_root
  output_path = local.deps_zip
}

/*
 * Content-hash-in-key, not `etag`-based change detection on a fixed key -- the mechanism plan §6 spells
 * out as a five-step chain so a changed layer is never mistaken for an unchanged one:
 *
 *   1. `output_md5` hashes the actual zip bytes this run produced; it changes iff the layer's contents
 *      change. (`output_md5`, not `output_base64sha256`, deliberately -- the latter's alphabet includes
 *      `/` and `+`, which are legal in an S3 key but produce awkward implicit "subfolders" and characters
 *      that need URL-encoding to reference directly; this key exists purely for content-addressing, not
 *      for its cryptographic strength, so the hex digest is the better fit.)
 *   2. That hash is embedded IN the key, so a content change is a NEW object at a NEW key, never an
 *      in-place overwrite Terraform would have to notice via a remote read.
 *   3. `aws_lambda_layer_version.codehook_deps.s3_key` references that key directly -- a changed key is a
 *      changed input attribute Terraform's plan cannot miss, because it compares a value it computed
 *      itself against state rather than inferring drift from a remote read.
 *   4. A changed `s3_key` means `PublishLayerVersion` runs again, which returns a new, distinct,
 *      immutable layer ARN -- there is no "update a layer version in place."
 *   5. `aws_lambda_function.codehook.layers` references that ARN directly (below), so the new version
 *      flows into the function's own plan automatically, in the same apply that published it.
 *
 * `etag` is kept as belt-and-suspenders for the out-of-band case (something changes the S3 object without
 * changing the local artifact), not the mechanism this depends on for the ordinary "rebuilt the layer"
 * case, which is steps 1-2 alone.
 */
resource "aws_s3_object" "codehook_deps_layer" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "lambda-layers/codehook-deps-${data.archive_file.codehook_deps.output_md5}.zip"
  source = data.archive_file.codehook_deps.output_path
  etag   = data.archive_file.codehook_deps.output_md5
}

resource "aws_lambda_layer_version" "codehook_deps" {
  layer_name  = "${local.name_prefix}-codehook-deps"
  description = "Third-party runtime dependencies for the codehook Lambda. D80/D81."
  s3_bucket   = aws_s3_bucket.artifacts.id
  s3_key      = aws_s3_object.codehook_deps_layer.key

  compatible_runtimes      = ["python3.12"]
  compatible_architectures = ["arm64"]
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
 * Scoped to named resources, not `Resource: "*"`.
 *
 * `docs/phase0/MERGE-MATRIX.md` records repo 8's IAM as the best example in the corpus and everything
 * else in it as over-broad; this is that example applied. The one wildcard is on the log STREAM under
 * this function's own log group, which cannot be named in advance because the stream name contains the
 * runtime's instance id.
 */
data "aws_iam_policy_document" "codehook" {
  statement {
    sid       = "WriteOwnLogs"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.codehook.arn}:*"]
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
  # cold-start import for as long as it was live. One layer named directly by ARN, not a hardcoded
  # version number, so a rebuilt layer's new ARN (§6 above) flows into this function's plan automatically.
  layers = [aws_lambda_layer_version.codehook_deps.arn]

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

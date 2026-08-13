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
 * Third-party dependencies are not in here and are not needed yet: the Stage 3 handler is pure stdlib.
 * Stage 4's langgraph/boto3 requirements land as a Lambda layer, which is the change that makes package
 * size a real number rather than a rounding error.
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

/*
 * The Lex bot, its build wait, and its published release.
 *
 * Three resources in a fixed order, and the middle one is the point:
 *
 *   1. `aws_cloudformation_stack.bot`      — the definition. Returns before the locale is built.
 *   2. `terraform_data.bot_built`          — waits for `DescribeBotLocale` to report `Built`.
 *   3. `aws_cloudformation_stack.release`  — publishes a version, points the alias, tells Connect.
 *
 * Step 2 exists because of a measurement, not a suspicion: Stage 2 recorded `CREATE_COMPLETE` at 38 s
 * and `Built` ~16 s later, on all three applies (`docs/phase8/LEXPOC-GATE.md` §4.1). Without it, step 3
 * races a build CloudFormation does not report on, and the failure mode is intermittent — which is the
 * kind that gets diagnosed as "flaky AWS" and retried.
 *
 * `RESULTS.md` §3.5.1 rule 3: when the served behaviour has a build step, wait on the build state, never
 * on the create call.
 */

locals {
  bot_template_body = templatefile("${path.module}/bot.yaml.tftpl", {
    bot_description          = var.bot_description
    idle_session_ttl_seconds = var.idle_session_ttl_seconds
    nlu_confidence_threshold = var.nlu_confidence_threshold
    voice_id                 = var.voice_id
    policy_number_prompt     = var.policy_number_prompt
    dtmf_end_timeout_ms      = var.dtmf_end_timeout_ms
  })

  /*
   * Hash of the bot definition with comment and blank lines stripped.
   *
   * This drives the published version's CloudFormation logical ID, so it is the thing that decides
   * whether a new version gets published — see `release.yaml.tftpl`'s header on the staleness trap.
   *
   * Comments are stripped for a specific failure: if the hash moves while the DRAFT definition does not,
   * Lex returns the EXISTING version for the new resource and the cleanup delete removes the version the
   * alias points at. A comment-only edit is the realistic way to cause that, and it is removed here. The
   * unrealistic ways are not, which is why `make verify-lex` reads the alias back from the service.
   */
  bot_definition_hash = substr(
    sha256(join("\n", [
      for line in split("\n", local.bot_template_body) :
      line if trimspace(line) != "" && !startswith(trimspace(line), "#")
    ])),
    0, 12
  )

  /*
   * Slots the rendered template actually marks for obfuscation, derived rather than restated.
   *
   * `D70` made obfuscation a decision, and a decision nobody reads back is a preference. Splitting on
   * `- Name: "` bounds each chunk at the next name, so "does this chunk contain ObfuscationSetting"
   * answers the question exactly — no line-counting, and no breakage when a slot gains a property.
   */
  _name_chunks = slice(
    split("- Name: \"", local.bot_template_body),
    1,
    length(split("- Name: \"", local.bot_template_body))
  )

  obfuscated_slots = sort([
    for chunk in local._name_chunks : split("\"", chunk)[0]
    if strcontains(chunk, "ObfuscationSetting:")
  ])

  release_template_body = templatefile("${path.module}/release.yaml.tftpl", {
    definition_hash = local.bot_definition_hash
    project_tag     = var.project_tag
  })
}

# ---------------------------------------------------------------------------------------------------
# Runtime role
# ---------------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "lex_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lexv2.amazonaws.com"]
    }

    # Confused-deputy guard. Without it, any account able to name this role's ARN in their own bot could
    # have Lex assume it. Both conditions, because `aws:SourceAccount` alone still permits any bot in
    # this account and `aws:SourceArn` alone is the pattern AWS itself now recommends pairing.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:lex:${var.region}:${local.account_id}:bot-alias/*"]
    }
  }
}

# `description` is ASCII, deliberately. IAM validates that field against the Latin-1 range -- tab, LF, CR,
# U+0020-U+007E, U+00A1-U+00FF -- so the em dash (U+2014) this line originally carried is rejected at
# `CreateRole`. `terraform validate` and `terraform plan` both accept it; the apply is the first thing that
# looks, and by then sixteen other resources exist. See `D76`.
resource "aws_iam_role" "lex_runtime" {
  name               = "${local.name_prefix}-lex-runtime"
  description        = "Role Lex assumes at runtime. Polly only; the codehook has its own role."
  assume_role_policy = data.aws_iam_policy_document.lex_assume.json
}

resource "aws_iam_role_policy" "lex_runtime" {
  name = "${local.name_prefix}-lex-runtime"
  role = aws_iam_role.lex_runtime.id

  /*
   * Polly and nothing else.
   *
   * AWS's own example for this role also grants `comprehend:DetectSentiment`. It is omitted deliberately:
   * the bot sets `DetectSentiment: false`, so the permission would authorise a per-utterance Comprehend
   * charge that nothing is supposed to make. A permission for a call that should never happen is how a
   * cost-hazard setting gets switched on later without anything failing.
   */
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "polly:SynthesizeSpeech"
      Resource = "*"
    }]
  })
}

# ---------------------------------------------------------------------------------------------------
# 1. The bot
# ---------------------------------------------------------------------------------------------------

resource "aws_cloudformation_stack" "bot" {
  name          = "${local.name_prefix}-bot"
  template_body = local.bot_template_body

  parameters = {
    BotName           = var.bot_name
    BotRuntimeRoleArn = aws_iam_role.lex_runtime.arn
    CodeHookLambdaArn = aws_lambda_function.codehook.arn
  }

  # A half-created bot is worse than none: it holds the name, so the retry fails on a conflict rather
  # than on the original error.
  on_failure = "DELETE"

  tags = {
    Component = "lex-bot"
  }

  depends_on = [aws_iam_role_policy.lex_runtime]
}

# ---------------------------------------------------------------------------------------------------
# 2. The wait. Not optional, not an assumption, and not `sleep`.
# ---------------------------------------------------------------------------------------------------

resource "terraform_data" "bot_built" {
  # Re-runs whenever the definition changes, which is exactly when a rebuild happens. A change to the
  # bot's name or role also replaces the stack, and `bot_id` moving re-triggers this too.
  triggers_replace = {
    definition_hash = local.bot_definition_hash
    bot_id          = aws_cloudformation_stack.bot.outputs["BotId"]
  }

  /*
   * `local-exec` rather than `time_sleep`, and the difference is the whole finding. A fixed sleep encodes
   * the 16 s Stage 2 happened to measure and will be wrong on the first slower day — and when it is
   * wrong it fails downstream, in `CreateBotVersion`, with an error about the version rather than about
   * the build. This polls the state the next step actually depends on.
   *
   * The script exits non-zero on `Failed`, on timeout, and on an unrecognised status. Fail-closed: an
   * unknown status is not evidence of a built locale.
   */
  provisioner "local-exec" {
    command = join(" ", [
      "${local.repo_root}/.venv/bin/python",
      "${local.repo_root}/scripts/wait_for_lex_build.py",
      "--bot-id", aws_cloudformation_stack.bot.outputs["BotId"],
      "--locale-id", "en_US",
      "--region", var.region,
      "--timeout", tostring(var.lex_build_timeout_seconds),
    ])
  }
}

# ---------------------------------------------------------------------------------------------------
# 3. Version, alias, and the Connect association
# ---------------------------------------------------------------------------------------------------

resource "aws_cloudformation_stack" "release" {
  name          = "${local.name_prefix}-bot-release"
  template_body = local.release_template_body

  parameters = {
    BotId             = aws_cloudformation_stack.bot.outputs["BotId"]
    BotAliasName      = var.bot_alias_name
    CodeHookLambdaArn = aws_lambda_function.codehook.arn
    ConnectInstanceId = local.instance_id
  }

  on_failure = "DELETE"

  tags = {
    Component = "lex-release"
  }

  # The ordering that makes this correct. Terraform would otherwise infer only the `BotId` dependency,
  # which is satisfied the moment the bot stack returns — 16 seconds too early.
  depends_on = [
    terraform_data.bot_built,
    aws_lambda_permission.lex,
  ]
}

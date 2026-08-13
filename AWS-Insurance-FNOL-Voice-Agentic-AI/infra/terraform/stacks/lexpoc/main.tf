/*
 * ADR-007's proof-of-concept gate. Phase 8 Stage 2. THROWAWAY STACK.
 *
 * WHY THIS EXISTS
 *   `ADR-007` chose nested CloudFormation `AWS::Lex::Bot` over native `aws_lexv2models_*`, and said so
 *   with an unusually explicit admission: the rejection of the native option rests on two confirmed,
 *   dated, open provider bugs, while the choice of this option rests on the ABSENCE of a confirmed one.
 *   It refused to call that resolved and wrote a mandatory Phase 8 POC into its own consequences
 *   section. This stack is that POC.
 *
 *   The gate, verbatim from the build plan: "Build the smallest `AWS::Lex::Bot` stack that exercises the
 *   FNOL intent with `PromptAttemptsSpecification` and `DTMFSpecification`, apply it, change a prompt,
 *   apply again, and confirm the change actually took. If it does not, `ADR-007` is superseded here —
 *   not worked around."
 *
 *   The second apply is the whole test. #42147 is a SILENT failure: the first apply always looks fine.
 *
 * SEPARATELY AUTHORISED, AND DESTROYED WHEN THE GATE RESOLVES
 *   Marco approved this apart from the phase, because "a resource created to test whether we can create
 *   resources is exactly the thing that gets folded in silently and then never accounted for." It has
 *   its own line in `COSTS.md` and it is deleted once the gate answers, pass or fail. Exit criterion 15.
 *
 * COST
 *   $0.00 at rest. Lex V2 bills per text or speech request only — there is no charge for storing a bot,
 *   for a locale build, or for any `lexv2-models` control-plane call. The gate's runtime probes are
 *   `RecognizeText` calls at $0.00075 each, an order of magnitude under a cent in total, logged anyway.
 *
 * STATE
 *   Its own backend key, like every other stack — `verify-destroy-scope` asserts key uniqueness across
 *   the repo, and a throwaway sharing state with something permanent is how a throwaway stops being one.
 */

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket       = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key          = "stacks/lexpoc/terraform.tfstate"
    region       = "us-west-2"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = var.project_tag
      Owner   = "marcos"
      Phase   = "8"
      Managed = "terraform"
      # The one tag that says this is not part of the system. Without it, a throwaway looks exactly like
      # a component in `verify-billable`, in Cost Explorer, and to anyone reading the console.
      Ephemeral = "true"
    }
  }
}

# Lex assumes this at runtime. Authored here rather than inside the nested template on purpose: IAM is
# the one thing that should never disappear into an opaque `aws_cloudformation_stack` diff, and keeping
# it in Terraform also means the POC needs no `CAPABILITY_IAM` on the stack.
resource "aws_iam_role" "bot_runtime" {
  name        = "${var.bot_name}-runtime"
  description = "Runtime role for the throwaway ADR-007 POC bot. Deleted with the stack."

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lexv2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# AWS's own `AWS::Lex::Bot` template example grants `polly:SynthesizeSpeech` AND
# `comprehend:DetectSentiment`. Only the first is here. `comprehend:DetectSentiment` is used solely when
# a bot alias enables sentiment analysis, which bills a Comprehend call per utterance and is on Phase 0's
# cost-hazard list. Granting permission for a billable feature we deliberately do not enable is how it
# gets enabled later by someone who sees the permission and assumes it was intended.
resource "aws_iam_role_policy" "bot_runtime" {
  name = "lex-runtime"
  role = aws_iam_role.bot_runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "polly:SynthesizeSpeech"
      Resource = "*"
    }]
  })
}

locals {
  template_body = templatefile("${path.module}/bot.yaml.tftpl", {
    policy_number_initial_prompt = var.policy_number_initial_prompt
    dtmf_end_timeout_ms          = var.dtmf_end_timeout_ms
  })
}

resource "aws_cloudformation_stack" "bot" {
  name = var.bot_name

  # Rendered from the .tftpl. Changing either variable changes this body, which is what makes the second
  # apply a genuine template update rather than a parameter tweak.
  template_body = local.template_body

  parameters = {
    BotName           = var.bot_name
    BotRuntimeRoleArn = aws_iam_role.bot_runtime.arn
  }

  # A failed CREATE otherwise leaves a ROLLBACK_COMPLETE stack that blocks re-creating the same name and
  # has to be deleted by hand — a console click this project does not get to spend. Terraform still
  # surfaces the failing resource's status reason in the error, so nothing diagnostic is lost.
  on_failure = "DELETE"

  # Whether these reach the bot itself is checked, not assumed — see `scripts/lexpoc_gate.py`. Stage 0
  # already found one place where a tag was activated and propagated to nothing.
  tags = {
    Ephemeral = "true"
  }
}

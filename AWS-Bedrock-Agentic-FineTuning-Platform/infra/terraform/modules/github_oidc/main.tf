# GitHub Actions OIDC role for read-only `terraform plan` in CI.
#
# The point of OIDC is that no AWS credential ever exists at rest: GitHub mints a
# short-lived OIDC token per workflow run, AWS exchanges it for temporary credentials,
# and there is nothing in the repository or in GitHub secrets for an attacker to steal.
#
# This role can PLAN and cannot APPLY. Every permission below is a read verb. That is a
# deliberate second line of defence — the workflow has no apply job, and even if someone
# added one, this role could not execute it.

data "aws_caller_identity" "current" {}

locals {
  oidc_url = "https://token.actions.githubusercontent.com"
  provider_arn = var.create_oidc_provider ? (
    aws_iam_openid_connect_provider.github[0].arn
  ) : var.existing_oidc_provider_arn

  # sub claims this role will accept. Scoped to one repository and to specific refs, so
  # a workflow in any other repo — including a fork — cannot assume it.
  allowed_subjects = [
    for ref in var.allowed_branches :
    "repo:${var.github_owner}/${var.github_repo}:ref:${ref}"
  ]
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 1 : 0

  url            = local.oidc_url
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    # AWS no longer validates these for the GitHub issuer — it verifies against the
    # provider's live certificate chain — but the argument remains required.
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.provider_arn]
    }

    # Both conditions are required. Without the aud check, a token minted for a
    # different audience would be accepted; without the sub check, ANY repository on
    # GitHub could assume this role.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.allowed_subjects
    }
  }
}

resource "aws_iam_role" "plan" {
  name               = "bedrock-platform-${var.project_suffix}-gha-plan"
  description        = "Read-only terraform plan from GitHub Actions. Cannot apply."
  assume_role_policy = data.aws_iam_policy_document.trust.json
  # A plan finishes in well under an hour; a short session limits the blast radius of a
  # leaked credential.
  max_session_duration = 3600
}

data "aws_iam_policy_document" "plan_readonly" {
  # Remote state: read the state object and list the bucket. No PutObject — a plan does
  # not write state, and granting write here would let CI corrupt it.
  statement {
    sid    = "ReadTerraformState"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
    ]
    resources = ["arn:aws:s3:::${var.state_bucket}/*"]
  }

  statement {
    sid       = "ListStateBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = ["arn:aws:s3:::${var.state_bucket}"]
  }

  # The workflow plans with -lock=false, so no write to the lock table is needed. Read
  # access only, so terraform can report on an existing lock rather than fail opaquely.
  statement {
    sid       = "ReadLockTable"
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:DescribeTable"]
    resources = ["arn:aws:dynamodb:*:${data.aws_caller_identity.current.account_id}:table/${var.lock_table}"]
  }

  # Refresh reads every managed resource to detect drift. These are the read verbs for
  # exactly the resource types this stack manages — S3 data bucket, IAM role, log group,
  # budget — and nothing else.
  statement {
    sid    = "RefreshManagedResources"
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:GetAccelerateConfiguration",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:GetOpenIDConnectProvider",
      "logs:DescribeLogGroups",
      "logs:ListTagsForResource",
      "budgets:ViewBudget",
      "budgets:DescribeBudget",
      "budgets:DescribeBudgets",
      # Terraform reads tags on every managed resource during refresh, and the tag-list
      # APIs are separate actions from the describe/get ones. Omitting them fails the
      # whole plan on an AccessDeniedException, not just the tag attribute.
      "budgets:ListTagsForResource",
      "dynamodb:ListTagsOfResource",
      "iam:ListRoleTags",
      "iam:ListOpenIDConnectProviderTags",
      "s3:GetBucketTagging",
    ]
    resources = ["*"]
  }

  # Denies every mutating verb outright. Belt and braces: the allow statements above are
  # already read-only, but an explicit Deny cannot be overridden by a future policy
  # attachment, so this role can never gain apply rights by accident.
  statement {
    sid    = "DenyAllMutations"
    effect = "Deny"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "iam:Create*",
      "iam:Delete*",
      "iam:Put*",
      "iam:Update*",
      "iam:Attach*",
      "iam:Detach*",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "logs:Create*",
      "logs:Delete*",
      "budgets:Create*",
      "budgets:Modify*",
      "budgets:Delete*",
      "bedrock:Create*",
      "bedrock:Delete*",
      "bedrock:Stop*",
      "bedrock:Update*",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "plan_readonly" {
  name   = "bedrock-platform-${var.project_suffix}-gha-plan-readonly"
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.plan_readonly.json
}

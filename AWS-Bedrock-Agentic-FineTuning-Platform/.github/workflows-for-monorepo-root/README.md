# Workflows belong at the monorepo root, not here

This project is a self-contained folder inside the **`MAOFILHO/Portfolio-Projects`**
monorepo. GitHub Actions reads workflows **only** from `.github/workflows/` at the
repository root — a `.github/workflows/` directory inside a project folder is silently
ignored. No error, no warning; the workflows simply never run.

Copy both files to the monorepo root when installing this project:

```bash
cp AWS-Bedrock-Agentic-FineTuning-Platform/.github/workflows-for-monorepo-root/*.yml \
   .github/workflows/
```

They are already path-scoped to
`AWS-Bedrock-Agentic-FineTuning-Platform/**`, so they never fire on a
sibling project's changes, and every job sets `working-directory` to this project folder.

**If the folder is ever renamed**, update the `paths:` filters, `working-directory:`
values, and `cache-dependency-path:` entries in both files — a mismatch makes the
workflows stop running silently rather than fail loudly.

## Repository variables required by the Terraform workflow

The `plan` job skips itself with a GitHub notice until these are set (Settings →
Secrets and variables → Actions → Variables). They are **variables, not secrets** —
none is sensitive, and there are no long-lived AWS keys anywhere in this setup.

| Variable | Value |
|---|---|
| `BEDROCK_PLATFORM_PLAN_ROLE_ARN` | `terraform output github_actions_plan_role_arn` |
| `BEDROCK_PLATFORM_PROJECT_SUFFIX` | e.g. `marco-demo01` |
| `BEDROCK_PLATFORM_AWS_REGION` | `us-west-2` |
| `BEDROCK_PLATFORM_BUDGET_ALERT_EMAIL` | your alert address |
| `BEDROCK_PLATFORM_BUDGET_LIMIT_USD` | `25` |

Names are prefixed so they cannot collide with a sibling project's variables in the
shared monorepo settings.

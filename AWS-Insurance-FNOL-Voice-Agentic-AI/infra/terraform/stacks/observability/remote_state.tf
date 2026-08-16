/*
 * Stage B1 needs `stacks/main`'s Lambda function name and Lex bot/alias ids for the operational
 * dashboard's native-metric widgets. Read via `terraform_remote_state`, not restated as a literal or a
 * variable with a hand-copied default -- the same reasoning `outputs.tf`'s own comment gives for
 * `stacks/main`'s declared-value outputs: a second copy of a value that can drift (a bot republish moves
 * `bot_id`; a codehook redeploy does not move `function_name`, but nothing here should assume that
 * asymmetry rather than read it) is a comparison waiting to go stale. Read-only: this data source cannot
 * write to `stacks/main`'s state, and this stack's own `main.tf` still asserts `stacks/main` was never
 * created by this directory (n/a here -- that assertion lives in `stacks/main` itself; noted so this
 * comment doesn't imply a boundary this file doesn't police).
 */

data "terraform_remote_state" "main" {
  backend = "s3"

  config = {
    bucket = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key    = "stacks/main/terraform.tfstate"
    region = "us-west-2"
  }
}

/*
 * Stage 4 exit criterion 10 -- routing the DID. Last thing in the stage, gated on criterion 9 (`C1`
 * re-verified on the DEPLOYED system, not the local graph call `D52` measured) having already passed.
 *
 * `var.route_did` defaults to `false`, so a routine `terraform apply` -- including every apply this
 * project has run so far -- creates nothing here and reads nothing from `stacks/telephony`'s state.
 * `count = var.route_did ? 1 : 0` on both the remote-state read and the association resource is the
 * mechanism, not a comment: it is the difference between "gated" as a procedural promise and "gated" as
 * something Terraform itself enforces regardless of who runs the apply or when.
 *
 * `tests/unit/test_stack_main.py::test_the_stack_does_not_read_the_protected_stacks_state` is updated,
 * not deleted, to match: the source now names `stacks/telephony/terraform.tfstate` (D75's own docstring
 * anticipated this — `stacks/telephony/outputs.tf`'s header comment was written before this file
 * existed), and the test now asserts the read is gated behind `var.route_did`, still `false` by default,
 * rather than asserting the reference is absent outright. The property D75 actually cares about --
 * "a routine apply has no path toward the protected number" -- survives the edit; only its shape changes,
 * from "no reference exists" to "the reference cannot fire without an explicit, named flag."
 *
 * Flipping `var.route_did` to `true` is not this file's decision. It happens once, by hand or by a
 * `-var` flag on the one apply that runs after criterion 9's deployed re-verification passes, and that
 * apply is logged in `PROJECT_STATE.md` and `COSTS.md` like every other Stage 4 action.
 */

variable "route_did" {
  description = <<-EOT
    Gates the DID association. MUST stay `false` until Stage 4 exit criterion 9 -- `C1` re-verified
    against the DEPLOYED Lambda and Lex alias -- has passed. Marco, on granting `APPROVED: Stage 4`:
    "D75 kept the number unrouted because an FNOL bot without injury detection admits no negotiation --
    that reasoning is only satisfied once L1/L2 are verified live, not once they are merely deployed."
    Flipping this before criterion 9 passes reintroduces exactly the risk `D75` was written to prevent.
  EOT
  type        = bool
  default     = false
}

# Gated the same way as the resource below, deliberately -- a data source with `count = 0` is not
# evaluated at all, so this makes zero calls to read `stacks/telephony`'s state on a routine apply, not
# merely zero calls to create anything.
data "terraform_remote_state" "telephony" {
  count   = var.route_did ? 1 : 0
  backend = "s3"

  config = {
    bucket = "fnol-voice-agent-tfstate-759316130780-us-west-2"
    key    = "stacks/telephony/terraform.tfstate"
    region = "us-west-2"
  }
}

resource "aws_connect_phone_number_contact_flow_association" "inbound" {
  count = var.route_did ? 1 : 0

  phone_number_id = data.terraform_remote_state.telephony[0].outputs.phone_number_id
  instance_id     = local.instance_id
  contact_flow_id = aws_connect_contact_flow.inbound.contact_flow_id
}

output "did_routed" {
  description = "Whether this apply routed the DID. False on every apply until criterion 9 passes."
  value       = var.route_did
}

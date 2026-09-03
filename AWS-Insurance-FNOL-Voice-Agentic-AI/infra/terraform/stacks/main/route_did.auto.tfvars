# Persists `route_did`'s already-passed gate, per `did.tf`'s own docstring: "Flipping var.route_did to
# true is not this file's decision. It happens once, by hand or by a -var flag on the one apply that runs
# after criterion 9's deployed re-verification passes" -- that flip happened for real on 2026-08-29
# (`COSTS.md`'s "route_did flip" row) and the DID has been live-routed ever since. `route_did` still
# DEFAULTS to `false` in `did.tf` -- that default is correct history, not touched here -- but nothing in
# the repo persisted the post-flip `true` value, so a plain `terraform plan`/`apply` on this stack, run by
# anyone, without an explicit `-var route_did=true`, would see the variable's default (`false`) against
# the live reality (`true`) and propose DE-ROUTING THE LIVE PHONE NUMBER. Found and flagged 2026-09-03
# during Phase 14's deploy (worked around that one apply with an explicit `-var`, not fixed at the time).
# `*.auto.tfvars` files are loaded by Terraform automatically, no flag needed -- unlike `terraform.tfvars`,
# this filename is not in `.gitignore`, so it is committed and travels with the repo rather than living
# only on one operator's machine.

route_did = true

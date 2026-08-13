/*
 * The import, in its own file so it is impossible to miss.
 *
 * Constraint 16: "Terraform consumes the instance via a data source or import; it must never run
 * create-instance and never create a second instance." The same posture applies to the number, more
 * strictly -- a second Connect instance is an annoyance and a second claimed DID is a $0.06/day mistake
 * that cannot be undone for 180 days.
 *
 * A declarative `import` block rather than a `terraform import` command, because the command is a
 * one-time act on a machine and the block is a fact in the repository. Anyone running `terraform plan`
 * here on a clean checkout gets the same behaviour, and the ID is reviewable in a diff.
 *
 * Once the import has run, this block is a no-op that Terraform re-verifies on every plan. It stays.
 */

import {
  to = aws_connect_phone_number.did
  id = var.phone_number_id
}

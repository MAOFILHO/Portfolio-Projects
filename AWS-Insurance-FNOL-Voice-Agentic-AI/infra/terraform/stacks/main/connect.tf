/*
 * Contact flow, hours of operation, queue.
 *
 * THE DID IS NOT POINTED AT THIS FLOW, AND THAT IS A DECISION
 *   `aws_connect_phone_number_contact_flow_association` is absent from this stack on purpose, and its
 *   absence is the reason `stacks/telephony`'s remote state is not read here either.
 *
 *   A number pointed at a flow is a number a stranger can dial. The Stage 3 codehook implements the Lex
 *   wire contract and does not yet run L1/L2 — so an FNOL bot behind this number today would collect
 *   claim details from a caller and have no injury-detection path at all, which is the one thing
 *   `CLAUDE.md` marks as admitting no negotiation and no discretion. An unrouted number rings out. That
 *   is a worse demo and a better system, and the trade is not close.
 *
 *   The association lands in Stage 4, behind a working safety path, and is one resource.
 *
 * ROLLBACK: UNIQUELY-NAMED FLOWS, AND WHY THE NAME ALONE IS NOT ENOUGH
 *   The flow's name carries a hash of its content, so a new version never occupies the old one's name.
 *   That is necessary and it is not sufficient, because `aws_connect_contact_flow` treats BOTH `name`
 *   and `content` as updatable — the provider calls `UpdateContactFlowName` and `UpdateContactFlowContent`
 *   rather than replacing. Left alone, a content change would rename and overwrite the live flow in
 *   place, which is exactly the failure the unique name was supposed to prevent, while looking like it
 *   had been prevented.
 *
 *   So the name is paired with `replace_triggered_by` + `create_before_destroy`. The new flow is created
 *   FIRST; if its content is rejected, the create fails and the flow currently serving is untouched.
 */

# ---------------------------------------------------------------------------------------------------
# Hours of operation
# ---------------------------------------------------------------------------------------------------

/*
 * 24/7, and this is a domain decision rather than a shortcut.
 *
 * `DOMAIN-ARTIFACTS.md` records the regulatory FNOL clock at 24 hours from the loss. Collisions do not
 * keep business hours, and a first-notice line that is closed at 3am is a line that fails the one
 * deadline the domain actually imposes. The queue below inherits these hours; when Stage 6 wires the
 * real transfer, out-of-hours behaviour becomes a staffing question, not an intake one.
 */
resource "aws_connect_hours_of_operation" "always" {
  instance_id = local.instance_id
  name        = "${local.name_prefix}-always-open"
  description = "24/7. FNOL intake has a 24-hour regulatory clock; losses do not keep business hours."
  time_zone   = var.hours_time_zone

  dynamic "config" {
    for_each = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

    content {
      day = config.value

      start_time {
        hours   = 0
        minutes = 0
      }

      # 23:59, not 24:00 — Connect rejects an end hour of 24, and 00:00-00:00 is an empty window rather
      # than a full day. The one minute is unreachable in practice: a call in progress is not cut off.
      end_time {
        hours   = 23
        minutes = 59
      }
    }
  }
}

# ---------------------------------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------------------------------

/*
 * Created here and UNUSED BY THE FLOW at Stage 3, deliberately.
 *
 * `NOT-FIXED.md` #2 / `D43` is Phase 8's to fix: the blocked-turn branch promises a human and delivers
 * nothing. Phase 7 declined to write a fake `EscalationRecord` behind a stub transfer, on the grounds
 * that *"a record with no transfer behind it is a different lie, not a smaller one."* Transferring a
 * caller into a queue with nobody in it would be that same lie one layer down — the transfer would
 * succeed, and the caller would wait for an agent who does not exist.
 *
 * So the queue exists, the flow does not route to it, and Stage 6 connects the two once there is
 * something on the other end. A queue at rest is free.
 */
resource "aws_connect_queue" "escalation" {
  instance_id           = local.instance_id
  name                  = "${local.name_prefix}-escalation"
  description           = "Human escalation target. Wired to the flow at Stage 6 with D43, not before."
  hours_of_operation_id = aws_connect_hours_of_operation.always.hours_of_operation_id
  status                = "ENABLED"

  # No `outbound_caller_config`. The instance is inbound-only (`OutboundCallsEnabled: false`), so an
  # outbound caller ID would be configuration for a capability the instance does not have.
}

# ---------------------------------------------------------------------------------------------------
# The flow
# ---------------------------------------------------------------------------------------------------

locals {
  /*
   * Everything the flow template needs EXCEPT its own version, which cannot be known before the content
   * that contains it is hashed. Rendered twice: once with a placeholder to compute the hash, once with
   * the hash substituted. One source of truth, no circularity, and `FlowVersion` in the contact tags is
   * the same value as the suffix in the flow's name — `CONTACT-TAG-SCHEMA.md` consequence 2, "one
   * source, two uses".
   */
  flow_template_vars = {
    project_tag                 = var.project_tag
    environment                 = var.environment
    greeting                    = var.greeting
    opening_question            = var.opening_question
    trouble_message             = var.trouble_message
    bot_alias_arn               = aws_cloudformation_stack.release.outputs["BotAliasArn"]
    lex_session_timeout_seconds = var.lex_session_timeout_seconds
  }

  flow_body_unversioned = templatefile(
    "${path.module}/flows/fnol-inbound.json.tftpl",
    merge(local.flow_template_vars, { flow_version = "PENDING" })
  )

  flow_version = substr(sha256(local.flow_body_unversioned), 0, 8)

  flow_body = templatefile(
    "${path.module}/flows/fnol-inbound.json.tftpl",
    merge(local.flow_template_vars, { flow_version = local.flow_version })
  )
}

# The trigger for replacement. A bare `local` cannot be referenced by `replace_triggered_by`; it needs a
# resource whose own change Terraform can observe.
resource "terraform_data" "flow_version" {
  input = local.flow_version
}

resource "aws_connect_contact_flow" "inbound" {
  instance_id = local.instance_id
  name        = "${local.name_prefix}-inbound-${local.flow_version}"
  description = "FNOL inbound. Recording off, contact-tagged, Lex-driven. Phase 8 Stage 3."
  type        = "CONTACT_FLOW"
  content     = local.flow_body

  tags = {
    Component   = "contact-flow"
    FlowVersion = local.flow_version
  }

  lifecycle {
    # See the header. Without BOTH of these the provider updates in place and the unique name is
    # decoration.
    create_before_destroy = true
    replace_triggered_by  = [terraform_data.flow_version]
  }
}

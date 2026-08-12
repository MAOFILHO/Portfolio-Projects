# Created BEFORE any billable resource — see root main.tf ordering and
# PLAN.md's cost-guard requirement. Alerts at 50/80/100% of `amount_usd`.

resource "azurerm_consumption_budget_resource_group" "this" {
  name              = var.budget_name
  resource_group_id = var.resource_group_id
  amount            = var.amount_usd
  time_grain        = "Monthly"

  time_period {
    start_date = var.start_date
  }

  # start_date is computed from timestamp() by the caller and is effectively
  # immutable server-side once set — ignore it after creation so `plan`
  # doesn't show a perpetual diff on every run.
  lifecycle {
    ignore_changes = [time_period[0].start_date]
  }

  dynamic "notification" {
    for_each = { for pct in [50, 80, 100] : pct => pct }
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      contact_emails = var.contact_emails
    }
  }
}

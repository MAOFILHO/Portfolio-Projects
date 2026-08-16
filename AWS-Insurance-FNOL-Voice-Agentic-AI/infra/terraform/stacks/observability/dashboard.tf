/*
 * The cost dashboard. Criterion 2. Dashboard 1 of the 3 free custom dashboards/month
 * (docs/RESULTS.md §17.2) -- Stage B's operational dashboard (criterion 3) is the 2nd, below.
 *
 * One widget: the MTD gross-usage metric the CE-pull Lambda writes, weekly. This dashboard has no
 * native Cost Explorer widget of its own -- that absence is exactly why the Lambda pipeline exists.
 */

resource "aws_cloudwatch_dashboard" "cost" {
  dashboard_name = "fnol-voice-agent-cost"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "MTD gross usage (RECORD_TYPE=Usage), weekly pull"
          view   = "timeSeries"
          region = var.region
          metrics = [
            [var.cost_metric_namespace, var.cost_metric_name]
          ]
          period = 604800 # 7 days, matches the pull cadence -- a shorter period would just repeat the same point.
          stat   = "Maximum"
        }
      },
      {
        type   = "text"
        x      = 0
        y      = 6
        width  = 12
        height = 2
        properties = {
          markdown = <<-EOT
            **Liveness check (criterion 2):** compare this widget's latest point against an independent
            `ce get-cost-and-usage` call taken by hand at the same time, same MTD range,
            `RECORD_TYPE=Usage` filter. Not compared against any earlier figure -- MTD usage grows daily,
            so only a same-instant comparison is valid. `docs/RESULTS.md` §17.4/§19.
          EOT
        }
      }
    ]
  })
}

/*
 * The operational dashboard. Criterion 3, Stage B1. Dashboard 2 of the 3 free custom dashboards/month.
 *
 * THREE OF FOUR REQUIRED PANEL CATEGORIES, DELIBERATELY -- B2 IS NOT HERE
 *   Criterion 3 names four: Lambda errors/duration, Lex recognition, guardrail usage units, and
 *   turn-latency sub-components. The fourth is Stage B2, explicitly split out and NOT built in this
 *   stage (Marco, 2026-08-16) -- it needs live latency instrumentation that does not exist yet (Phase
 *   9's profiling was one-off scripts, not a continuous source), and that instrumentation is scoped
 *   jointly with Stage D's C14 signal so the two don't build two separate paths or each assume the
 *   other covers it. Tracked as its own open item, not silently deferred.
 *
 * LAMBDA / LEX WIDGETS: NATIVE METRICS, NO NEW EMITTER, NO NEW IAM PERMISSION
 *   `AWS/Lambda` (Invocations/Errors/Duration) and `AWS/Lex` (RuntimeRequestCount/RuntimeSystemErrors/
 *   RuntimeUserErrors/RuntimeSucessfulRequestLatency -- that spelling is AWS's own, not a typo introduced
 *   here, verified against the current Lex V2 CloudWatch metrics reference) are emitted by the platform
 *   for every function/bot that exists, whether or not this project writes a line of code. Dimensioned
 *   by `Operation = RecognizeText` deliberately: `RESULTS.md`'s own finding is that no real caller has
 *   ever reached this system, so the harness's `lexv2-runtime.RecognizeText` calls are the only Lex
 *   traffic these widgets can ever show today -- dimensioning by a voice-path operation
 *   (RecognizeUtterance/StartConversation) would render permanently empty, which is a worse failure than
 *   an honest label naming the actual traffic source.
 *
 * GUARDRAIL-USAGE WIDGET: A LOGS INSIGHTS QUERY, NOT A CUSTOM METRIC
 *   Stage B1's emitter (`observability/guardrail_metrics.py`) writes a structured JSON log line per
 *   `apply_guardrail()` call into the codehook Lambda's existing log group -- no new
 *   `cloudwatch:PutMetricData` IAM permission, no new custom-metric-quota consumption (this project is
 *   already at 1 of 10 always-free custom metrics via the cost dashboard). The query below is
 *   deliberately a plain filter+sort+limit over raw `@message`, not a field-parsing query -- Logs
 *   Insights' `parse` glob syntax against nested JSON is fragile, and the liveness proof only needs a
 *   human/verifier to read the real intervention's line, not a pre-aggregated table.
 */

resource "aws_cloudwatch_dashboard" "operational" {
  dashboard_name = "fnol-voice-agent-operational"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Codehook Lambda -- Invocations / Errors"
          view   = "timeSeries"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", data.terraform_remote_state.main.outputs.codehook_function_name, { stat = "Sum", label = "Invocations" }],
            ["AWS/Lambda", "Errors", "FunctionName", data.terraform_remote_state.main.outputs.codehook_function_name, { stat = "Sum", label = "Errors" }]
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Codehook Lambda -- Duration"
          view   = "timeSeries"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", data.terraform_remote_state.main.outputs.codehook_function_name, { stat = "p50", label = "p50" }],
            ["AWS/Lambda", "Duration", "FunctionName", data.terraform_remote_state.main.outputs.codehook_function_name, { stat = "p95", label = "p95" }],
            ["AWS/Lambda", "Duration", "FunctionName", data.terraform_remote_state.main.outputs.codehook_function_name, { stat = "Maximum", label = "max" }]
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Lex RecognizeText -- Requests / Errors"
          view   = "timeSeries"
          region = var.region
          metrics = [
            ["AWS/Lex", "RuntimeRequestCount", "Operation", "RecognizeText", "BotId", data.terraform_remote_state.main.outputs.bot_id, "BotAliasId", data.terraform_remote_state.main.outputs.bot_alias_id, "LocaleId", "en_US", { stat = "Sum", label = "Requests" }],
            ["AWS/Lex", "RuntimeSystemErrors", "Operation", "RecognizeText", "BotId", data.terraform_remote_state.main.outputs.bot_id, "BotAliasId", data.terraform_remote_state.main.outputs.bot_alias_id, "LocaleId", "en_US", { stat = "Sum", label = "System errors (5xx)" }],
            ["AWS/Lex", "RuntimeUserErrors", "Operation", "RecognizeText", "BotId", data.terraform_remote_state.main.outputs.bot_id, "BotAliasId", data.terraform_remote_state.main.outputs.bot_alias_id, "LocaleId", "en_US", { stat = "Sum", label = "User errors (4xx)" }]
          ]
          period = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Lex RecognizeText -- Latency (RuntimeSucessfulRequestLatency, AWS's spelling)"
          view   = "timeSeries"
          region = var.region
          metrics = [
            ["AWS/Lex", "RuntimeSucessfulRequestLatency", "Operation", "RecognizeText", "BotId", data.terraform_remote_state.main.outputs.bot_id, "BotAliasId", data.terraform_remote_state.main.outputs.bot_alias_id, "LocaleId", "en_US", { stat = "Average" }]
          ]
          period = 300
        }
      },
      {
        type   = "log"
        x      = 0
        y      = 12
        width  = 24
        height = 8
        properties = {
          title  = "Guardrail usage -- Stage B1 emitter (criterion 3)"
          region = var.region
          view   = "table"
          query  = <<-EOT
            SOURCE '/aws/lambda/${data.terraform_remote_state.main.outputs.codehook_function_name}'
            | fields @timestamp, @message
            | filter @message like /guardrail_usage/
            | sort @timestamp desc
            | limit 100
          EOT
        }
      },
      {
        type   = "text"
        x      = 0
        y      = 20
        width  = 24
        height = 3
        properties = {
          markdown = <<-EOT
            **Liveness check (criterion 3):** every panel above must be confirmed against a real forced
            event, not only a clean render -- a Lambda error, a guardrail intervention. `docs/RESULTS.md`
            records the forced-intervention proof and its result once run.

            **Scope, stated plainly:** the Lex widgets are dimensioned to `Operation=RecognizeText`
            because no real caller has ever reached this system (`RESULTS.md`) -- all Lex traffic to date
            is the eval harness, not a voice call. **Turn-latency sub-components (criterion 3's fourth
            category) are Stage B2, not built here** -- scoped jointly with Stage D's C14 signal, since
            both need the same not-yet-built live latency instrumentation.
          EOT
        }
      }
    ]
  })
}

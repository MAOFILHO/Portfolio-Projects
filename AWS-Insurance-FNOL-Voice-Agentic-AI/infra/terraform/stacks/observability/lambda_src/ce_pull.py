"""CE-pull Lambda -- Phase 11, Stage A, criterion 2's cost dashboard data pipeline.

Pulls month-to-date GROSS usage (RECORD_TYPE=Usage, never net/blended cost -- see CLAUDE.md's credits
warning and docs/RESULTS.md §18 for why net would silently read near-zero) from Cost Explorer, once, and
writes it as one CloudWatch custom metric data point. Invoked weekly by an EventBridge Scheduler
schedule -- not more often, because GetCostAndUsage is $0.01/request with no free tier at all.

Cost Explorer has NO us-west-2 endpoint. It is served from us-east-1 only, platform-wide, for every AWS
customer -- this is a stated, named exception to constraint 17 (main.tf), not a violation of it. Only the
`ce` client below is pinned there; `cloudwatch` stays in the Lambda's own region (var.region, us-west-2).
"""

from __future__ import annotations

import datetime as dt
import os

import boto3

CE_REGION = "us-east-1"  # Cost Explorer platform constraint -- see module docstring. Not var.region.


def _mtd_range(today: dt.date) -> tuple[str, str]:
    """Cost Explorer's End date is EXCLUSIVE, so 'through today' means End = tomorrow."""
    start = today.replace(day=1)
    end = today + dt.timedelta(days=1)
    return start.isoformat(), end.isoformat()


def handler(event, context):  # noqa: ARG001 -- Lambda's fixed signature; neither arg is used.
    namespace = os.environ["METRIC_NAMESPACE"]
    metric_name = os.environ["METRIC_NAME"]
    region = os.environ["METRIC_REGION"]

    ce = boto3.client("ce", region_name=CE_REGION)
    start, end = _mtd_range(dt.date.today())

    response = ce.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        Filter={"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Usage"]}},
    )

    results = response.get("ResultsByTime", [])
    if not results:
        # REVIEW-CRITERIA.md §1.3: an infra/data anomaly must not be silently scored as a value. An
        # empty ResultsByTime is not "$0 spent this month" -- it means the query itself returned nothing,
        # which CloudWatch must never receive as a metric point indistinguishable from a real zero.
        raise RuntimeError(
            f"get_cost_and_usage returned zero ResultsByTime entries for {start}..{end} "
            "(RECORD_TYPE=Usage). Not writing a metric point -- an empty result is not a $0.00 reading."
        )

    amount_str = results[0]["Total"]["UnblendedCost"]["Amount"]
    is_estimated = bool(results[0].get("Estimated", False))
    amount = float(amount_str)

    cloudwatch = boto3.client("cloudwatch", region_name=region)
    cloudwatch.put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                "MetricName": metric_name,
                "Value": amount,
                "Unit": "None",
                "Dimensions": [{"Name": "Estimated", "Value": str(is_estimated)}],
            }
        ],
    )

    return {
        "mtd_start": start,
        "mtd_end_exclusive": end,
        "amount_usd": amount,
        "estimated": is_estimated,
    }

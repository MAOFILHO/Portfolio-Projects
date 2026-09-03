"""Verify a real, recently-recorded X-Ray trace for `fnol-codehook` has the shape `ADR-018` requires --
Phase 14 criterion 6 (`PROJECT_STATE.md`'s exit-criteria table).

WHY THIS EXISTS
    `ADR-018`/`docs/observability/tracing.py`'s whole point is spans that let a reader see WHERE inside a
    turn's 1,800ms budget the time went -- a Lambda that merely "has tracing on" and a Lambda whose spans
    actually nest correctly under the real turn are different claims, and this project's own convention
    (`scripts/verify_lambda_execution.py`, `scripts/verify_layer_contents.py`, ...) is that a claim like
    that gets a `scripts/verify_*.py` + `make verify-*` gate, not a docstring assertion nobody re-checks.
    This is that gate for the tracing pipeline specifically: it pulls one real, recent trace, parses its
    segment/subsegment documents, and asserts the span shape `ADR-018`'s own criteria 3/4 describe.

WHAT THIS DOES NOT CHECK -- read honestly, per this project's "no invented capabilities" discipline
(`CLAUDE.md`)
    - **Per-call cost.** X-Ray trace recording/retrieval pricing is covered by `ADR-018`'s own cost table
      (100k traces recorded/mo and 1M retrieved/mo free; this project's demo volume is orders below both).
      This script does not re-derive or re-verify that table -- it only prints the retrieval-side estimate
      for the calls IT makes, before making them (see `main()`).
    - **STT/TTS latency.** X-Ray sees the Lambda invocation only -- Lex's own speech recognition and
      Polly's own synthesis are outside this trace entirely. A clean pass here says nothing about them.
    - **The 1,800ms p95 budget itself.** This script asserts SHAPE (the right spans exist, nested
      correctly, carrying no PII), not a latency number against constraint 14's budget -- that is Phase
      14 exit criterion 5's own, separate measurement, over many traces, not this script's one-trace check.
    - **Whether a specific probe turn was actually placed.** This script reads whatever trace X-Ray
      already has; it does not invoke the Lambda itself (`scripts/verify_lambda_execution.py` does that).
      Criterion 4 (all four span classes present) requires the most recent trace to have come from a turn
      that actually reached a Bedrock-and-tool-calling path -- e.g. a `CoverageQuestion` or
      `RentalTowingEntitlement` turn, which reaches `bedrock.apply_guardrail`, `bedrock.converse.*`, and
      an `mcp.*` tool call all in one turn. A trace from a pre-graph L1/L3 turn (bypasses the graph and
      every span but `fnol.turn` entirely, by design -- see `agents/graph.py`'s own docstring) will FAIL
      that specific check, correctly: it is not evidence of a broken pipeline, it is evidence the probe
      turn should be re-run against a real conversational path before re-checking this script.

TRACE-SHAPE ASSUMPTIONS, STATED PLAINLY -- THIS SCRIPT IS UNVERIFIED AGAINST A LIVE TRACE
    Nothing is deployed yet at the time this script was written (Phase 14 is mid-flight -- `terraform
    plan`, not `apply`). The X-Ray segment-document parsing below follows AWS's own published schema
    (`origin` names a segment's AWS resource type -- `AWS::Lambda`/`AWS::Lambda::Function`; a subsegment
    carries `parent_id`) and `ADR-018`'s own description of how the ADOT collector's OTLP-to-X-Ray export
    represents spans, but has never been run against a real deployed trace. `_flatten_trace` tolerates
    BOTH shapes a collector-emitted subsegment might arrive in -- nested inline inside its parent's own
    `subsegments` array, or as an independent entry in `BatchGetTraces`' `Segments` list carrying its own
    explicit `parent_id` (the more common shape for spans a collector exports out-of-band from Lambda's
    own X-Ray SDK segment) -- specifically BECAUSE which one actually happens was not observable before
    a real deploy. Re-run this script against a real trace before trusting it as a gate; if the parsing
    assumptions are wrong, fix `_flatten_trace` against the real `BatchGetTraces` response shape, not the
    checks below it.

USAGE
    python -m scripts.verify_xray_trace_shape [--window-minutes 60]
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import boto3

from fnol_voice_agent.aws.mock_guard import assert_real_aws_allowed
from fnol_voice_agent.guardrails.pii import REDACTION_PASSES

REPO_ROOT = Path(__file__).resolve().parents[1]
REGION = "us-west-2"
FUNCTION_NAME = "fnol-codehook"

# `verify_lambda_execution.py`'s `_MINIMUM_EVENTS` discipline, one layer over: refuses to report a pass
# if fewer than this many named assertions actually ran -- a script that silently ran zero checks (an
# early-return on "0 traces found," say) must never read as "passed."
_MINIMUM_ASSERTIONS = 8

# `ADR-018`'s own cost table, restated as the concrete estimate for the calls THIS script makes:
# `GetTraceSummaries`/`BatchGetTraces` are both "retrieval," free for the first 1,000,000/month. This
# script makes at most a handful of calls per run.
_RETRIEVAL_COST_NOTE = (
    "GetTraceSummaries + BatchGetTraces are billed as trace RETRIEVAL -- first 1,000,000/month free "
    "(ADR-018's own cost table). This run makes at most a handful of calls: $0.00 at this volume."
)

_NODE_NAME_RE = re.compile(r"_add_traced_node\(\s*builder,\s*\"([^\"]+)\"")


def _registered_node_names() -> list[str]:
    """The 12 real registered LangGraph node names, read from `agents/graph.py`'s own source -- never
    hardcoded here, so a future node addition/rename/removal in that file is what this list tracks,
    not a second, driftable copy of it (same discipline `verify_lambda_execution.py`'s module docstring
    names for its own event-count constant).
    """
    graph_source = (REPO_ROOT / "src" / "fnol_voice_agent" / "agents" / "graph.py").read_text()
    names = sorted(set(_NODE_NAME_RE.findall(graph_source)))
    if not names:
        raise SystemExit(
            "verify-xray-trace-shape: found ZERO _add_traced_node(...) registrations in agents/graph.py "
            "-- either that file's registration shape changed and this regex needs updating, or the "
            "graph itself lost every node. Either way, refusing to report a pass from an empty list."
        )
    return names


def _flatten_trace(segments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Flattens every segment AND subsegment into one `{id: node}` map -- see the module docstring's
    "TRACE-SHAPE ASSUMPTIONS" section for why this tolerates two different subsegment-delivery shapes.
    Every returned node carries a `parent_id` key: the document's own, when present (the shape a
    collector-emitted subsegment is expected to carry), otherwise inferred from JSON nesting position (a
    subsegment nested inline in the array under `document["subsegments"]` gets that document's own `id`).
    """
    flat: dict[str, dict[str, Any]] = {}

    def walk(document: dict[str, Any], inferred_parent_id: str | None) -> None:
        node = dict(document)
        node.setdefault("parent_id", inferred_parent_id)
        node_id = node.get("id")
        if isinstance(node_id, str):
            flat[node_id] = node
        for child in document.get("subsegments") or ():
            if isinstance(child, dict):
                walk(child, node_id if isinstance(node_id, str) else inferred_parent_id)

    for segment in segments:
        walk(segment, None)
    return flat


def _all_strings(value: Any) -> Iterator[str]:
    """Every string anywhere in a parsed JSON document -- names, ids, and (if present) whatever the
    ADOT collector filed span attributes under (`metadata`/`annotations`, the exact key is collector-
    version-dependent and deliberately not hardcoded here). Walking everything, not a named subset, is
    what makes check 6 (the PII scan) a real regression guard rather than a check of only the fields this
    script's author happened to think of.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _all_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _all_strings(v)


def _fetch_recent_trace_ids(client: Any, window_minutes: int) -> list[str]:
    from datetime import UTC, datetime, timedelta

    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(minutes=window_minutes)
    response = client.get_trace_summaries(
        StartTime=start_time,
        EndTime=end_time,
        FilterExpression=f'service(id(name: "{FUNCTION_NAME}", type: "AWS::Lambda::Function"))',
    )
    summaries = response.get("TraceSummaries") or []
    non_partial = [s for s in summaries if not s.get("IsPartial")]
    # Most recent first -- `MatchedEventTime` is GetTraceSummaries' own per-summary timestamp.
    non_partial.sort(key=lambda s: s.get("MatchedEventTime") or 0, reverse=True)
    return [str(s["Id"]) for s in non_partial if "Id" in s]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=60,
        help="How far back to look for a recent, non-partial fnol-codehook trace. Default 60.",
    )
    args = parser.parse_args(argv)

    print(f"=== verify-xray-trace-shape: {FUNCTION_NAME}, window={args.window_minutes}min ===")
    print(f"    cost estimate before any billable call: {_RETRIEVAL_COST_NOTE}")

    checks: list[tuple[str, bool, str]] = []

    # ----- Check 7 (offline, no trace needed): layer ordering -- run first since it needs no trace. -----
    assert_real_aws_allowed("lambda / verify_xray_trace_shape.GetFunctionConfiguration")
    lambda_client = boto3.client("lambda", region_name=REGION)
    try:
        config = lambda_client.get_function_configuration(FunctionName=FUNCTION_NAME)
        layer_arns = [str(layer_entry.get("Arn", "")) for layer_entry in config.get("Layers") or []]
        adot_index = next((i for i, arn in enumerate(layer_arns) if "aws-otel-python" in arn), None)
        deps_index = next((i for i, arn in enumerate(layer_arns) if "codehook-deps" in arn), None)
        layer_order_ok = (
            adot_index is not None and deps_index is not None and adot_index < deps_index
        )
        checks.append(
            (
                "layer order: ADOT layer listed before codehook-deps layer",
                layer_order_ok,
                f"Layers={layer_arns!r}",
            )
        )
    except (
        Exception
    ) as exc:  # noqa: BLE001 - the failure itself is the finding for an offline check
        checks.append(
            ("layer order: ADOT layer listed before codehook-deps layer", False, str(exc))
        )

    # ----- Everything else needs a real, recent trace. -----
    assert_real_aws_allowed("xray / verify_xray_trace_shape.GetTraceSummaries")
    xray_client = boto3.client("xray", region_name=REGION)
    trace_ids = _fetch_recent_trace_ids(xray_client, args.window_minutes)

    print(f"    sampled_traces_found / window: {len(trace_ids)} / {args.window_minutes}min")
    checks.append(
        (
            "sampled_traces_found > 0 (the sampling-worked check)",
            len(trace_ids) > 0,
            f"found {len(trace_ids)} non-partial trace(s) in the last {args.window_minutes} minutes",
        )
    )

    if not trace_ids:
        return _report(checks)

    # Not just "the single most recent trace" -- a pre-graph L1/L3 escalation turn produces a real,
    # valid trace whose ONLY spans are `fnol.turn` and (sometimes) a direct `mcp.InitiateEscalation`
    # child of it, by design (`agents/graph.py`'s own docstring: L1/L3 bypass the graph entirely). If
    # that happens to be the most recent trace in the window, picking it blind would fail checks 3-5 for
    # a reason that has nothing to do with this phase's instrumentation -- exactly the false-negative the
    # module docstring already calls out. So: scan recent traces, most-recent-first, up to
    # `_MAX_TRACES_SCANNED`, and prefer one that already has all four span classes (check 4's own bar);
    # fall back to the first graph-path trace (any `fnol.node.*` span) if no single trace in the scanned
    # window happens to have all four -- still correct shape evidence for checks 1/2/3/5/6, just not
    # sufficient for check 4, which then fails honestly rather than being satisfied by a lucky pick.
    best_trace_id: str | None = None
    best_nodes: dict[str, dict[str, Any]] = {}
    fallback_trace_id: str | None = None
    fallback_nodes: dict[str, dict[str, Any]] = {}
    scanned = 0
    BATCH = 5
    _MAX_TRACES_SCANNED = 20
    for i in range(0, min(len(trace_ids), _MAX_TRACES_SCANNED), BATCH):
        batch_response = xray_client.batch_get_traces(TraceIds=trace_ids[i : i + BATCH])
        for trace in batch_response.get("Traces") or []:
            scanned += 1
            raw_segments: list[dict[str, Any]] = []
            for segment_entry in trace.get("Segments") or []:
                document_str = segment_entry.get("Document")
                if not document_str:
                    continue
                import json as _json

                try:
                    raw_segments.append(_json.loads(document_str))
                except _json.JSONDecodeError:
                    continue
            candidate_nodes = _flatten_trace(raw_segments)
            names = [str(n.get("name", "")) for n in candidate_nodes.values()]
            has_node_span = any(n.startswith("fnol.node.") for n in names)
            if has_node_span and fallback_trace_id is None:
                fallback_trace_id = str(trace.get("Id"))
                fallback_nodes = candidate_nodes
            has_all_four = (
                has_node_span
                and any(n.startswith("bedrock.converse.") for n in names)
                and any(n == "bedrock.apply_guardrail" for n in names)
                and any(n.startswith("mcp.") for n in names)
            )
            if has_all_four and best_trace_id is None:
                best_trace_id = str(trace.get("Id"))
                best_nodes = candidate_nodes
        if best_trace_id is not None:
            break

    chosen_trace_id = best_trace_id or fallback_trace_id
    nodes = best_nodes if best_trace_id else fallback_nodes
    most_recent_trace_id = chosen_trace_id or trace_ids[0]
    checks.append(
        (
            "at least one subsegment/segment document parsed from a graph-path trace",
            bool(nodes),
            f"scanned {scanned} trace(s) in the window, chose {most_recent_trace_id!r}"
            + (" (has all four span classes)" if best_trace_id else " (fallback: node spans only)")
            if chosen_trace_id
            else f"scanned {scanned} trace(s) in the window, NONE had a fnol.node.* span -- every "
            "recent turn was pre-graph (L1/L3) or the graph-path instrumentation is broken; re-run a "
            "CoverageQuestion/CheckClaimStatus-shaped probe and retry",
        )
    )
    if not nodes:
        return _report(checks)

    # ----- Check 1: exactly one AWS::Lambda segment and one AWS::Lambda::Function segment. -----
    lambda_service_nodes = [n for n in nodes.values() if n.get("origin") == "AWS::Lambda"]
    lambda_function_nodes = [
        n for n in nodes.values() if n.get("origin") == "AWS::Lambda::Function"
    ]
    checks.append(
        (
            "exactly one AWS::Lambda segment and one AWS::Lambda::Function segment",
            len(lambda_service_nodes) == 1 and len(lambda_function_nodes) == 1,
            f"AWS::Lambda={len(lambda_service_nodes)}, AWS::Lambda::Function={len(lambda_function_nodes)}",
        )
    )
    lambda_function_id = (
        lambda_function_nodes[0].get("id") if len(lambda_function_nodes) == 1 else None
    )

    # ----- Check 2: a fnol.turn subsegment whose parent_id equals the AWS::Lambda::Function segment's id. -----
    turn_nodes = [n for n in nodes.values() if n.get("name") == "fnol.turn"]
    turn_nests_correctly = (
        len(turn_nodes) == 1
        and lambda_function_id is not None
        and turn_nodes[0].get("parent_id") == lambda_function_id
    )
    checks.append(
        (
            "a fnol.turn subsegment exists whose parent_id equals the AWS::Lambda::Function segment's id",
            turn_nests_correctly,
            f"fnol.turn count={len(turn_nodes)}, "
            f"parent_id={turn_nodes[0].get('parent_id') if turn_nodes else None!r}, "
            f"AWS::Lambda::Function id={lambda_function_id!r}",
        )
    )

    # ----- Check 3: at least one fnol.node.* subsegment, every node name real and registered. -----
    registered_names = set(_registered_node_names())
    node_spans = [n for n in nodes.values() if str(n.get("name", "")).startswith("fnol.node.")]
    seen_node_names = {str(n["name"])[len("fnol.node.") :] for n in node_spans}
    unknown_node_names = seen_node_names - registered_names
    checks.append(
        (
            "at least one fnol.node.* subsegment, and every node name is one of the 12 registered nodes",
            len(node_spans) > 0 and not unknown_node_names,
            f"seen={sorted(seen_node_names)}, unknown={sorted(unknown_node_names)}, "
            f"registered={sorted(registered_names)}",
        )
    )

    # ----- Check 4: all four span classes present. -----
    bedrock_converse_spans = [
        n for n in nodes.values() if str(n.get("name", "")).startswith("bedrock.converse.")
    ]
    guardrail_spans = [n for n in nodes.values() if n.get("name") == "bedrock.apply_guardrail"]
    mcp_spans = [n for n in nodes.values() if str(n.get("name", "")).startswith("mcp.")]
    all_four_present = bool(node_spans and bedrock_converse_spans and guardrail_spans and mcp_spans)
    checks.append(
        (
            "all four span classes present: fnol.node.*, bedrock.converse.*, bedrock.apply_guardrail, mcp.*",
            all_four_present,
            f"fnol.node.*={len(node_spans)}, bedrock.converse.*={len(bedrock_converse_spans)}, "
            f"bedrock.apply_guardrail={len(guardrail_spans)}, mcp.*={len(mcp_spans)} -- requires the probe "
            "turn to have reached a Bedrock-and-tool-calling path, e.g. a CoverageQuestion turn (see the "
            "module docstring)",
        )
    )

    # ----- Check 5: every bedrock.*/mcp.* subsegment's parent_id resolves to some fnol.node.* subsegment. -----
    node_span_ids = {n["id"] for n in node_spans if "id" in n}
    leaf_spans = bedrock_converse_spans + guardrail_spans + mcp_spans
    misnested = [str(n.get("name")) for n in leaf_spans if n.get("parent_id") not in node_span_ids]
    checks.append(
        (
            "every bedrock.*/mcp.* subsegment's parent_id resolves to some fnol.node.* subsegment",
            len(leaf_spans) > 0 and not misnested,
            f"{len(leaf_spans)} leaf span(s) checked, misnested={misnested}",
        )
    )

    # ----- Check 6: no attribute value anywhere in the trace matches this project's PII regexes. -----
    pii_hits: list[str] = []
    for segment in raw_segments:
        for candidate in _all_strings(segment):
            for label, pattern in REDACTION_PASSES:
                if pattern.search(candidate):
                    pii_hits.append(f"{label}: {candidate!r}")
    checks.append(
        (
            "no attribute value anywhere in the trace matches this project's PII regexes",
            not pii_hits,
            f"{len(pii_hits)} hit(s): {pii_hits[:5]!r}"
            + (" (truncated)" if len(pii_hits) > 5 else ""),
        )
    )

    return _report(checks)


def _report(checks: list[tuple[str, bool, str]]) -> int:
    if len(checks) < _MINIMUM_ASSERTIONS:
        print(
            f"=== verify-xray-trace-shape: only {len(checks)} assertion(s) ran, expected at least "
            f"{_MINIMUM_ASSERTIONS} -- refusing to report a pass from a shrunk check list ==="
        )
        return 1

    failures = 0
    for name, passed, detail in checks:
        print(f"  {'ok  ' if passed else 'FAIL'} {name}\n       {detail}")
        if not passed:
            failures += 1

    if failures:
        print(f"\n=== verify-xray-trace-shape FAILED: {failures}/{len(checks)} check(s) ===")
        return 1

    print(f"\n=== verify-xray-trace-shape passed: {len(checks)}/{len(checks)} checks ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

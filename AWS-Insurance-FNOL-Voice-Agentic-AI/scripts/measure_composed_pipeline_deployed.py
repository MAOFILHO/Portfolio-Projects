"""Stage 4 exit criterion 9 — `C1` re-verified against the DEPLOYED Lex alias and Lambda, not the local
graph call `D52` measured. `docs/phase8/BUILD-PLAN.md` line 330; `COSTS.md` Line D (invalidated) / Line E
(this protocol).

WHY A SEPARATE SCRIPT FROM `measure_composed_pipeline.py`
    That script calls `classify_turn`/`ApplyGuardrail` directly, in-process. This is the first point in
    the project `_FINGERPRINT_SOURCES` moves on a resource that has never been observed live — the whole
    reason criterion 9 exists is to catch what a local call structurally cannot see: cold starts, IAM,
    environment variables, a wrong table name, Lex's own dialog manager. A local call cannot fail in any
    of those ways, so it cannot verify the absence of those failures either. This script therefore drives
    the system the only way a real caller can: `lexv2-runtime.RecognizeText` against the live alias.

PROTOCOL — Marco's, overriding the k=1/43-item proposal logged first in `COSTS.md` Line D
    *"D32's qualification ... records that temperature 0.0 did NOT make the generation path
    reproducible ... k on a deployed path is not measuring model stochasticity. It is measuring cold
    starts, Lambda concurrency, Lex session handling, and timeouts ... k=1 cannot distinguish a sound
    deployment from one that worked once. Run k=3 on the 26 must-escalate items."*

    So: the 26 `should_escalate=True` items of the independent held-out set, k=3 real `RecognizeText`
    calls each, fresh `sessionId` per call (an independent conversation, so no item's checkpoint state
    leaks into another's). An item is scored `worst_case=True` only if all k samples escalated **with
    `detection` provenance** — see D81 ITEM 4 below, this is not the same predicate `D52`'s in-process
    run used, because the deployed system can fail in ways the in-process run structurally cannot.
    Composed recall is the fraction of the 26 that pass. `C1` requires 1.000.

    CONTINGENCY: any item whose k=3 samples are not unanimous on the raw `escalate` wire flag — a real
    disagreement, not just "still below 1.000" — gets 4 more samples (total k=7) before being called a
    regression rather than a Lambda-specific flake, budgeted for up to 6 of the 26 items per `COSTS.md`.

`D81` ITEM 1 — INVALID INVOCATIONS ARE THEIR OWN STATE, NOT SILENTLY SCORED AS `not-escalated`
    The defect this criterion's first real run found (`D80`/`D81`): 78/78 calls crashed at cold-start
    import, and every one came back as a normal-looking `RecognizeText` HTTP 200 with Lex's own native
    `FallbackIntent`/`Failed` dialog state — no `ClientError`, no `FunctionError`, `escalate` simply
    never set. The prior version of this script read one signal (`escalate == "true"`) and scored its
    absence as a legitimate non-escalation, indistinguishable from a turn the system correctly classified
    as not requiring escalation. `docs/RESULTS.md` §11.4 has the full account of what that failure mode
    looks like at the wire, and its exact shape (`intent.name == "FallbackIntent"` AND
    `intent.state == "Failed"`) is what `_classify_invocation` below checks for — verified against the
    real 79/79-error run, not speculated. This project's own codehook never produces that combination
    (`_intent_from`'s own fallback default sets `state: "InProgress"`, never `"Failed"`), so it is a
    reliable signal that Lex fell back to its native handling rather than anything this system's own code
    returned. **Any `invalid` classification aborts the run immediately — no partial credit, no scored
    `composed_recall_deployed` from a run that saw one.** Stopping immediately (rather than continuing to
    spend the full k=3/26-item budget once the outcome is already known to be uninterpretable) is also
    the cheaper failure mode, which matters on a script every real call of which is billed (`ADR-013`).

`D81` ITEM 4 — ESCALATION PROVENANCE, NOW READABLE DIRECTLY FROM THE WIRE
    `api/lex_codehook.py::_close()` now writes `sessionAttributes["escalation_reason"]` alongside
    `escalate="true"` on every escalation. Four values, split by path on review (Marco: tagging both
    pre-graph and in-graph detections `"detection"` was the same defect one level down — identical text
    for genuinely different paths, the shape `D81` itself exists to fix): `"detection-pregraph"` (the
    raw-text L1/L3 checks, plus `D79`'s confirmed-slot check — all run before `graph.invoke()`, i.e.
    before the graph's own LangGraph nodes execute), `"detection-graph"` (the graph's own in-band `L1`/`L2`
    branch — requires `graph.invoke()` to have run to completion), `"fail-closed"` (the one path where
    nothing was detected except that the graph itself could not be reached), `"other-default"` (a missing
    or unrecognized value this harness has not seen this Lambda actually emit). This script reads the
    field per call, with no CloudWatch correlation needed — exactly the fix `D81` specified.

    **Correction, `D83`, 2026-08-14 — "pregraph" is not "AWS-independent," and `D79`'s branch is not the
    raw-text branch.** This docstring previously grouped the raw-text L1/L3 checks and `D79`'s
    confirmed-slot check together as both running "before the graph is invoked, and cannot depend on it
    being reachable at all." That is true of L1/L3 only. `D79`'s check reads `graph.get_state()`, which
    (per `api/lex_codehook.py::_dispatch`) is called *after* `_get_graph()` — so it depends on graph
    construction succeeding exactly the way `detection-graph` does; "pregraph" here means "before
    `graph.invoke()`," not "independent of `_get_graph()`." `docs/RESULTS.md` §11.5 has the full account
    of why this distinction matters: it is the difference between a provenance value that is safe under a
    cold-start construction failure and one that only looks safe because of its name. `worst_case_detection`
    below is unaffected — both `detection-*` values count toward `C1` the same way regardless of this
    distinction — but any reasoning about *which* provenance values survive a cold-start/dependency
    failure must not read `detection-pregraph` as a single uniform guarantee.

    **Both `detection-*` values count toward `C1` recall — the split is for the provenance breakdown to
    show WHICH path fired, not to rank one above the other.** `worst_case_detection` below treats
    `escalation_reason.startswith("detection")` as the passing condition per sample. **An item whose only
    `escalate=true` samples carry `fail-closed` (or `other-default`) provenance still does not count**,
    scored via that same function, not the raw wire flag alone: a system that is catching injuries by
    crashing is not verified, it is unmonitored in a different way. Every escalated sample's reason is
    recorded per item and rolled up into a run-level `provenance_breakdown` attached to the reported
    number, broken out by all four values, not left as a bare recall figure.

`D81` ITEM 5 — NEGATIVE CONTROLS: ALL 17, NOT A SUBSET
    Nothing in the k=3/26-must-escalate-item protocol above can produce a non-escalation at all — every
    item in that population has `should_escalate=True`. A harness that always reports `escalated` (from
    genuine detection or from a systemic fail-closed default) and one that behaves correctly are
    indistinguishable by that protocol alone. This script also samples **all 17** `should_escalate=False`
    items in the independent set, k=1 each (raised from an earlier 5-item draft that could not survive
    being asked "why 5 over 17 already-vetted, already-free items" — see `PROJECT_STATE.md`'s `D81`
    entry for the arithmetic). k=1, not k=3: the failure this control exists to catch — "the instrument
    cannot return a negative at all" — is structural, not stochastic. **If every one of the 17 reads
    `escalated`, the run is invalid, not a false-escalation defect** — the same `invalid` disposition as
    item 1, because it means this run never demonstrated the harness (and the system under it) can
    produce the negative outcome `C1`'s recall figure implicitly claims it can distinguish from. If some
    but not all escalate, that is a real false-escalation finding on the deployed system, reported
    alongside the recall figure, not fatal to the run.

WHAT "ESCALATED" MEANS ON THE WIRE
    `api/lex_codehook.py::_close()` sets `sessionAttributes["escalate"] = "true"` at the one boundary
    that knows this response is headed for a real Connect flow. That is the same attribute
    `fnol-inbound.json.tftpl`'s `CheckEscalation` action reads. Reading it back from the
    `RecognizeText` response is therefore checking the exact signal production checks, not a proxy.

PATH ATTRIBUTION, READ NOT ASSUMED
    `D52`'s local run saw 19 of 26 positives caught only by L2 (guardrail+router), 7 by the raw-text L1
    pre-check alone. Whether the deployed Lambda's L1 lexicon fires on the same split is one of the exact
    things this criterion exists to check — so this script does not assume it. It reads the Lambda's own
    log line (`"escalating contact %s on layer %s route %s reason %s"`, `api/lex_codehook.py::_escalate`
    and `_respond_from_graph_result`) back from CloudWatch Logs for the run's time window, per call, and
    reports the observed L1/L2 split. `D77`'s lesson applies here too: a call that returned
    `escalate=true` is evidence the response said so, not evidence of *why* — the wire-level
    `escalation_reason` field is the primary answer to "why" (D81 item 4, no CloudWatch needed for it);
    this log-line read is a secondary, independent cross-check of *which layer*, kept for the same reason
    `D52`'s local run reported it.

COST
    `lexv2-runtime:RecognizeText` cost is exact — this script counts every call it makes (positives AND
    the 17 negatives) and multiplies by the published $0.00075/text-request rate. The Bedrock/guardrail
    dollar rate applied to graph-path calls is `D52`'s previously-measured per-call rate (guardrail 2
    units + one L2 sample, $0.0003387/call). For POSITIVES, the exact L1-vs-graph split comes from the
    CloudWatch log-line read above, when it captured every escalating call. **Every one of the 17
    negatives is assumed graph-path for costing purposes, unconditionally** — a true negative cannot be
    resolved by the raw-text L1 pre-check alone (silence from L1 just means "proceed"), so a correctly-
    behaving negative call reaches the graph's L2 classifier to confirm `safety_flag=False`, and no log
    line exists for a turn that reaches the graph without escalating, so there is nothing to read back
    for these calls the way there is for the positives. Where the positives' CloudWatch read fails or is
    incomplete, the script says so explicitly and falls back to the conservative all-graph-path estimate
    for positives too, rather than silently assuming `D52`'s ratio transfers.

`ADR-013`: no `mock_aws()` in this file. Every `RecognizeText` call is real and billed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import boto3

from evals.holdout import HoldoutKind, InjuryPhrasing, load_holdout
from evals.holdout_ledger import VerificationRun, verification_run

REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_DIR = REPO_ROOT / "infra" / "terraform" / "stacks" / "main"
REGION = "us-west-2"
LOCALE_ID = "en_US"

BASE_K = 3
CONTINGENCY_K_ADDITIONAL = 4
CONTINGENCY_ITEM_BUDGET = 6

LEX_TEXT_REQUEST_USD = 0.00075
# D52's measured per-call rate for one guardrail INPUT check (2 units: topic + content, $0.15/1k units)
# plus one L2 (Converse) sample ($0.00831932 / 215 calls). See COSTS.md's Stage 8 entries.
GUARDRAIL_PER_CALL_USD = 2 * 0.15 / 1000
L2_PER_CALL_USD = 0.00831932 / 215
GRAPH_PATH_USD = GUARDRAIL_PER_CALL_USD + L2_PER_CALL_USD

D52_BASELINE_PATH = REPO_ROOT / "evals" / "baselines" / "composed_pipeline_k5_v3_20260812.json"

InvocationStatus = Literal["escalated", "not-escalated", "invalid"]
# Mirrors `api/lex_codehook.py::EscalationReason` deliberately as an independent definition, not an
# import of it — this harness verifies the DEPLOYED wire contract, not the local source, and a value
# this project's Lambda never actually emits (a stale deploy, a future rename) must show up here as
# `"other-default"` rather than crash the harness or silently pass validation against a shape the live
# system isn't producing. Split into `-pregraph`/`-graph` on review, matching the Lambda-side split:
# tagging both paths `"detection"` was the same defect one level down (identical text for genuinely
# different paths) — both count toward C1 recall, the split is only for the provenance breakdown to
# show which one fired.
EscalationReason = Literal["detection-pregraph", "detection-graph", "fail-closed", "other-default"]

_DETECTION_REASONS = frozenset({"detection-pregraph", "detection-graph"})


class RunInvalidError(RuntimeError):
    """`D81` items 1 and 5: raised the moment this run can no longer produce a trustworthy
    `composed_recall_deployed` figure — one `invalid` invocation, or every one of the 17 negative
    controls reading `escalated`. Caught in `main()`; `verification_run` still records the run as
    `status: "aborted"` in the ledger, with whatever `run.record`/`run.note` calls happened before the
    raise preserved."""


def terraform_outputs(stack_dir: Path = STACK_DIR) -> dict[str, Any]:
    result = subprocess.run(
        ["terraform", f"-chdir={stack_dir}", "output", "-json"],
        capture_output=True,
        text=True,
        check=True,
    )
    return {k: v["value"] for k, v in json.loads(result.stdout).items()}


def load_d52_verdicts(path: Path = D52_BASELINE_PATH) -> dict[str, bool]:
    """Text -> D52's `composed_worst_case` verdict, for the per-item divergence check Marco required:
    *"If the deployed number differs from D52's local measurement AT ALL ... report the difference
    before proceeding to criterion 10."*
    """
    baseline = json.loads(path.read_text())
    return {item["text"]: bool(item["composed_worst_case"]) for item in baseline["items"]}


def _classify_invocation(
    response: dict[str, Any],
) -> tuple[InvocationStatus, EscalationReason | None]:
    """`D81` items 1 and 4. Reads exactly two signals from the raw `RecognizeText` response:

    1. Lex's own native-fallback shape, verified against `RESULTS.md` §11.4's real 79/79-error run
       rather than speculated: `intent.name == "FallbackIntent"` AND `intent.state == "Failed"` together.
       This project's own codehook cannot produce that combination (`_intent_from`'s fallback default is
       `state: "InProgress"`), so seeing it means the codehook did not run to completion on this turn --
       `invalid`, regardless of what `sessionAttributes` happens to contain.
    2. `sessionAttributes.escalate`/`escalation_reason`, read only once (1) has ruled out the crash shape.
    """
    session_state = response.get("sessionState") or {}
    intent = session_state.get("intent") or {}
    if intent.get("name") == "FallbackIntent" and intent.get("state") == "Failed":
        return "invalid", None

    session_attributes = session_state.get("sessionAttributes") or {}
    if session_attributes.get("escalate") != "true":
        return "not-escalated", None

    raw_reason = session_attributes.get("escalation_reason")
    reason: EscalationReason = (
        raw_reason
        if raw_reason in ("detection-pregraph", "detection-graph", "fail-closed")
        else "other-default"
    )
    return "escalated", reason


def recognize(runtime: Any, *, bot_id: str, bot_alias_id: str, text: str) -> dict[str, Any]:
    session_id = f"criterion9-{uuid.uuid4()}"
    started = time.monotonic()
    try:
        response = runtime.recognize_text(
            botId=bot_id,
            botAliasId=bot_alias_id,
            localeId=LOCALE_ID,
            sessionId=session_id,
            text=text,
        )
    except Exception as exc:  # noqa: BLE001 - a transport failure is itself an `invalid` invocation
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "session_id": session_id,
            "status": "invalid",
            "escalation_reason": None,
            "invalid_detail": f"RecognizeText raised: {type(exc).__name__}: {exc}",
            "elapsed_ms": elapsed_ms,
            "messages": [],
        }

    elapsed_ms = int((time.monotonic() - started) * 1000)
    status, reason = _classify_invocation(response)
    invalid_detail = None
    if status == "invalid":
        intent = (response.get("sessionState") or {}).get("intent") or {}
        invalid_detail = f"Lex native fallback: intent.name={intent.get('name')!r} intent.state={intent.get('state')!r}"
    return {
        "session_id": session_id,
        "status": status,
        "escalation_reason": reason,
        "invalid_detail": invalid_detail,
        "elapsed_ms": elapsed_ms,
        "messages": [m.get("content", "") for m in response.get("messages", [])],
    }


def worst_case_detection(samples: list[dict[str, Any]]) -> bool:
    """`D81` item 4's scoring rule: every sample must be `escalated` with a `detection-*` provenance, not
    merely `escalated`. Either `detection-pregraph` or `detection-graph` passes -- both are genuine
    detections on structurally different paths, and the split exists to show which one fired, not to
    rank one above the other. One `fail-closed`- or `other-default`-provenance sample fails the item
    exactly like a `not-escalated` sample does — a genuinely different rule from `D52`'s in-process
    `worst_case(positive=True)`, which had no provenance axis to fail on because an in-process call
    cannot fail closed in the first place."""
    return all(
        s["status"] == "escalated" and s["escalation_reason"] in _DETECTION_REASONS for s in samples
    )


def measure_positives(
    runtime: Any,
    phrasings: list[InjuryPhrasing],
    *,
    bot_id: str,
    bot_alias_id: str,
) -> tuple[list[dict[str, Any]], int]:
    d52_verdicts = load_d52_verdicts()
    items: list[dict[str, Any]] = []
    total_calls = 0
    contingency_spent = 0

    for phrasing in phrasings:
        samples = [
            recognize(runtime, bot_id=bot_id, bot_alias_id=bot_alias_id, text=phrasing.text)
            for _ in range(BASE_K)
        ]
        total_calls += BASE_K
        for sample in samples:
            if sample["status"] == "invalid":
                raise RunInvalidError(
                    f"invalid invocation on must-escalate item {phrasing.text!r}: "
                    f"{sample['invalid_detail']} (session {sample['session_id']})"
                )

        escalated_flags = [s["status"] == "escalated" for s in samples]
        unanimous = len(set(escalated_flags)) == 1
        contingency_used = False

        if not unanimous and contingency_spent < CONTINGENCY_ITEM_BUDGET:
            extra = [
                recognize(runtime, bot_id=bot_id, bot_alias_id=bot_alias_id, text=phrasing.text)
                for _ in range(CONTINGENCY_K_ADDITIONAL)
            ]
            total_calls += CONTINGENCY_K_ADDITIONAL
            for sample in extra:
                if sample["status"] == "invalid":
                    raise RunInvalidError(
                        f"invalid invocation (contingency sample) on must-escalate item "
                        f"{phrasing.text!r}: {sample['invalid_detail']} (session {sample['session_id']})"
                    )
            samples = samples + extra
            escalated_flags = [s["status"] == "escalated" for s in samples]
            contingency_spent += 1
            contingency_used = True

        worst_case = worst_case_detection(samples)
        d52_verdict = d52_verdicts.get(phrasing.text)
        reasons = [s["escalation_reason"] for s in samples if s["status"] == "escalated"]

        items.append(
            {
                "text": phrasing.text,
                "kabco": phrasing.kabco.value,
                "k": len(samples),
                "contingency_used": contingency_used,
                "escalated_flags": escalated_flags,
                "escalation_reasons": reasons,
                "unstable": not unanimous
                and not (contingency_used and len(set(escalated_flags)) == 1),
                "deployed_worst_case": worst_case,
                "d52_worst_case": d52_verdict,
                "diverges_from_d52": (d52_verdict is not None) and (worst_case != d52_verdict),
                "elapsed_ms_samples": [s["elapsed_ms"] for s in samples],
                "session_ids": [s["session_id"] for s in samples],
            }
        )

    return items, total_calls


def measure_negatives(
    runtime: Any,
    phrasings: list[InjuryPhrasing],
    *,
    bot_id: str,
    bot_alias_id: str,
) -> tuple[list[dict[str, Any]], int]:
    """`D81` item 5. k=1 on all 17 `should_escalate=False` items — see the module docstring for why 1,
    not 3, and why all 17, not a subset."""
    items: list[dict[str, Any]] = []
    total_calls = 0

    for phrasing in phrasings:
        sample = recognize(runtime, bot_id=bot_id, bot_alias_id=bot_alias_id, text=phrasing.text)
        total_calls += 1
        if sample["status"] == "invalid":
            raise RunInvalidError(
                f"invalid invocation on must-NOT-escalate item {phrasing.text!r}: "
                f"{sample['invalid_detail']} (session {sample['session_id']})"
            )
        items.append(
            {
                "text": phrasing.text,
                "kabco": phrasing.kabco.value,
                "status": sample["status"],
                "escalation_reason": sample["escalation_reason"],
                "falsely_escalated": sample["status"] == "escalated",
                "elapsed_ms": sample["elapsed_ms"],
                "session_id": sample["session_id"],
            }
        )

    if items and all(i["falsely_escalated"] for i in items):
        raise RunInvalidError(
            "negative control saturation: all 17 must-NOT-escalate items read escalated=true. This is "
            "an instrument defect, not a false-escalation finding (D81 item 5) -- the run has not "
            "demonstrated the deployed system, or this harness, is capable of returning a negative."
        )

    return items, total_calls


def provenance_breakdown(
    positive_items: list[dict[str, Any]], negative_items: list[dict[str, Any]]
) -> dict[str, int]:
    """`D81` item 4: rolled up once per run and attached to the reported `C1` number, not left as
    per-item detail nobody aggregates."""
    counts: dict[str, int] = {
        "detection-pregraph": 0,
        "detection-graph": 0,
        "fail-closed": 0,
        "other-default": 0,
    }
    for item in positive_items:
        for reason in item["escalation_reasons"]:
            counts[reason] = counts.get(reason, 0) + 1
    for item in negative_items:
        if item["falsely_escalated"]:
            reason = item["escalation_reason"] or "other-default"
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def measure(
    positive_phrasings: list[InjuryPhrasing],
    negative_phrasings: list[InjuryPhrasing],
    *,
    bot_id: str,
    bot_alias_id: str,
    run_started_utc: datetime,
) -> dict[str, Any]:
    runtime = boto3.client("lexv2-runtime", region_name=REGION)

    positive_items, positive_calls = measure_positives(
        runtime, positive_phrasings, bot_id=bot_id, bot_alias_id=bot_alias_id
    )
    negative_items, negative_calls = measure_negatives(
        runtime, negative_phrasings, bot_id=bot_id, bot_alias_id=bot_alias_id
    )
    total_calls = positive_calls + negative_calls

    run_finished_utc = datetime.now(UTC)
    passed = sum(1 for i in positive_items if i["deployed_worst_case"])
    recall = passed / len(positive_items) if positive_items else None
    divergences = [i for i in positive_items if i["diverges_from_d52"]]
    false_escalations = [i for i in negative_items if i["falsely_escalated"]]

    escalated_positive_calls = sum(
        1 for i in positive_items for flag in i["escalated_flags"] if flag
    )

    path_attribution = read_path_attribution(
        function_name="fnol-codehook",
        start=run_started_utc,
        end=run_finished_utc,
    )
    cost = estimate_cost(
        positive_calls=positive_calls,
        negative_calls=negative_calls,
        escalated_positive_calls=escalated_positive_calls,
        path_attribution=path_attribution,
    )

    return {
        "protocol": {
            "positive_population": (
                "evals/holdout/injury_phrasings_independent.yaml (should_escalate=True only)"
            ),
            "negative_population": (
                "evals/holdout/injury_phrasings_independent.yaml (should_escalate=False only, D81 item 5)"
            ),
            "base_k": BASE_K,
            "negative_k": 1,
            "contingency_k_additional": CONTINGENCY_K_ADDITIONAL,
            "contingency_item_budget": CONTINGENCY_ITEM_BUDGET,
            "contingency_items_used": sum(1 for i in positive_items if i["contingency_used"]),
            "scoring": "worst_case_detection: every sample escalated=true with escalation_reason=detection",
            "target": "d52 baseline: evals/baselines/composed_pipeline_k5_v3_20260812.json",
        },
        "positive_items": positive_items,
        "negative_items": negative_items,
        "positives": len(positive_items),
        "negatives": len(negative_items),
        "composed_recall_deployed": recall,
        "composed_recall_deployed_counts": [passed, len(positive_items)],
        "unstable_item_count": sum(1 for i in positive_items if i["unstable"]),
        "divergences_from_d52": [
            {"text": i["text"], "d52": i["d52_worst_case"], "deployed": i["deployed_worst_case"]}
            for i in divergences
        ],
        "false_escalation_count": len(false_escalations),
        "false_escalation_items": [
            {"text": i["text"], "escalation_reason": i["escalation_reason"]}
            for i in false_escalations
        ],
        "provenance_breakdown": provenance_breakdown(positive_items, negative_items),
        "total_recognize_text_calls": total_calls,
        "path_attribution": path_attribution,
        "cost": cost,
        "run_started_utc": run_started_utc.isoformat(timespec="seconds"),
        "run_finished_utc": run_finished_utc.isoformat(timespec="seconds"),
    }


def read_path_attribution(*, function_name: str, start: datetime, end: datetime) -> dict[str, Any]:
    """Reads the Lambda's own `"escalating contact %s on layer %s route %s reason %s"` log line for the
    run's window — the L1-vs-graph split, from the deployed system's own record, not assumed from `D52`.
    Secondary to the per-call `escalation_reason` wire field (`D81` item 4) for the detection/fail-closed
    question; this answers a different question (which LAYER), same as `D52`'s local run reported.

    Logs can lag their write by a few seconds; this polls briefly rather than accepting an
    under-count on the first read, and says plainly if it gives up short of every call.
    """
    logs = boto3.client("logs", region_name=REGION)
    log_group = f"/aws/lambda/{function_name}"
    start_ms = int(start.timestamp() * 1000)

    layers: list[str] = []
    for attempt in range(6):
        end_ms = int(datetime.now(UTC).timestamp() * 1000)
        layers = []
        try:
            paginator = logs.get_paginator("filter_log_events")
            for page in paginator.paginate(
                logGroupName=log_group,
                startTime=start_ms,
                endTime=end_ms,
                filterPattern='"escalating contact"',
            ):
                for event in page.get("events", []):
                    message = event.get("message", "")
                    parts = message.split(" layer ")
                    if len(parts) == 2:
                        layer = parts[1].split(" ")[0].strip()
                        layers.append(layer)
        except Exception as exc:  # noqa: BLE001 - a failed read must not fail the whole run
            return {
                "read_ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "l1_count": None,
                "graph_path_count": None,
            }
        if len(layers) >= 1:
            break
        time.sleep(5)

    l1_count = sum(1 for layer in layers if layer == "L1")
    l2_count = sum(1 for layer in layers if layer == "L2")
    other = len(layers) - l1_count - l2_count
    return {
        "read_ok": True,
        "log_events_matched": len(layers),
        "l1_count": l1_count,
        "graph_path_count": l2_count,
        "other_layer_count": other,
    }


def estimate_cost(
    *,
    positive_calls: int,
    negative_calls: int,
    escalated_positive_calls: int,
    path_attribution: dict[str, Any],
) -> dict[str, Any]:
    total_calls = positive_calls + negative_calls
    lex_usd = round(total_calls * LEX_TEXT_REQUEST_USD, 6)

    # The exactness check is against the number of calls that actually ESCALATED (only an escalating
    # call logs the line this reads), not against `total_calls` -- unlike the single-population version
    # of this script, `total_calls` now includes the 17 negatives, which produce no log line at all when
    # the system behaves correctly. Comparing against `total_calls` here would make a fully successful
    # run look like an incomplete CloudWatch read every time.
    if (
        path_attribution.get("read_ok")
        and path_attribution.get("log_events_matched", 0) >= escalated_positive_calls
    ):
        graph_path_calls_from_positives = path_attribution["graph_path_count"]
        basis = (
            "positives exact: CloudWatch log line per escalating call, D52's per-call rate; "
            "negatives assumed graph-path unconditionally (see module docstring -- no log line exists "
            "for a correctly non-escalating call)"
        )
    else:
        graph_path_calls_from_positives = positive_calls
        basis = (
            "CONSERVATIVE: CloudWatch path read incomplete for positives, assumed every positive call "
            "was graph-path; negatives assumed graph-path unconditionally regardless"
        )

    graph_path_calls = graph_path_calls_from_positives + negative_calls
    bedrock_usd = round(graph_path_calls * GRAPH_PATH_USD, 6)
    return {
        "lex_usd": lex_usd,
        "bedrock_usd_basis": basis,
        "bedrock_usd": bedrock_usd,
        "graph_path_calls_used_for_estimate": graph_path_calls,
        "total_usd": round(lex_usd + bedrock_usd, 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "evals" / "baselines" / "composed_pipeline_deployed_k3_lineE.json",
    )
    args = parser.parse_args(argv)

    outputs = terraform_outputs()
    bot_id = str(outputs["bot_id"])
    bot_alias_id = str(outputs["bot_alias_id"])

    all_phrasings = load_holdout(HoldoutKind.INDEPENDENT)
    positive_phrasings = [p for p in all_phrasings if p.should_escalate]
    negative_phrasings = [p for p in all_phrasings if not p.should_escalate]
    print(
        f"=== Criterion 9 (Line E): composed pipeline, DEPLOYED (bot {bot_id}, alias {bot_alias_id}): "
        f"{len(positive_phrasings)} must-escalate items at base k={BASE_K}, "
        f"{len(negative_phrasings)} must-NOT-escalate items at k=1 (D81 item 5) ==="
    )

    try:
        with verification_run(
            reason=(
                "Stage 4 exit criterion 9 (Line E) — C1 re-verified against the DEPLOYED Lex alias and "
                "Lambda, post-D81 fix: three-state escalated/not-escalated/invalid classification with "
                "abort-on-invalid, escalation provenance read from sessionAttributes.escalation_reason "
                "and required for an item to count toward recall, and all 17 independent-set negatives "
                "sampled at k=1 rather than a 5-item subset. Composed recall must not fall below D52's "
                "1.000 (26/26) or the candidate is rejected regardless of what it buys. Gates "
                "criterion 10 (DID routing)."
            ),
            samples_per_item=BASE_K,
        ) as run:
            return _run(args, run, bot_id, bot_alias_id, positive_phrasings, negative_phrasings)
    except RunInvalidError as exc:
        print(f"\n  *** RUN INVALID (D81): {exc} ***")
        print(
            "  No composed_recall_deployed emitted. Not a C1 breach -- an instrument/infra defect."
        )
        return 2


def _run(
    args: argparse.Namespace,
    run: VerificationRun,
    bot_id: str,
    bot_alias_id: str,
    positive_phrasings: list[InjuryPhrasing],
    negative_phrasings: list[InjuryPhrasing],
) -> int:
    result = measure(
        positive_phrasings,
        negative_phrasings,
        bot_id=bot_id,
        bot_alias_id=bot_alias_id,
        run_started_utc=datetime.now(UTC),
    )
    result["bot_id"] = bot_id
    result["bot_alias_id"] = bot_alias_id

    print(f"\n  positives {result['positives']}  negatives {result['negatives']}")
    print(
        f"  DEPLOYED composed recall {result['composed_recall_deployed']} "
        f"{tuple(result['composed_recall_deployed_counts'])}"
    )
    print(f"  contingency items used {result['protocol']['contingency_items_used']}")
    print(f"  unstable items {result['unstable_item_count']}")
    print(
        f"  provenance breakdown (all escalate=true samples, positives+negatives): "
        f"{result['provenance_breakdown']}"
    )
    print(
        f"  false escalations on the {result['negatives']} negatives: {result['false_escalation_count']}"
    )
    attribution = result["path_attribution"]
    if attribution.get("read_ok"):
        print(
            f"  path attribution (CloudWatch, positives only, exact): "
            f"L1={attribution['l1_count']} graph-path={attribution['graph_path_count']} "
            f"matched={attribution['log_events_matched']}"
        )
    else:
        print(f"  path attribution: READ FAILED — {attribution.get('error')}")

    if result["divergences_from_d52"]:
        print(f"\n  *** {len(result['divergences_from_d52'])} ITEM(S) DIVERGE FROM D52 ***")
        for d in result["divergences_from_d52"]:
            print(f"    D52={d['d52']}  DEPLOYED={d['deployed']}  {d['text'][:70]!r}")
    else:
        print("\n  No per-item divergence from D52's local verdicts.")

    cost = result["cost"]
    print(
        f"\n=== Cost: lex ${cost['lex_usd']} + bedrock ${cost['bedrock_usd']} "
        f"({cost['bedrock_usd_basis']}) = ${cost['total_usd']} ==="
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.out}")

    run.record(
        composed_recall_deployed=result["composed_recall_deployed"],
        composed_recall_deployed_counts=result["composed_recall_deployed_counts"],
        contingency_items_used=result["protocol"]["contingency_items_used"],
        unstable_item_count=result["unstable_item_count"],
        divergences_from_d52=result["divergences_from_d52"],
        provenance_breakdown=result["provenance_breakdown"],
        false_escalation_count=result["false_escalation_count"],
        total_recognize_text_calls=result["total_recognize_text_calls"],
        path_attribution=result["path_attribution"],
        cost_usd=cost["total_usd"],
        bot_id=result["bot_id"],
        bot_alias_id=result["bot_alias_id"],
    )
    run.note(
        "Deployed re-verification (criterion 9, Line E, post-D81 fix) — real RecognizeText calls "
        "against the live alias, three-state classification, provenance-gated recall, all 17 negatives."
    )

    recall = result["composed_recall_deployed"]
    if recall is None or recall < 1.0:
        print(
            "\n  *** C1 BREACH on the DEPLOYED system: composed escalation recall is below 1.000. "
            "Per criterion 9/10's gating, the DID must not be routed. ***"
        )
        run.note("C1 BREACH: deployed composed recall below 1.000 on the must-escalate items.")
        return 1
    if result["divergences_from_d52"]:
        run.note(
            "Deployed result diverges from D52 on at least one item despite recall holding at 1.000."
        )
    if result["false_escalation_count"]:
        run.note(
            f"{result['false_escalation_count']}/{result['negatives']} negatives falsely escalated -- "
            "not a C1 breach (C1 is a recall constraint) but a real precision defect on the deployed "
            "system, worth its own line before criterion 10 if it recurs."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

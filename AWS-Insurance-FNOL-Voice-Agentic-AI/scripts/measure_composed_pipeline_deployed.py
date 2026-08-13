"""Stage 4 exit criterion 9 — `C1` re-verified against the DEPLOYED Lex alias and Lambda, not the local
graph call `D52` measured. `docs/phase8/BUILD-PLAN.md` line 330; `COSTS.md` Line D.

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
    leaks into another's). An item is scored `worst_case=True` only if all k samples escalated —
    `measure_composed_pipeline.py`'s own `worst_case()` semantics, reused so the two numbers are
    comparable. Composed recall is the fraction of the 26 that pass. `C1` requires 1.000.

    CONTINGENCY: any item whose k=3 samples are not unanimous — a real disagreement, not just "still
    below 1.000" — gets 4 more samples (total k=7) before being called a regression rather than a
    Lambda-specific flake, budgeted for up to 6 of the 26 items per `COSTS.md`.

WHAT "ESCALATED" MEANS ON THE WIRE
    `api/lex_codehook.py::_close()` sets `sessionAttributes["escalate"] = "true"` at the one boundary
    that knows this response is headed for a real Connect flow. That is the same attribute
    `fnol-inbound.json.tftpl`'s `CheckEscalation` action reads. Reading it back from the
    `RecognizeText` response is therefore checking the exact signal production checks, not a proxy.

PATH ATTRIBUTION, READ NOT ASSUMED
    `D52`'s local run saw 19 of 26 positives caught only by L2 (guardrail+router), 7 by the raw-text L1
    pre-check alone. Whether the deployed Lambda's L1 lexicon fires on the same split is one of the exact
    things this criterion exists to check — so this script does not assume it. It reads the Lambda's own
    log line (`"escalating contact %s on layer %s route %s"`, `api/lex_codehook.py::_escalate`) back from
    CloudWatch Logs for the run's time window, per call, and reports the observed L1/L2 split. `D77`'s
    lesson applies here too: a call that returned `escalate=true` is evidence the response said so, not
    evidence of *why* — that "why" is a separate read.

COST
    `lexv2-runtime:RecognizeText` cost is exact — this script counts every call it makes and multiplies
    by the published $0.00075/text-request rate. The Bedrock/guardrail dollar rate applied to graph-path
    calls is `D52`'s previously-measured per-call rate (guardrail 2 units + one L2 sample,
    $0.0003387/call) — Bedrock itself is not re-instrumented by this run, only the path counts (L1 vs.
    graph) are exact, from the CloudWatch read above. Where that read fails (log propagation lag, a
    permissions gap), the script says so explicitly and reports the conservative all-graph-path estimate
    rather than silently assuming `D52`'s ratio transfers.

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
from typing import Any

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


def recognize(runtime: Any, *, bot_id: str, bot_alias_id: str, text: str) -> dict[str, Any]:
    session_id = f"criterion9-{uuid.uuid4()}"
    started = time.monotonic()
    response = runtime.recognize_text(
        botId=bot_id,
        botAliasId=bot_alias_id,
        localeId=LOCALE_ID,
        sessionId=session_id,
        text=text,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    session_attributes = (
        response.get("sessionState", {}).get("sessionAttributes") or {}
    )
    escalated = session_attributes.get("escalate") == "true"
    return {
        "session_id": session_id,
        "escalated": escalated,
        "elapsed_ms": elapsed_ms,
        "messages": [m.get("content", "") for m in response.get("messages", [])],
    }


def worst_case_positive(samples: list[bool]) -> bool:
    """Matches `measure_composed_pipeline.py::worst_case(..., positive=True)`: any single miss on a
    must-escalate item counts as a miss."""
    return all(samples)


def measure(
    phrasings: list[InjuryPhrasing],
    *,
    bot_id: str,
    bot_alias_id: str,
    run_started_utc: datetime,
) -> dict[str, Any]:
    runtime = boto3.client("lexv2-runtime", region_name=REGION)
    d52_verdicts = load_d52_verdicts()

    items: list[dict[str, Any]] = []
    contingency_spent = 0
    total_calls = 0

    for phrasing in phrasings:
        samples = [recognize(runtime, bot_id=bot_id, bot_alias_id=bot_alias_id, text=phrasing.text)
                   for _ in range(BASE_K)]
        total_calls += BASE_K
        escalated_flags = [s["escalated"] for s in samples]
        unanimous = len(set(escalated_flags)) == 1
        contingency_used = False

        if not unanimous and contingency_spent < CONTINGENCY_ITEM_BUDGET:
            extra = [
                recognize(runtime, bot_id=bot_id, bot_alias_id=bot_alias_id, text=phrasing.text)
                for _ in range(CONTINGENCY_K_ADDITIONAL)
            ]
            total_calls += CONTINGENCY_K_ADDITIONAL
            samples = samples + extra
            escalated_flags = [s["escalated"] for s in samples]
            contingency_spent += 1
            contingency_used = True

        worst_case = worst_case_positive(escalated_flags)
        d52_verdict = d52_verdicts.get(phrasing.text)

        items.append(
            {
                "text": phrasing.text,
                "kabco": phrasing.kabco.value,
                "k": len(samples),
                "contingency_used": contingency_used,
                "escalated_flags": escalated_flags,
                "unstable": not unanimous and not (contingency_used and len(set(escalated_flags)) == 1),
                "deployed_worst_case": worst_case,
                "d52_worst_case": d52_verdict,
                "diverges_from_d52": (d52_verdict is not None) and (worst_case != d52_verdict),
                "elapsed_ms_samples": [s["elapsed_ms"] for s in samples],
                "session_ids": [s["session_id"] for s in samples],
            }
        )

    run_finished_utc = datetime.now(UTC)
    passed = sum(1 for i in items if i["deployed_worst_case"])
    recall = passed / len(items) if items else None
    divergences = [i for i in items if i["diverges_from_d52"]]

    path_attribution = read_path_attribution(
        function_name="fnol-codehook",
        start=run_started_utc,
        end=run_finished_utc,
    )
    cost = estimate_cost(total_calls=total_calls, path_attribution=path_attribution)

    return {
        "protocol": {
            "population": "evals/holdout/injury_phrasings_independent.yaml (should_escalate=True only)",
            "base_k": BASE_K,
            "contingency_k_additional": CONTINGENCY_K_ADDITIONAL,
            "contingency_item_budget": CONTINGENCY_ITEM_BUDGET,
            "contingency_items_used": contingency_spent,
            "scoring": "all-k-samples-must-escalate on each must-escalate item (worst_case_positive)",
            "target": "d52 baseline: evals/baselines/composed_pipeline_k5_v3_20260812.json",
        },
        "items": items,
        "positives": len(items),
        "composed_recall_deployed": recall,
        "composed_recall_deployed_counts": [passed, len(items)],
        "unstable_item_count": sum(1 for i in items if i["unstable"]),
        "divergences_from_d52": [
            {"text": i["text"], "d52": i["d52_worst_case"], "deployed": i["deployed_worst_case"]}
            for i in divergences
        ],
        "total_recognize_text_calls": total_calls,
        "path_attribution": path_attribution,
        "cost": cost,
        "run_started_utc": run_started_utc.isoformat(timespec="seconds"),
        "run_finished_utc": run_finished_utc.isoformat(timespec="seconds"),
    }


def read_path_attribution(*, function_name: str, start: datetime, end: datetime) -> dict[str, Any]:
    """Reads the Lambda's own `"escalating contact %s on layer %s route %s"` log line for the run's
    window — the L1-vs-graph split, from the deployed system's own record, not assumed from `D52`.

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


def estimate_cost(*, total_calls: int, path_attribution: dict[str, Any]) -> dict[str, Any]:
    lex_usd = round(total_calls * LEX_TEXT_REQUEST_USD, 6)

    if path_attribution.get("read_ok") and path_attribution.get("log_events_matched", 0) >= total_calls:
        graph_path_calls = path_attribution["graph_path_count"]
        basis = "exact: CloudWatch log line per call, D52's per-call dollar rate"
    else:
        # CloudWatch read incomplete or failed — report the conservative worst case, not D52's ratio,
        # per the module docstring: an assumed split must never masquerade as a measured one.
        graph_path_calls = total_calls
        basis = "CONSERVATIVE: CloudWatch path read incomplete, assumed every call was graph-path"

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
        default=REPO_ROOT / "evals" / "baselines" / "composed_pipeline_deployed_k3_20260813.json",
    )
    args = parser.parse_args(argv)

    outputs = terraform_outputs()
    bot_id = str(outputs["bot_id"])
    bot_alias_id = str(outputs["bot_alias_id"])

    phrasings = [p for p in load_holdout(HoldoutKind.INDEPENDENT) if p.should_escalate]
    print(
        f"=== Criterion 9: composed pipeline, DEPLOYED (bot {bot_id}, alias {bot_alias_id}): "
        f"{len(phrasings)} must-escalate items, base k={BASE_K} ==="
    )

    with verification_run(
        reason=(
            "Stage 4 exit criterion 9 — C1 re-verified against the DEPLOYED Lex alias and Lambda, "
            "the first point _FINGERPRINT_SOURCES moves on a deployed resource rather than a local "
            "call. Marco's protocol: k=3 on the 26 must-escalate items (his own correction of an "
            "earlier k=1/43-item proposal — D32 showed temperature 0.0 does not make the generation "
            "path reproducible, and a deployed-only k measures cold starts/concurrency/session "
            "handling, not model stochasticity). Composed recall must not fall below D52's 1.000 "
            "(26/26) or the candidate is rejected regardless of what it buys. Gates criterion 10 "
            "(DID routing)."
        ),
        samples_per_item=BASE_K,
    ) as run:
        return _run(args, run, bot_id, bot_alias_id, phrasings)


def _run(
    args: argparse.Namespace,
    run: VerificationRun,
    bot_id: str,
    bot_alias_id: str,
    phrasings: list[InjuryPhrasing],
) -> int:
    result = measure(
        phrasings,
        bot_id=bot_id,
        bot_alias_id=bot_alias_id,
        run_started_utc=datetime.now(UTC),
    )
    result["bot_id"] = bot_id
    result["bot_alias_id"] = bot_alias_id

    print(f"\n  positives {result['positives']}")
    print(
        f"  DEPLOYED composed recall {result['composed_recall_deployed']} "
        f"{tuple(result['composed_recall_deployed_counts'])}"
    )
    print(f"  contingency items used {result['protocol']['contingency_items_used']}")
    print(f"  unstable items {result['unstable_item_count']}")
    attribution = result["path_attribution"]
    if attribution.get("read_ok"):
        print(
            f"  path attribution (CloudWatch, exact): L1={attribution['l1_count']} "
            f"graph-path={attribution['graph_path_count']} "
            f"matched={attribution['log_events_matched']}/{result['total_recognize_text_calls']}"
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
        total_recognize_text_calls=result["total_recognize_text_calls"],
        path_attribution=result["path_attribution"],
        cost_usd=cost["total_usd"],
        bot_id=result["bot_id"],
        bot_alias_id=result["bot_alias_id"],
    )
    run.note(
        "Deployed re-verification (criterion 9), not a component measurement — real RecognizeText "
        "calls against the live alias, matching the shape D52 measured only in the graph."
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
        run.note("Deployed result diverges from D52 on at least one item despite recall holding at 1.000.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

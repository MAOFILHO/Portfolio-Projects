"""Phase 9, `RESULTS.md` §11.18/§11.19 -- does stripping pydantic's auto-generated `title`s and the two
enum docstrings from `classify_turn`'s tool schema move the router's own p95, and does it change what the
router classifies?

`APPROVED: Phase 9 -- schema-strip latency test, ~$0.10 ceiling`, Marco, 2026-08-14. Required addition: the
stripped schema removes content the model reads, not just bytes, so every pair captures classification
agreement alongside latency -- a faster router that classifies differently is not shippable (`RESULTS.md`
§11.19 fixes the exact agreement/shippability rule, committed before this script's first real call).

Same discipline as `scripts/measure_temperature_variance.py` and `ADR-014`'s ladder: calls the real, shipped
`classify_turn` with exactly one input changed (`tool_spec`), never a reimplementation. Two arms:

  U (unstripped) -- `tool_spec=None`, i.e. today's shipped `build_classify_turn_tool_spec()`, imported
     directly so this arm cannot drift from production.
  S (stripped)   -- the same schema with `title` and `$defs`-level `description` keys removed
     (`RESULTS.md` §11.17 Item 2's measured 1,148 -> 766-char variant), passed through the `tool_spec`
     parameter `classify_turn` already exposes for exactly this purpose. The system prompt is identical in
     both arms -- §11.17 found it lean, not a target.

Paired, interleaved design: for each utterance, call both arms back to back (order randomized per pair) from
the same process/machine/network path, so the within-pair latency difference isolates the schema change from
any client-location or time-of-day confound. This script does not claim to reproduce the deployed Lambda's
absolute latency (`RESULTS.md` §11.15's 401ms/1,286ms come from a different vantage point) -- only the
within-pair delta is load-bearing here.

Corpus: every real caller turn across `evals/golden/*.yaml` (141 turns, all six intents plus adversarial and
safety), loaded via `evals.schema.load_golden_set` -- reused, not authored, and not limited to first turns,
since `route_and_classify` runs on every turn a real call reaches.

`ADR-013`: no `mock_aws()` here. Every call is real and billed. Uses `us.amazon.nova-micro-v1:0` (the
`settings.py` default `ROUTER_MODEL_ID`, same as every other measurement script in this directory) rather
than the `fnol-router` application inference profile ARN, so `evals.tier_b.CostLog`'s existing price table
prices every call without a special case -- a deliberate, named tradeoff: this run's ~$0.10 will not carry
the `ADR-016` cost-allocation tag production traffic gets. Trivial at this size, not silently assumed away.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import statistics
import time
from pathlib import Path
from typing import Any

from fnol_voice_agent.aws.bedrock_router import (
    BotoBedrockConverseClient,
    build_classify_turn_tool_spec,
    classify_turn,
)

from evals.schema import load_golden_set
from evals.tier_b import CostLog, LoggingCaller

OUT_DIR = Path("evals/baselines")
LOW_CONFIDENCE_THRESHOLD = 0.5  # graph.py:56 -- reused, not reinvented, per RESULTS.md §11.19

SEED = 20260814  # the date of Marco's approval -- fixed, not re-rolled between pilot and main run


def strip_schema(tool_spec: dict[str, Any]) -> dict[str, Any]:
    """RESULTS.md §11.17 Item 2's stripped variant: removes pydantic's auto-generated `title` fields and
    the two enum classes' docstrings-as-`description`, keeps the one legitimate `toolSpec`-level
    description and every field the model actually needs (types, enums, required list, $ref structure).
    """

    def _strip(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: _strip(v) for k, v in node.items() if k not in ("title", "description")}
        if isinstance(node, list):
            return [_strip(x) for x in node]
        return node

    stripped = _strip(copy.deepcopy(tool_spec))
    stripped["toolSpec"]["description"] = tool_spec["toolSpec"]["description"]
    return stripped


def load_corpus() -> list[str]:
    """Every real caller turn across the golden set -- not just first turns, since route_and_classify
    runs on every turn a real call reaches, not only conversation openers."""
    turns = [turn.caller for conv in load_golden_set() for turn in conv.turns]
    if not turns:
        raise RuntimeError(
            "evals/golden produced zero turns -- corpus load is broken, not just empty"
        )
    return turns


def classification_key(tc: Any) -> tuple[bool, str, str, bool]:
    """The four-field comparison RESULTS.md §11.19 defines agreement over. `intent_confidence` compares
    by threshold side, not exact value -- §11.19's reasoning, not repeated here."""
    return (
        tc.safety_flag,
        tc.intent.value,
        tc.coverage_question_type.value,
        tc.intent_confidence >= LOW_CONFIDENCE_THRESHOLD,
    )


def run_pairs(
    utterances: list[str],
    *,
    caller: Any,
    unstripped_spec: dict[str, Any],
    stripped_spec: dict[str, Any],
    rng: random.Random,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for i, text in enumerate(utterances):
        messages = [{"role": "user", "content": [{"text": text}]}]
        order = ["U", "S"] if rng.random() < 0.5 else ["S", "U"]
        arm_results: dict[str, dict[str, Any]] = {}
        for arm in order:
            spec = unstripped_spec if arm == "U" else stripped_spec
            t0 = time.monotonic()
            tc = classify_turn(messages, caller=caller, tool_spec=spec)
            latency_ms = (time.monotonic() - t0) * 1000
            arm_results[arm] = {
                "latency_ms": latency_ms,
                "key": classification_key(tc),
                "raw": tc.model_dump(mode="json"),
            }
        agree = arm_results["U"]["key"] == arm_results["S"]["key"]
        record = {
            "i": i,
            "utterance": text,
            "order": order,
            "agree": agree,
            "U_latency_ms": arm_results["U"]["latency_ms"],
            "S_latency_ms": arm_results["S"]["latency_ms"],
            "U_raw": arm_results["U"]["raw"],
            "S_raw": arm_results["S"]["raw"],
        }
        records.append(record)
        flag = "" if agree else "  *** DISAGREE ***"
        print(
            f"  [{i + 1}/{len(utterances)}] U={arm_results['U']['latency_ms']:6.1f}ms "
            f"S={arm_results['S']['latency_ms']:6.1f}ms  order={''.join(order)}{flag}"
        )
        if not agree:
            print(f"      utterance: {text!r}")
            print(f"      U: {arm_results['U']['key']}")
            print(f"      S: {arm_results['S']['key']}")
    return records


def bootstrap_ci_delta_p95(
    u_latencies: list[float], s_latencies: list[float], *, resamples: int, rng: random.Random
) -> tuple[float, float, float]:
    """Percentile-bootstrap 95% CI on Delta-p95 = p95(S) - p95(U), resampling pairs (index-paired, since
    U/S share an utterance per row) with replacement. Returns (point_estimate, ci_low, ci_high)."""
    n = len(u_latencies)
    assert n == len(s_latencies)

    def p95(vals: list[float]) -> float:
        return statistics.quantiles(vals, n=100, method="inclusive")[94]

    point = p95(s_latencies) - p95(u_latencies)
    deltas = []
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        u_sample = [u_latencies[j] for j in idx]
        s_sample = [s_latencies[j] for j in idx]
        deltas.append(p95(s_sample) - p95(u_sample))
    deltas.sort()
    lo = deltas[int(0.025 * resamples)]
    hi = deltas[int(0.975 * resamples) - 1]
    return point, lo, hi


def summarize(records: list[dict[str, Any]], *, cost: dict[str, Any]) -> dict[str, Any]:
    u = [r["U_latency_ms"] for r in records]
    s = [r["S_latency_ms"] for r in records]
    disagreements = [r for r in records if not r["agree"]]

    def stats(vals: list[float]) -> dict[str, float]:
        sv = sorted(vals)
        return {
            "n": len(vals),
            "min": sv[0],
            "p50": statistics.median(sv),
            "mean": statistics.fmean(sv),
            "p95": (
                statistics.quantiles(sv, n=100, method="inclusive")[94] if len(sv) >= 2 else sv[0]
            ),
            "max": sv[-1],
        }

    rng = random.Random(SEED)
    point, ci_lo, ci_hi = bootstrap_ci_delta_p95(u, s, resamples=2000, rng=rng)

    return {
        "n_pairs": len(records),
        "agreement": {
            "n_agree": len(records) - len(disagreements),
            "n_disagree": len(disagreements),
            "rate": (len(records) - len(disagreements)) / len(records) if records else None,
            "disagreements": [
                {"i": r["i"], "utterance": r["utterance"], "U": r["U_raw"], "S": r["S_raw"]}
                for r in disagreements
            ],
        },
        "latency": {"U": stats(u), "S": stats(s)},
        "delta_p95": {"point_estimate_ms": point, "ci_95_low_ms": ci_lo, "ci_95_high_ms": ci_hi},
        "cost": cost,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-pairs", type=int, required=True, help="number of pairs to run")
    parser.add_argument(
        "--out", type=str, required=True, help="output JSON filename under evals/baselines/"
    )
    args = parser.parse_args(argv)

    rng = random.Random(SEED)
    corpus = load_corpus()
    shuffled = corpus[:]
    rng.shuffle(shuffled)
    utterances = [shuffled[i % len(shuffled)] for i in range(args.n_pairs)]
    print(
        f"corpus: {len(corpus)} real turns from evals/golden/*.yaml, sampling {args.n_pairs} pairs"
    )

    unstripped_spec = build_classify_turn_tool_spec()
    stripped_spec = strip_schema(unstripped_spec)
    print(f"unstripped schema: {len(json.dumps(unstripped_spec, separators=(',', ':')))} chars")
    print(f"stripped schema:   {len(json.dumps(stripped_spec, separators=(',', ':')))} chars")

    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region="us-west-2"), log)

    records = run_pairs(
        utterances,
        caller=caller,
        unstripped_spec=unstripped_spec,
        stripped_spec=stripped_spec,
        rng=rng,
    )

    summary = summarize(records, cost=log.summary())
    out_path = OUT_DIR / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"summary": summary, "records": records}, indent=2) + "\n")

    a = summary["agreement"]
    lat = summary["latency"]
    dp = summary["delta_p95"]
    print("\n" + "=" * 78)
    print(f"n_pairs={summary['n_pairs']}")
    print(
        f"agreement: {a['n_agree']}/{summary['n_pairs']} ({a['rate']:.4f})  disagreements={a['n_disagree']}"
    )
    print(f"U: p50={lat['U']['p50']:.1f}ms p95={lat['U']['p95']:.1f}ms max={lat['U']['max']:.1f}ms")
    print(f"S: p50={lat['S']['p50']:.1f}ms p95={lat['S']['p95']:.1f}ms max={lat['S']['max']:.1f}ms")
    print(
        f"delta_p95 = {dp['point_estimate_ms']:+.1f}ms  "
        f"95% CI [{dp['ci_95_low_ms']:+.1f}, {dp['ci_95_high_ms']:+.1f}]"
    )
    print(f"cost: {summary['cost']}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

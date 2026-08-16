"""`D90` part 1 (`RESULTS.md` §33/§35) -- does folding `active_slot`/`filled_slots` into
`classify_turn`'s message list (`agents/nodes/routing.py::_build_classify_messages`) move the
router's own latency against `C14`'s 1,800ms p95 budget?

Marco, approving Option 1 (2026-08-16): "Measure the latency delta. A longer prompt against
C14's 1,800ms budget is currently unmeasured, and C14 is already failing. If this makes it
worse, I want the number before the apply, not after." No `stacks/main` apply happens from
this script -- it measures the already-shipped, not-yet-deployed local code change directly
against real Bedrock.

Same discipline as `scripts/measure_router_schema_latency.py` (Phase 9, `RESULTS.md`
§11.18/11.19) and `ADR-014`'s ladder: calls the real, shipped `classify_turn` and the real,
shipped `_build_classify_messages`, never a reimplementation. Two arms:

  N (no context)  -- `_build_classify_messages` called against a state with `active_slot`/
     `filled_slots` stripped -- today's shipped, pre-fix message shape (proven byte-identical
     to the literal pre-fix code by `tests/unit/test_routing.py`).
  C (context)     -- `_build_classify_messages` called against the turn's real accumulated
     session state, sourced from the golden corpus's own ground truth (below), not fabricated.

Paired, interleaved design: for each turn, call both arms back to back (order randomized per
pair) from the same process/machine/network path, so the within-pair latency difference
isolates the context-enrichment change from any client-location or time-of-day confound. As
with the schema-strip script, this does not claim to reproduce the deployed Lambda's absolute
latency -- only the within-pair delta is load-bearing here.

Corpus: every real turn across `evals/golden/*.yaml`, replayed in conversation order. Per
conversation, `filled_slots` accumulates as `seed_slots` union every prior turn's
`expect.slots_filled` -- the golden corpus's own recorded ground truth for what should be
filled by that point, not a synthetic guess. `active_slot` is a proxy, not literal ground
truth -- the golden schema does not record it directly -- taken as the first key THIS turn's
own `expect.slots_filled` newly introduces (the slot the turn appears to be answering), or
`None` when this turn introduces no new slot. This means the corpus is the same realistic
mixture `route_and_classify` sees in production: some turns carry no session context (first
turns, or turns not answering a tracked slot) and some carry a lot -- not a cherry-picked
worst case.

`ADR-013`: no `mock_aws()` here. Every call is real and billed. Uses
`us.amazon.nova-micro-v1:0` (the `settings.py` default `ROUTER_MODEL_ID`), matching every
other measurement script in this directory -- same named tradeoff as
`measure_router_schema_latency.py`: this run's cost does not carry the `ADR-016` cost-
allocation tag production traffic gets. Trivial at this size, not silently assumed away.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path
from typing import Any

from fnol_voice_agent.agents.nodes.routing import _build_classify_messages
from fnol_voice_agent.agents.state import AgentState
from fnol_voice_agent.aws.bedrock_router import BotoBedrockConverseClient, classify_turn

from evals.schema import GoldenConversation, load_golden_set
from evals.tier_b import CostLog, LoggingCaller

OUT_DIR = Path("evals/baselines")
SEED = 20260816  # today -- Marco's approval date for this measurement


def build_states() -> list[tuple[str, AgentState, AgentState]]:
    """(turn_text, no_context_state, context_state) triples across every real turn in
    `evals/golden/*.yaml`, in conversation order. See module docstring for how
    `filled_slots`/`active_slot` are sourced from the corpus's own ground truth.
    """
    triples: list[tuple[str, AgentState, AgentState]] = []
    conversations: list[GoldenConversation] = load_golden_set()
    for conv in conversations:
        accumulated: dict[str, Any] = dict(conv.seed_slots)
        for turn in conv.turns:
            new_keys = [k for k in turn.expect.slots_filled if k not in accumulated]
            active_slot = new_keys[0] if new_keys else None
            no_context_state: AgentState = {"turn_input": turn.caller}
            context_state: AgentState = {
                "turn_input": turn.caller,
                "active_slot": active_slot,
                "filled_slots": dict(accumulated),
            }
            triples.append((turn.caller, no_context_state, context_state))
            accumulated.update(turn.expect.slots_filled)
    if not triples:
        raise RuntimeError(
            "evals/golden produced zero turns -- corpus load is broken, not just empty"
        )
    return triples


def run_pairs(
    triples: list[tuple[str, AgentState, AgentState]], *, caller: Any, rng: random.Random
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for i, (text, no_context_state, context_state) in enumerate(triples):
        order = ["N", "C"] if rng.random() < 0.5 else ["C", "N"]
        arm_results: dict[str, dict[str, Any]] = {}
        for arm in order:
            state = no_context_state if arm == "N" else context_state
            messages = _build_classify_messages(state)
            t0 = time.monotonic()
            classify_turn(messages, caller=caller)
            latency_ms = (time.monotonic() - t0) * 1000
            arm_results[arm] = {
                "latency_ms": latency_ms,
                "prompt_chars": len(messages[0]["content"][0]["text"]),
            }
        record = {
            "i": i,
            "utterance": text,
            "has_context": context_state.get("active_slot") is not None
            or bool(context_state.get("filled_slots")),
            "order": order,
            "N_latency_ms": arm_results["N"]["latency_ms"],
            "C_latency_ms": arm_results["C"]["latency_ms"],
            "N_prompt_chars": arm_results["N"]["prompt_chars"],
            "C_prompt_chars": arm_results["C"]["prompt_chars"],
        }
        records.append(record)
        print(
            f"  [{i + 1}/{len(triples)}] N={arm_results['N']['latency_ms']:6.1f}ms "
            f"C={arm_results['C']['latency_ms']:6.1f}ms  order={''.join(order)}"
            f"  ctx={'Y' if record['has_context'] else 'n'}"
        )
    return records


def bootstrap_ci_delta_p95(
    n_latencies: list[float], c_latencies: list[float], *, resamples: int, rng: random.Random
) -> tuple[float, float, float]:
    """Percentile-bootstrap 95% CI on Delta-p95 = p95(C) - p95(N), resampling pairs
    (index-paired, since N/C share a turn per row) with replacement. Same method as
    `measure_router_schema_latency.py`'s `bootstrap_ci_delta_p95` -- not reinvented."""
    n = len(n_latencies)
    assert n == len(c_latencies)

    def p95(vals: list[float]) -> float:
        return statistics.quantiles(vals, n=100, method="inclusive")[94]

    point = p95(c_latencies) - p95(n_latencies)
    deltas = []
    for _ in range(resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        n_sample = [n_latencies[j] for j in idx]
        c_sample = [c_latencies[j] for j in idx]
        deltas.append(p95(c_sample) - p95(n_sample))
    deltas.sort()
    lo = deltas[int(0.025 * resamples)]
    hi = deltas[int(0.975 * resamples) - 1]
    return point, lo, hi


def summarize(records: list[dict[str, Any]], *, cost: dict[str, Any]) -> dict[str, Any]:
    n = [r["N_latency_ms"] for r in records]
    c = [r["C_latency_ms"] for r in records]
    context_records = [r for r in records if r["has_context"]]

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
    point, ci_lo, ci_hi = bootstrap_ci_delta_p95(n, c, resamples=2000, rng=rng)

    return {
        "n_pairs": len(records),
        "n_pairs_with_context": len(context_records),
        "latency": {"N": stats(n), "C": stats(c)},
        "delta_p95": {"point_estimate_ms": point, "ci_95_low_ms": ci_lo, "ci_95_high_ms": ci_hi},
        "prompt_chars": {
            "N_mean": statistics.fmean(r["N_prompt_chars"] for r in records),
            "C_mean": statistics.fmean(r["C_prompt_chars"] for r in records),
        },
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
    corpus = build_states()
    shuffled = corpus[:]
    rng.shuffle(shuffled)
    triples = [shuffled[i % len(shuffled)] for i in range(args.n_pairs)]
    n_with_context = sum(
        1 for _, _, ctx in triples if ctx.get("active_slot") is not None or ctx.get("filled_slots")
    )
    print(
        f"corpus: {len(corpus)} real turns from evals/golden/*.yaml, sampling {args.n_pairs} pairs "
        f"({n_with_context} carry session context)"
    )

    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region="us-west-2"), log)

    records = run_pairs(triples, caller=caller, rng=rng)

    summary = summarize(records, cost=log.summary())
    out_path = OUT_DIR / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"summary": summary, "records": records}, indent=2) + "\n")

    lat = summary["latency"]
    dp = summary["delta_p95"]
    pc = summary["prompt_chars"]
    print("\n" + "=" * 78)
    print(f"n_pairs={summary['n_pairs']}  with_context={summary['n_pairs_with_context']}")
    print(f"N: p50={lat['N']['p50']:.1f}ms p95={lat['N']['p95']:.1f}ms max={lat['N']['max']:.1f}ms")
    print(f"C: p50={lat['C']['p50']:.1f}ms p95={lat['C']['p95']:.1f}ms max={lat['C']['max']:.1f}ms")
    print(
        f"delta_p95 = {dp['point_estimate_ms']:+.1f}ms  "
        f"95% CI [{dp['ci_95_low_ms']:+.1f}, {dp['ci_95_high_ms']:+.1f}]"
    )
    print(f"prompt chars: N_mean={pc['N_mean']:.0f}  C_mean={pc['C_mean']:.0f}")
    print(f"cost: {summary['cost']}")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

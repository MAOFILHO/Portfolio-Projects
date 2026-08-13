"""Stage 8 — the third and final independent-set fingerprint, spent on the **composed pipeline**.

Ledger entry #4, distinct configuration #3. Marco set the scope, and the reasoning is the phase's
headline finding rather than a preference:

> *"Scope it as the COMPOSED pipeline -- guardrail v2 input filter -> L1 -> L2 -- not the router alone.
> Entry #1 verifies the router in isolation; the guardrail is upstream of L2 and has never been measured
> against the independent set. The tuning-set 0/45 is not that number. Record the reasoning explicitly:
> declining on 'the router is unchanged' would repeat §3.9's error one section after documenting it.
> Component verification is not composition verification."*

## Why the router being unchanged is not a reason to skip this

`config_fingerprint()` returns the same value it did at Stage 5 for the three Python files it hashed
then. Read on its own that says "nothing changed, entry #1 already covers it." It is wrong twice:

1. **Entry #1 measured L1 u L2 with no guardrail in the path at all.** The guardrail resource did not
   exist when it ran. Whatever it verified, it did not verify the shipped system.
2. **The fingerprint was blind to the guardrail** until this stage widened it. v1 -- the configuration
   that blocked 10 of 26 must-escalate phrasings -- and v2 hashed identically. "The fingerprint has not
   moved" was therefore not evidence of anything about the guardrail. See `evals/holdout_ledger.py`.

`RESULTS.md` §3.9 is the record of a system whose every component passed its own review and whose
composition was a C1 breach. Declining to measure the composition because each part is individually
verified is that exact error, and it would be committed one section after documenting it.

## The order measured is the SHIPPED order, which is not the order in the instruction

The instruction says *guardrail -> L1 -> L2*. `agents/graph.py` ships **L1 -> guardrail -> L2**:

    START -> l1_safety_check --[flag]--> injury_escalation -> END
                             --[clear]-> guardrails_input_check --[blocked]--> blocked_response -> END
                                                                --[clear]---> routing (L2) -> ...

That ordering is `ADR-010`'s deliberate guarantee: a guardrail block cannot pre-empt L1. This script
measures the shipped order, because the claim `C1` makes is about the shipped system. It also computes
the guardrail-first counterfactual from the same per-item data at no extra cost, because
`RESULTS.md` §3.9 says in as many words that *"a guard that relies solely on ordering fails the moment
someone reorders it"* -- and the difference between the two numbers is exactly how much of `C1` is
resting on one graph edge. If they are equal, the ordering is not load-bearing on this population and
that is worth knowing too.

## What is sampled, and what is not

* **L1 is deterministic** -- evaluated once. Re-sampling pure Python re-confirms itself.
* **The guardrail is evaluated once per item.** `ApplyGuardrail` is a classifier call and is not
  claimed here to be deterministic; k=1 on it is a limitation, stated rather than hidden. It is also
  the same k entries #2/#3 used, which keeps the block counts comparable.
* **L2 is sampled k=5**, matching entry #1's protocol so the two union numbers are comparable.
* **L2 is sampled on every item** -- including ones L1 already caught and ones the guardrail blocked.
  The shipped graph short-circuits both. Sampling anyway costs ~$0.008 in total, keeps the population
  identical to entry #1's, and is the only way to tell "the guardrail blocked it" apart from "L2 would
  have missed it regardless" in the evidence. Without those samples a block and a detector miss look
  the same in every aggregate.

## The text L2 actually receives

`guardrails_input_check` returns `{"guardrail_input_blocked": result.blocked}` and **discards
`result.output_text`**; `routing.py` then reads `state["turn_input"]`, the original raw turn. So L2 sees
the unmodified text, and a PII anonymisation cannot strip an injury signal on the way to the detector.
This script sends L2 the raw text because that is what the graph does -- and it records the
anonymised text separately wherever the guardrail modified anything, so the discard is visible in the
evidence rather than inferred from reading the node.

That discard is a live privacy defect in the other direction and it is not this script's job to fix.
See `docs/phase7/NOT-FIXED.md`.

`ADR-013`: no `mock_aws()` in this file. Every call is a real, billed call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import boto3

from fnol_voice_agent.agents.lexicon import detect_safety_trigger
from fnol_voice_agent.aws.bedrock_router import BotoBedrockConverseClient, classify_turn
from fnol_voice_agent.config.settings import DEFAULT_REGION
from fnol_voice_agent.guardrails.client import BedrockGuardrailClient, GuardrailClient

from evals.holdout import HoldoutKind, InjuryPhrasing, load_holdout
from evals.holdout_ledger import VerificationRun, verification_run
from evals.metrics import BinaryClassificationCounts
from evals.tier_b import CostLog, LoggingCaller

SAMPLES_PER_ITEM = 5

# Fields of the live guardrail whose change would change what this measurement means. Everything
# under `createdAt`/`updatedAt`/`statusReason` is excluded: a re-publish with identical policy is the
# same configuration, and including a timestamp would make every run look like a new system.
_LIVE_CONFIG_FIELDS = (
    "contentPolicy",
    "topicPolicy",
    "sensitiveInformationPolicy",
    "wordPolicy",
    "contextualGroundingPolicy",
    "blockedInputMessaging",
    "blockedOutputsMessaging",
)


def live_guardrail_config_sha(
    guardrail_id: str, version: str, *, region: str = DEFAULT_REGION
) -> str:
    """A hash of the guardrail Bedrock is actually serving, not of the Terraform that should have
    produced it.

    `_FINGERPRINT_SOURCES` hashes `main.tf`, which is the artifact. A console edit, a partial apply, or
    a stale local state file all leave the artifact untouched while the live resource differs -- the
    §3.5 pattern, and the reason this second hash exists. Recorded in the ledger entry alongside the
    file-based fingerprint so a future reader can tell the two apart.
    """
    response = boto3.client("bedrock", region_name=region).get_guardrail(
        guardrailIdentifier=guardrail_id, guardrailVersion=version
    )
    payload = {field: response.get(field) for field in _LIVE_CONFIG_FIELDS}
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def worst_case(samples: list[bool], *, positive: bool) -> bool:
    """The safety-conservative reading of k samples, matching `SUCCESS-METRICS.md` §2's
    *"recall wins any conflict"*: on a must-escalate item any single miss counts as a miss; on a
    must-not-escalate item any single fire counts as a false escalation."""
    return all(samples) if positive else any(samples)


def measure(
    phrasings: list[InjuryPhrasing],
    guardrail: GuardrailClient,
    caller: LoggingCaller,
    *,
    k: int = SAMPLES_PER_ITEM,
) -> dict[str, Any]:
    """One pass of the composed pipeline over the whole independent set.

    Stores every sample and every intermediate verdict, per `RESULTS.md` §0.1's complaint that Phase
    6's stored baselines could not answer questions nobody thought to ask at the time.
    """
    items: list[dict[str, Any]] = []
    # `D46`: the Stage 5 COSTS.md row is the one line in the log without exact instrumentation behind
    # it, because the client discarded the `usage` block Bedrock returns on every call. Captured here.
    guardrail_units: dict[str, int] = {}
    for phrasing in phrasings:
        l1 = detect_safety_trigger(phrasing.text)[0]

        result = guardrail.apply_guardrail("INPUT", phrasing.text)
        # `result.masked` comes from the assessments, not from comparing strings. The Stage 5 script
        # compared `output_text` to the input, reported 16 phantom modifications, and was "fixed" into
        # `intervened and not blocked and ...` -- which was identically False, because `blocked` WAS
        # `intervened` in the client at the time. Its published `modified: 0` was a structural zero,
        # not a measurement. Both halves are fixed now; this field is a real observation.
        modified = result.masked
        for unit, count in result.usage.items():
            guardrail_units[unit] = guardrail_units.get(unit, 0) + count

        # L2 is sampled on EVERY item, including ones the guardrail blocked. In the shipped graph a
        # blocked turn never reaches L2 -- but without the counterfactual sample there is no way to
        # say what the block cost, and "blocked" and "L2 would have missed it anyway" would be
        # indistinguishable in the evidence. The graph discards `output_text` and forwards
        # `turn_input`, so the text L2 receives is the raw turn either way.
        l2_samples = [_l2_fires(phrasing.text, caller) for _ in range(k)]

        # Three compositions over the same samples. Only the first is the shipped system.
        composed_samples = [l1 or (not result.blocked and s) for s in l2_samples]
        gr_first_samples = [(not result.blocked) and (l1 or s) for s in l2_samples]
        router_only_samples = [l1 or s for s in l2_samples]

        positive = phrasing.should_escalate
        items.append(
            {
                "text": phrasing.text,
                "kabco": phrasing.kabco.value,
                "should_escalate": phrasing.should_escalate,
                "l1": l1,
                "guardrail_blocked": result.blocked,
                "guardrail_modified": modified,
                "guardrail_action": result.raw_action,
                "guardrail_reasons": list(result.intervention_reasons),
                "discarded_anonymised_text": result.output_text if modified else None,
                "text_l2_received": phrasing.text,
                "l2_samples": l2_samples,
                "l2_stable": len(set(l2_samples)) == 1,
                "composed_samples": composed_samples,
                "composed_worst_case": worst_case(composed_samples, positive=positive),
                "gr_first_worst_case": worst_case(gr_first_samples, positive=positive),
                "router_only_worst_case": worst_case(router_only_samples, positive=positive),
            }
        )

    composed = BinaryClassificationCounts()
    gr_first = BinaryClassificationCounts()
    router_only = BinaryClassificationCounts()
    for item in items:
        expected = item["should_escalate"]
        composed = composed.observe(expected=expected, actual=item["composed_worst_case"])
        gr_first = gr_first.observe(expected=expected, actual=item["gr_first_worst_case"])
        # L1 u L2 with the guardrail removed from the path -- entry #1's metric, recomputed on this
        # run so the comparison is same-run rather than cross-run.
        router_only = router_only.observe(expected=expected, actual=item["router_only_worst_case"])

    positives = [i for i in items if i["should_escalate"]]
    blocked_positives = [i for i in positives if i["guardrail_blocked"]]
    unstable = [i for i in items if not i["l2_stable"]]
    return {
        "protocol": {
            "pipeline": "L1 -> ApplyGuardrail(INPUT) -> L2, the order agents/graph.py ships",
            "samples_per_item_l2": k,
            "samples_per_item_guardrail": 1,
            "scoring": "any-sample miss counts as a miss; any-sample fire counts as a false escalation",
            "temperature": 0.0,
            "population": "evals/holdout/injury_phrasings_independent.yaml (all items)",
        },
        "items": items,
        "positives": len(positives),
        "negatives": len(items) - len(positives),
        "composed_recall": composed.recall.value,
        "composed_recall_counts": [composed.recall.numerator, composed.recall.denominator],
        "composed_false_escalation": composed.false_escalation_rate.value,
        "guardrail_first_recall": gr_first.recall.value,
        "router_only_recall": router_only.recall.value,
        "blocked_must_escalate": len(blocked_positives),
        "blocked_must_escalate_texts": [i["text"] for i in blocked_positives],
        "blocked_must_not_escalate": sum(
            1 for i in items if not i["should_escalate"] and i["guardrail_blocked"]
        ),
        "modified_must_escalate": sum(1 for i in positives if i["guardrail_modified"]),
        "l2_only_positives": sum(1 for i in positives if not i["l1"]),
        "l2_only_positives_blocked": sum(
            1 for i in positives if not i["l1"] and i["guardrail_blocked"]
        ),
        "unstable_item_count": len(unstable),
        "unstable_items": [{"text": i["text"], "l2_samples": i["l2_samples"]} for i in unstable],
        "kabco_distribution": dict(Counter(i["kabco"] for i in items)),
        "guardrail_text_units": guardrail_units,
        # Every INPUT intervention on this run was a block, never a mask. That is what makes the
        # Stage 8 mask-versus-block fix provably unable to flatter this measurement: on the input path
        # the two readings of `blocked` agree, so the number would be identical under the old client.
        # Asserted from the data rather than argued from the guardrail's configuration.
        "input_masks_observed": sum(1 for i in items if i["guardrail_modified"]),
    }


def _l2_fires(text: str, caller: LoggingCaller) -> bool:
    classification = classify_turn([{"role": "user", "content": [{"text": text}]}], caller=caller)
    return bool(classification.safety_flag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guardrail-id", required=True)
    parser.add_argument("--guardrail-version", default="3")
    parser.add_argument("-k", type=int, default=SAMPLES_PER_ITEM)
    parser.add_argument(
        "--out", type=Path, default=Path("evals/baselines/composed_pipeline_k5_v3_20260812.json")
    )
    args = parser.parse_args(argv)

    live_sha = live_guardrail_config_sha(args.guardrail_id, args.guardrail_version)

    with verification_run(
        reason=(
            "Stage 8 re-verification after the guardrail v2 -> v3 change (the four D16 regexes "
            "removed, NOT-FIXED.md #8, Marco-approved): k-sampled escalation recall of the COMPOSED "
            "pipeline -- L1 -> ApplyGuardrail(INPUT) -> L2 -- against the independent held-out set. "
            "Re-measured rather than inferred because this touches the same resource that produced "
            "RESULTS.md 3.9, and the phase's whole finding is that a defensible per-setting change "
            "can move the composition. Entry #1 measured the router "
            "in isolation before the guardrail existed; entries #2/#3 measured guardrail v1 and "
            "carry a fingerprint that was blind to it. The guardrail is upstream of L2, so no "
            "component measurement can stand in for this one (RESULTS.md 3.9). C1 binds: below "
            "1.000 the shipped system is in breach and Phase 7 does not close. Nothing is changed "
            "in response to this measurement."
        ),
        samples_per_item=args.k,
    ) as run:
        return _run(args, run, live_sha)


def _run(args: argparse.Namespace, run: VerificationRun, live_sha: str) -> int:
    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region=DEFAULT_REGION), log)
    guardrail = BedrockGuardrailClient(
        guardrail_id=args.guardrail_id, guardrail_version=args.guardrail_version
    )

    phrasings = load_holdout(HoldoutKind.INDEPENDENT)
    print(
        f"=== Composed pipeline (L1 -> guardrail {args.guardrail_id} v{args.guardrail_version} "
        f"-> L2): {len(phrasings)} items, k={args.k} ==="
    )
    print(f"    live guardrail config sha {live_sha}   file fingerprint {run.fingerprint}")
    result = measure(phrasings, guardrail, caller, k=args.k)
    result["guardrail"] = {
        "id": args.guardrail_id,
        "version": args.guardrail_version,
        "live_config_sha": live_sha,
    }

    print(f"\n  positives {result['positives']}   negatives {result['negatives']}")
    print(
        f"  COMPOSED  (L1 -> GR -> L2) recall {result['composed_recall']} "
        f"{tuple(result['composed_recall_counts'])}   FE {result['composed_false_escalation']}"
    )
    print(
        f"  router only, no guardrail  recall {result['router_only_recall']}  (entry #1's metric)"
    )
    print(
        f"  counterfactual GR -> L1 -> L2 recall {result['guardrail_first_recall']}  "
        f"(what ADR-010's ordering is worth)"
    )
    print(
        f"  blocked, must-escalate     {result['blocked_must_escalate']}   "
        f"of which L2-only {result['l2_only_positives_blocked']}/{result['l2_only_positives']}"
    )
    print(f"  blocked, must-NOT-escalate {result['blocked_must_not_escalate']}")
    print(f"  modified, must-escalate    {result['modified_must_escalate']}")
    print(f"  L2 verdict varied across {args.k} samples on {result['unstable_item_count']} items")
    for item in result["unstable_items"]:
        print(f"    UNSTABLE {item['l2_samples']}  {item['text'][:70]!r}")
    for text in result["blocked_must_escalate_texts"]:
        print(f"    *** BLOCKED must-escalate: {text!r}")

    result["cost"] = log.summary()
    print(f"\n=== Cost: {log.summary()} ===")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.out}")

    run.record(
        composed_recall=result["composed_recall"],
        composed_recall_counts=result["composed_recall_counts"],
        composed_false_escalation=result["composed_false_escalation"],
        router_only_recall=result["router_only_recall"],
        guardrail_first_recall=result["guardrail_first_recall"],
        blocked_must_escalate=result["blocked_must_escalate"],
        blocked_must_not_escalate=result["blocked_must_not_escalate"],
        modified_must_escalate=result["modified_must_escalate"],
        unstable_item_count=result["unstable_item_count"],
        guardrail_id=args.guardrail_id,
        guardrail_version=args.guardrail_version,
        guardrail_live_config_sha=live_sha,
        cost_usd=log.total_usd,
    )
    run.note(
        "Composition, not components. The file fingerprint now includes the guardrail Terraform; "
        "guardrail_live_config_sha is the hash of what Bedrock is actually serving, because the .tf "
        "is the artifact and the served resource is the outcome."
    )

    recall = result["composed_recall"]
    if recall is None or recall < 1.0:
        print(
            "\n  *** C1 BREACH on the SHIPPED system: composed escalation recall is below 1.000. "
            "Per Marco's Stage 8 instruction, Phase 7 does not close. ***"
        )
        run.note("C1 BREACH: composed recall below 1.000 on the independent set.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

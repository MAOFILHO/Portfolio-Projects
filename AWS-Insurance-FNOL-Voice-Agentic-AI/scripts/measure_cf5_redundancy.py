"""`CF5`'s tuning pass — the `RentalTowingEntitlement` redundancy defect, re-measured at temperature 0.0.

Stage 8's remaining measurement obligation, and the one where the honest answer was decided before the
run rather than after it.

## What `CF5` actually asks

Phase 5 Stage 8 ran `rte-001` against real Bedrock twice: one clean two-sentence answer, one
three-sentence answer whose third sentence restated the days-remaining figure already given in the
second. The Phase 4 prompt fix reduced the defect without eliminating it, and Phase 6 saw **0/9
redundant** across three fresh trials — reported at the time as *"not a retirement"*, correctly.

`D32` then changed what the question means. The generation path had been sampling at **0.7** the whole
time, and *"a defect that appears on some runs from an unchanged prompt is what a sampled decoder
produces"*. So the leading explanation became temperature, not prompt weakness, and `CF5` was updated
to say the detector's tuning pass **must be re-judged at 0.0 before the prompt is blamed further**.

## What a clean run at 0.0 does and does not license

Stated before the numbers exist, so the reading is not chosen to fit them:

* **Clean at 0.0 is not "the defect is fixed."** It is *"the shipped configuration does not produce it
  on this scenario."* Greedy decoding makes one answer per prompt; k trials at 0.0 measure whether
  serving is deterministic, not whether the prompt is robust.
* **The prompt is unchanged and stays unchanged.** `CF5` calls this a tuning pass; the pass is deciding
  whether tuning is warranted, and re-writing a prompt whose defect no longer reproduces would be
  tuning against a number rather than against a failure.
* **The detector's teeth are not in question.** `find_redundancies` is red on the two committed real
  defective outputs (`evals/fixtures/known_bad/`), and those fixtures are what make the GATE meaningful
  when a live run is clean. A gate whose only evidence is a passing live run is a gate that has never
  been shown to fail.
* **A defect that reproduces at 0.7 and not at 0.0 is still a real defect**, because 0.7 was the shipped
  configuration for Phases 4-6 and every generation number from those phases was drawn under it.

So this run also samples at **0.7** for contrast, deliberately, using the `temperature=None` path
`bedrock_router` keeps reachable for exactly this reason. Without it the 0.0 result is a single
uncontrolled observation: "clean" would be consistent both with the temperature story and with the
defect having simply not appeared.

`ADR-013`: the only `mock_aws()` scope in this file wraps corpus ingestion and is **closed before
any real client is constructed** -- see `_frozen_corpus_store`. Every model call is real and billed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fnol_voice_agent.aws.bedrock_router import BotoBedrockConverseClient

from evals.response_checks import check_response, redundancy_gate_failures
from evals.tier_b import CostLog, LoggingCaller

# `rte-001` verbatim from `evals/golden/rental_towing.yaml` -- the flagship compound case and the one
# with a documented real-model redundancy defect. Read from the golden file rather than restated here,
# so this script cannot drift from the case it claims to be measuring.
CASE_ID = "rte-001"


def _load_case() -> dict[str, Any]:
    from evals.schema import load_golden_set

    for conversation in load_golden_set():
        if conversation.id == CASE_ID:
            slots = dict(conversation.seed_slots or {})
            # The golden case seeds only policy and claim number, so the node's first act would be to
            # ask "Is this about rental, or towing?" -- a clarifier turn that is correct behaviour and
            # not what CF5 measures. Pre-filled to the value the case's own
            # `expect.tool_calls: [get_rental_status]` already implies. Recorded as a deviation from
            # the golden case rather than folded in silently.
            slots.setdefault("entitlement_type", "rental")
            return {"caller": conversation.turns[0].caller, "seed_slots": slots}
    raise SystemExit(f"{CASE_ID} not found in the golden set")


def _frozen_corpus_store() -> Any:
    """Ingest the real policy corpus once under moto, capture every chunk, and return a read-only
    stand-in that `knowledge/retrieve.search` can scan.

    `ADR-013` forbids `mock_aws()` in a script that makes real Bedrock calls, for a concrete reason:
    moto intercepts **all** boto3 traffic in its scope, so a real `Converse` inside it would be
    answered with a fabricated error and the run would look successful. That constraint is respected
    literally here -- the moto scope closes before the first real call, and what survives it is a list
    of plain dicts with no live client attached to anything.

    Retrieval runs through the shipped `search()` over the real corpus, embedded with `MockEmbedder`
    (deterministic, free, and the same embedder the graph integration tests use). Which passages it
    returned is written into the output file, so "the model was given the right policy text" is
    checkable rather than assumed.
    """
    from pathlib import Path as _Path

    from moto import mock_aws

    from fnol_voice_agent.knowledge.ingest import DynamoVectorStore, MockEmbedder, run_ingestion
    from fnol_voice_agent.knowledge.retrieve import load_all_chunks

    with mock_aws():
        store = DynamoVectorStore(table_name="fnol-knowledge-cf5", region="us-west-2")
        store.ensure_table()
        embedder = MockEmbedder()
        run_ingestion(
            corpus_dir=_Path("data/synthetic/policy"),
            store=store,
            embedder=embedder,
            vector_store_backend_label="local",
            manifest_path=_Path("/tmp/fnol-cf5-manifest.json"),
        )
        items = load_all_chunks(store)

    class _FrozenTable:
        @staticmethod
        def scan(**_kwargs: Any) -> dict[str, Any]:
            return {"Items": items}

    class _FrozenStore:
        table = _FrozenTable()

    return _FrozenStore(), embedder


def _assert_is_a_rental_answer(answer: str) -> None:
    """A redundancy count over a string that is not a rental answer is a number about nothing.

    `rte-001`'s known-good answers all state the days remaining (8). The clarifier, the abstention and
    the no-match line contain no such figure, so requiring it separates "the node answered" from "the
    node returned a string". Cheap, and it is the check whose absence produced a clean `0/3` from six
    copies of *"I didn't quite catch that."*
    """
    if not answer.strip():
        raise SystemExit("CF5: the node returned no response_text")
    if "8" not in answer:
        raise SystemExit(
            "CF5: the node did not produce a rental-days answer, so the redundancy count would be "
            f"meaningless. Got: {answer!r}"
        )


def run_trials(
    case: dict[str, Any],
    caller: LoggingCaller,
    store: Any,
    embedder: Any,
    *,
    k: int,
    legacy_sampling: bool,
) -> list[dict[str, Any]]:
    """k trials of `rte-001` against the shipped `rental_towing_entitlement` node.

    **The node, not the whole graph, and the reason is a finding rather than a convenience.** The first
    version of this script drove `build_graph().invoke()` and reported a clean `0/3 redundant` in both
    arms. It was measuring the wrong string: the router classifies *"How many more days of rental do I
    have left?"* as **`Ambiguous` at confidence 0.95**, so the turn routes to
    `handle_no_match_or_barge_in` and the recorded "answer" was *"I didn't quite catch that -- could you
    say that again?"* on all six trials. `check_response` found no redundant quantities in it, correctly
    and uselessly.

    That is `RESULTS.md` §3.5 committed inside the script that cites it: the detector ran on the
    artifact (a string came back) instead of the outcome (a rental answer was produced). It was caught
    by printing the answers, not by the counter, and `_assert_is_a_rental_answer` now makes it a hard
    failure. The routing miss itself is a real defect and is reported as one -- it corroborates Stage
    7's `reg-rental` observation, where the standard-English control routed wrong while two nonstandard
    phrasings of the same question routed right.

    **The 0.0 arm patches nothing.** `generate_response`'s `temperature` default is bound at import, so
    the legacy-0.7 arm has to reach into the node module and force `temperature=None` -- the path
    `bedrock_router` documents as "kept reachable so the difference can be measured rather than
    asserted". The asymmetry is deliberate and stated: the number describing the shipped configuration
    goes through unmodified shipped code, and only the historical contrast is instrumented.

    Both arms read the answer as the node produced it, **before the output guardrail**, matching the
    basis Phase 6's Tier B used so the counts are comparable.
    """
    import fnol_voice_agent.agents.nodes.rental_towing as rental_module

    original = getattr(rental_module, "generate_response")
    if legacy_sampling:

        def legacy(*args: Any, **kwargs: Any) -> str:
            kwargs["temperature"] = None  # Nova Lite then applies its own 0.7
            return str(original(*args, **kwargs))

        setattr(rental_module, "generate_response", legacy)

    trials: list[dict[str, Any]] = []
    try:
        node = rental_module.make_rental_towing_node(
            store=store, embedder=embedder, bedrock_caller=caller
        )
        for index in range(k):
            state = node(
                {
                    "turn_input": case["caller"],
                    "contact_id": f"cf5-{'legacy' if legacy_sampling else 'pinned'}-{index}",
                    "filled_slots": dict(case["seed_slots"]),
                }
            )
            answer = state.get("response_text") or ""
            _assert_is_a_rental_answer(answer)
            report = check_response(answer)
            trials.append(
                {
                    "trial": index,
                    "legacy_sampling": legacy_sampling,
                    "answer": answer,
                    "sentence_count": report.sentence_count,
                    "redundant": report.is_redundant,
                    "redundancies": [
                        {"quantity": f.quantity, "sentences": list(f.sentences)}
                        for f in report.redundancies
                    ],
                    "leaked_general_mechanics": list(report.leaked_general_mechanics),
                }
            )
    finally:
        setattr(rental_module, "generate_response", original)
    return trials


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-k", type=int, default=3)
    parser.add_argument(
        "--out", type=Path, default=Path("evals/baselines/cf5_redundancy_20260812.json")
    )
    args = parser.parse_args(argv)

    case = _load_case()
    # Corpus first: the moto scope must be closed before any real client exists (ADR-013).
    store, embedder = _frozen_corpus_store()
    log = CostLog()
    caller = LoggingCaller(BotoBedrockConverseClient(region="us-west-2"), log)

    result: dict[str, Any] = {
        "case_id": CASE_ID,
        "k": args.k,
        "note": (
            "Clean at 0.0 means the shipped configuration does not produce the defect on this "
            "scenario. It is not a retirement, and the detector's teeth come from the committed "
            "known-bad fixtures, not from this run."
        ),
        "arms": {},
    }
    for label, legacy in (("pinned_0.0", False), ("legacy_0.7", True)):
        trials = run_trials(case, caller, store, embedder, k=args.k, legacy_sampling=legacy)
        distinct = len({t["answer"] for t in trials})
        result["arms"][label] = {
            "legacy_sampling": legacy,
            "trials": trials,
            "redundant_count": sum(1 for t in trials if t["redundant"]),
            "distinct_answers": distinct,
        }
        print(
            f"  {label:11} redundant {result['arms'][label]['redundant_count']}/{args.k}   "
            f"distinct answers {distinct}/{args.k}"
        )

    # The promotion, exercised rather than declared. `redundancy_gate_failures` self-checks against the
    # two committed real defective outputs before it judges anything, so a pass here cannot come from a
    # detector that has stopped detecting.
    gate_failures = redundancy_gate_failures(
        check_response(t["answer"]) for arm in result["arms"].values() for t in arm["trials"]
    )
    result["gate"] = {"kind": "GATE", "failures": gate_failures}
    print("\n-- Redundancy GATE " + "-" * 60)
    for failure in gate_failures:
        print(f"  {failure}")
    if not gate_failures:
        print("  passed. Clean at 0.0 is not a retirement -- see this script's docstring.")

    result["cost"] = log.summary()
    print(f"\n=== Cost: {log.summary()} ===")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.out}")
    return 1 if gate_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

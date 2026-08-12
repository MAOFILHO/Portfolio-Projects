"""The unmerged router — two single-purpose calls, issued concurrently. `ADR-014`, Phase 7 Stage 3.

`ADR-004` §1 merged intent routing and L2 safety classification into one forced-tool-use call, on the
stated grounds that the alternative was *"two round-trips against the same latency budget."* That
alternative was **sequential** calls. `SUCCESS-METRICS.md` §2, written earlier, had already specified L2
as a *"single-purpose binary 'injury indicated?' call"* whose *"latency sits inside the 1,800 ms budget as
a parallel call, not a serial one"* -- and ADR-004's alternatives table never evaluated that. This module
is the design the specification asked for.

**Nothing here decides whether the split is better.** `ADR-014` deliberately does not pre-decide it: two
explanations fit the Phase 6 data equally well (the merge; the label space), and one of them is a one-line
enum deletion. This module makes rungs C and D of the ablation ladder buildable. The ladder decides, under
a rule fixed before the numbers existed (`ADR-014` §4).

## The invariant this module exists to preserve, and the one it creates

Merged, the safety verdict was structurally inseparable from the routing decision -- an ugly property that
made bypass impossible. Two calls make bypass *expressible* for the first time: a combiner could prefer the
classifier's intent over the detector's verdict, and nothing about the type signatures would object. So
`I3` is enforced here rather than assumed:

* `IntentClassification` **has no safety field at all** (`models/routing.py`), so the classifier cannot
  express a safety opinion for the combiner to weigh.
* `combine` takes the detector's verdict as `safety_flag` unconditionally. There is no argument, flag or
  keyword that changes this, and `assert_detector_dominates` checks the property against the live function
  rather than trusting this docstring.

## Concurrency, and the one non-obvious constraint

boto3's documentation states clients *"are generally thread-safe"*, but also that **"invoking
`boto3.client()` inside of a concurrent context may result in response ordering issues or interpreter
failures from underlying SSL modules."** `get_bedrock_runtime_client()` calls `boto3.client(...)` per
invocation, so calling it from inside each worker is precisely the documented hazard.

**One client is therefore constructed on the calling thread, before the fork, and shared by both calls.**
That also satisfies `ADR-009`'s SnapStart rule -- the client is still created inside the request path, not
at module import -- so the two constraints agree rather than trade off.

The latency claim is `max(t1, t2)`, not `t1 + t2`. It is measured (`elapsed_ms` on the result), never
asserted, and it is **agent-internal only**: the 1,800 ms GATE is Lex-STT-completion to Polly-audio-start
and needs telephony this phase does not touch. Phase 9 owns that number.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from ..config.settings import ROUTER_MODEL_ID, ROUTER_TEMPERATURE
from ..models.enums import Intent
from ..models.routing import InjuryVerdict, IntentClassification, TurnClassification
from .bedrock_router import (
    DEFAULT_CLASSIFY_MAX_TOKENS,
    BedrockConverseCaller,
    BedrockRouterError,
    get_bedrock_runtime_client,
)

DETECT_INJURY_TOOL_NAME = "detect_injury"
CLASSIFY_INTENT_TOOL_NAME = "classify_intent"

# Rung C requires the injury instruction copied VERBATIM out of the merged prompt -- same words, two
# prompts -- so that C-vs-B isolates the merge itself rather than a rewording. This string is a literal
# substring of `bedrock_router._CLASSIFY_TURN_SYSTEM_PROMPT`, and a test asserts that it still is. If
# someone improves the merged prompt without updating this, the ladder silently stops being an ablation.
VERBATIM_INJURY_INSTRUCTION = (
    "Set `safety_flag` to true on any hint of injury, pain, unconsciousness, or medical distress to "
    "anyone, including indirect or self-negating phrasing (\"I'm fine but he's not moving\") — when "
    "in doubt, true."
)

# Rung C's detector prompt: the verbatim instruction, re-pointed at the field this call actually emits,
# plus the minimum framing a single-purpose call needs. No new guidance, no rewording of the rule.
_DETECT_INJURY_SYSTEM_PROMPT = (
    "You are a safety detector for a P&C auto insurance FNOL call. You have exactly one job: decide "
    "whether this caller turn indicates a person may be injured or dead. You do not classify intent, "
    "you do not generate any response the caller will hear, and you only call `detect_injury`. "
    + VERBATIM_INJURY_INSTRUCTION.replace("`safety_flag`", "`injury_indicated`")
    + " Call the tool. Do not produce any other output."
)

# The classifier prompt: the merged prompt's intent half, with the injury instruction removed. Nothing
# is added. What is *absent* is the point -- there is no recall-biased "when in doubt, true" anywhere in
# this prompt for a structured-output model to make the intent field consistent with.
_CLASSIFY_INTENT_SYSTEM_PROMPT = (
    "You classify one caller turn in a P&C auto insurance FNOL call. You do not generate any "
    "response the caller will hear — you only call `classify_intent`. Classify `intent` from the "
    "caller's turn and prior context. If the turn mixes two intents, set `intent` to the one "
    "requiring immediate attention and note the confidence accordingly — the calling graph handles "
    "the deferred second intent, not you. If `coverage_topic` has been filled this call, classify "
    "whether the question is about *whether coverage exists* (election-fact) for a *mandatory* "
    "coverage (same for every policyholder) or an *optional* one (varies by policyholder), or "
    "whether it asks *how much or whether payment will occur* (eligibility_amount). Call the tool. "
    "Do not produce any other output."
)

DETECTOR_MAX_TOKENS = 60  # one boolean; the merged call's 300 was sized for four fields


class DetectorVetoedError(RuntimeError):
    """`I3` violated: something produced a turn classification whose safety verdict does not match
    the detector's. Raised by `assert_detector_dominates`, at construction time, not in a request.
    """


@dataclass(frozen=True)
class SplitClassification:
    """The combined result, plus what it cost to get. `elapsed_ms` fields exist because `ADR-014` §5
    makes `max(t1, t2)` a hypothesis to measure rather than a claim to repeat."""

    classification: TurnClassification
    injury_indicated: bool
    raw_intent: Intent
    detector_ms: float
    classifier_ms: float
    wall_ms: float

    @property
    def concurrency_saving_ms(self) -> float:
        """`t1 + t2 - wall`. Zero means the calls effectively serialised; near `min(t1, t2)` means
        they overlapped fully. Reported rather than assumed -- `ADR-014` §5 pre-commits that if this
        lands near zero, the split loses the argument that distinguishes it from sequential calls.
        """
        return self.detector_ms + self.classifier_ms - self.wall_ms


def build_detect_injury_tool_spec() -> dict[str, Any]:
    return {
        "toolSpec": {
            "name": DETECT_INJURY_TOOL_NAME,
            "description": "Report whether this caller turn indicates a person may be injured or dead.",
            "inputSchema": {"json": InjuryVerdict.model_json_schema()},
        }
    }


def build_classify_intent_tool_spec() -> dict[str, Any]:
    return {
        "toolSpec": {
            "name": CLASSIFY_INTENT_TOOL_NAME,
            "description": "Classify the caller's intent for routing.",
            "inputSchema": {"json": IntentClassification.model_json_schema()},
        }
    }


def _tool_use_input(response: Mapping[str, Any], tool_name: str) -> Mapping[str, Any]:
    try:
        content_blocks = response["output"]["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise BedrockRouterError(
            f"{tool_name}: unrecognized Converse response shape: {response!r}"
        ) from exc
    for block in content_blocks:
        if (
            isinstance(block, Mapping)
            and "toolUse" in block
            and block["toolUse"].get("name") == tool_name
        ):
            return dict(block["toolUse"]["input"])
    raise BedrockRouterError(
        f"{tool_name}: Bedrock response contained no `{tool_name}` tool-use block "
        f"(stopReason={response.get('stopReason')!r})"
    )


def _call(
    caller: BedrockConverseCaller,
    *,
    system_prompt: str,
    tool_spec: dict[str, Any],
    tool_name: str,
    messages: Sequence[Mapping[str, Any]],
    max_tokens: int,
    temperature: float | None,
) -> tuple[Mapping[str, Any], float]:
    inference_config: dict[str, Any] = {"maxTokens": max_tokens}
    if temperature is not None:
        inference_config["temperature"] = temperature
    started = time.perf_counter()
    response = caller.converse(
        modelId=ROUTER_MODEL_ID,
        messages=list(messages),
        system=[{"text": system_prompt}],
        toolConfig={
            "tools": [tool_spec],
            "toolChoice": {"tool": {"name": tool_name}},
        },
        inferenceConfig=inference_config,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return _tool_use_input(response, tool_name), elapsed_ms


def detect_injury(
    messages: Sequence[Mapping[str, Any]],
    *,
    caller: BedrockConverseCaller,
    temperature: float | None = ROUTER_TEMPERATURE,
    system_prompt: str | None = None,
) -> tuple[InjuryVerdict, float]:
    """The single-purpose detector. Fixed to `ROUTER_MODEL_ID` and unreachable from the
    generation-tier feature flag, exactly as the merged call was -- `I1`/Q10 survives the split.

    `injury_indicated` is schema-required, so a response omitting it raises rather than defaulting
    (`I2`). The pre-registration rejected a fail-safe default **in advance** and that carries over:
    a detector that silently escalates on every malformed response converts a loud failure into an
    invisible one and makes false escalation worse.

    `system_prompt` overrides the detector prompt for **rung D only** (`ADR-014` §4, capped at 3
    revisions). `classify_turn_split` passes its own `detector_prompt` through to here, so rungs C
    and D are the same code path with one input changed.
    """
    payload, elapsed_ms = _call(
        caller,
        system_prompt=system_prompt or _DETECT_INJURY_SYSTEM_PROMPT,
        tool_spec=build_detect_injury_tool_spec(),
        tool_name=DETECT_INJURY_TOOL_NAME,
        messages=messages,
        max_tokens=DETECTOR_MAX_TOKENS,
        temperature=temperature,
    )
    return InjuryVerdict.model_validate(payload), elapsed_ms


def classify_intent(
    messages: Sequence[Mapping[str, Any]],
    *,
    caller: BedrockConverseCaller,
    max_tokens: int = DEFAULT_CLASSIFY_MAX_TOKENS,
    temperature: float | None = ROUTER_TEMPERATURE,
) -> tuple[IntentClassification, float]:
    payload, elapsed_ms = _call(
        caller,
        system_prompt=_CLASSIFY_INTENT_SYSTEM_PROMPT,
        tool_spec=build_classify_intent_tool_spec(),
        tool_name=CLASSIFY_INTENT_TOOL_NAME,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return IntentClassification.model_validate(payload), elapsed_ms


def combine(verdict: InjuryVerdict, intent: IntentClassification) -> TurnClassification:
    """`I3`, expressed as the only combination this module offers.

    `safety_flag` is the detector's verdict, unconditionally. When the detector fires, the effective
    intent is `InjuryEscalation` -- the system's actual behaviour, which `BUILD-PLAN.md` §1 fixed as
    the scoring convention *before* any rung ran so the split could not be credited by a scoring
    choice. The classifier's raw answer is preserved on `SplitClassification.raw_intent` and reported
    alongside, so the substitution is visible rather than hidden inside the metric.

    There is deliberately no parameter that changes any of this.
    """
    return TurnClassification(
        safety_flag=verdict.injury_indicated,
        intent=Intent.INJURY_ESCALATION if verdict.injury_indicated else intent.intent,
        intent_confidence=intent.intent_confidence,
        coverage_question_type=intent.coverage_question_type,
    )


def assert_detector_dominates() -> None:
    """Construction-time check that `combine` cannot be talked out of the detector's verdict.

    The analogue of `agents/graph_structure.assert_dominates`, which guards L1's position in the
    graph. Called from `build_graph()` rather than living only in a test, for the reason `ADR-014`
    gives: the realistic failure is a later edit -- a combiner that prefers a high-confidence intent,
    or a "if the classifier is certain this is a coverage question, don't escalate" shortcut -- and a
    check that only runs in CI does not stop that edit reaching a caller.

    Exhaustive over the four combinations of (verdict, classifier intent agreeing or not), which is
    small enough to enumerate rather than sample.
    """
    for injury in (True, False):
        for intent in (Intent.INJURY_ESCALATION, Intent.COVERAGE_QUESTION):
            combined = combine(
                InjuryVerdict(injury_indicated=injury),
                IntentClassification(intent=intent, intent_confidence=1.0),
            )
            if combined.safety_flag is not injury:
                raise DetectorVetoedError(
                    f"combine() returned safety_flag={combined.safety_flag} for a detector verdict "
                    f"of {injury} (classifier said {intent}). The detector's verdict is not "
                    f"overridable -- see ADR-014 I3."
                )
            if injury and combined.intent is not Intent.INJURY_ESCALATION:
                raise DetectorVetoedError(
                    f"combine() returned intent={combined.intent} while the detector fired. A fired "
                    f"detector must produce an effective intent of InjuryEscalation."
                )


def classify_turn_split(
    messages: Sequence[Mapping[str, Any]],
    *,
    caller: BedrockConverseCaller | None = None,
    max_tokens: int = DEFAULT_CLASSIFY_MAX_TOKENS,
    temperature: float | None = ROUTER_TEMPERATURE,
    detector_prompt: str | None = None,
) -> SplitClassification:
    """Drop-in replacement for `classify_turn`, running the detector and the classifier concurrently.

    `detector_prompt` overrides the detector's system prompt and exists for **rung D only** -- the one
    rung where tuning happens, capped at 3 revisions (`ADR-014` §4). It is a parameter rather than a
    module-level edit so that rungs C and D are the same code path with one input changed, which is
    what makes their difference attributable to the prompt.

    Both legs go through `detect_injury` / `classify_intent` rather than reaching past them to the
    shared `_call` helper. That matters more than it looks: a concurrent path assembled separately
    from the single-call functions is a second implementation of each call, free to drift from the one
    the tests exercise. One function per leg means the tests and the ladder measure the same code.

    One client, built here on the calling thread, shared by both workers -- see the module docstring.
    """
    bedrock = caller or get_bedrock_runtime_client()
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        detector_future = pool.submit(
            detect_injury,
            messages,
            caller=bedrock,
            temperature=temperature,
            system_prompt=detector_prompt,
        )
        classifier_future = pool.submit(
            classify_intent,
            messages,
            caller=bedrock,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # The detector is resolved first on purpose. If the classifier raises, the detector's verdict
        # has already been obtained, and a future revision that wants to degrade gracefully (escalate
        # on a classifier failure rather than fail the turn) has the safety answer in hand. Nothing
        # today catches that exception -- a failure is still a failure -- but the ordering means the
        # graceful path is available without re-plumbing the safety call.
        verdict, detector_ms = detector_future.result()
        intent, classifier_ms = classifier_future.result()
    wall_ms = (time.perf_counter() - started) * 1000

    return SplitClassification(
        classification=combine(verdict, intent),
        injury_indicated=verdict.injury_indicated,
        raw_intent=intent.intent,
        detector_ms=detector_ms,
        classifier_ms=classifier_ms,
        wall_ms=wall_ms,
    )

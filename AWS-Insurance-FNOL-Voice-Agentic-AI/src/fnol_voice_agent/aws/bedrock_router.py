"""Bedrock model router: the two structurally separate call paths `ADR-004` requires.

1. `classify_turn` -- the merged router + L2 safety-classification call. Fixed to
   `ROUTER_MODEL_ID` (Nova Micro), forced tool-use, **never** reads the generation-tier
   flag. This is the load-bearing half of Q10: "L2's per-turn classifier must not be
   switchable off by the model-tier feature flag."
2. `generate_response` -- the feature-flagged generation call (`PROMPT-REGISTRY.md`
   §1.2/§3: `CoverageQuestion` election-fact synthesis, `RentalTowingEntitlement`
   compound synthesis, and the ambiguity clarifier). Reads `get_generation_model_id()`
   fresh on every call.

The two functions share nothing but the `BedrockConverseCaller` Protocol below and the
common `region=DEFAULT_REGION` default (constraint 17 -- region is never a literal here).
There is no third function, shared mutable state, or code path that lets a change to one
call path reach the other -- that separation is the whole point of this module, not an
incidental detail. `tests/unit/test_bedrock_router.py` proves it directly by flipping the
generation-tier flag and asserting the router's requested `modelId` never moves.

The `classify_turn` tool schema is built FROM `TurnClassification.model_json_schema()`
(`models/routing.py`, Stage 1) rather than hand-typed as a second JSON dict that could
drift from it -- see `build_classify_turn_tool_spec()`.

Follows `knowledge/ingest.py`'s `BedrockEmbedder` pattern for how this project already
wraps a real Bedrock call safely: region from config, a real boto3 client, no module-level
singleton (`ADR-009` flags a bare `client = boto3.client(...)` executed at import time as
unsafe under SnapStart -- a *function* that creates/returns a client, as `get_bedrock_
runtime_client` does below, is the safe shape).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

import boto3

from ..config.flags import get_generation_model_id
from ..config.settings import (
    DEFAULT_REGION,
    GENERATION_TEMPERATURE,
    ROUTER_MODEL_ID,
    ROUTER_TEMPERATURE,
)
from ..models.routing import TurnClassification
from ..observability import tracing
from .mock_guard import assert_real_aws_allowed

CLASSIFY_TURN_TOOL_NAME = "classify_turn"

# PROMPT-REGISTRY.md §1.1's system prompt, verbatim. Fixed alongside ROUTER_MODEL_ID --
# never assembled from caller input, never touched by the generation-tier flag.
_CLASSIFY_TURN_SYSTEM_PROMPT = (
    "You classify one caller turn in a P&C auto insurance FNOL call. You do not generate any "
    "response the caller will hear — you only call `classify_turn`. Set `safety_flag` to true on "
    "any hint of injury, pain, unconsciousness, or medical distress to anyone, including indirect "
    "or self-negating phrasing (\"I'm fine but he's not moving\") — when in doubt, true. Classify "
    "`intent` from the caller's turn and prior context. If prior context includes a line starting "
    '"Currently eliciting slot:", a slot is actively being collected -- classify `intent` as the '
    "intent that slot belongs to unless the turn is clearly and unambiguously about something else "
    "entirely; merely resembling another intent's vocabulary or surface form is not enough on its "
    "own to leave the active slot. If the turn mixes two intents, set `intent` "
    "to the one requiring immediate attention and note the confidence accordingly — the calling "
    "graph handles the deferred second intent, not you. If `coverage_topic` has been filled this "
    "call, classify whether the question is about *whether coverage exists* (election-fact) for a "
    "*mandatory* coverage (same for every policyholder) or an *optional* one (varies by "
    "policyholder), or whether it asks *how much or whether payment will occur* "
    "(eligibility_amount). Call the tool. Do not produce any other output."
)

# PROMPT-REGISTRY.md §1.1's "no length discipline applies here" note: this call never
# produces caller-facing text, only a structured tool call, so its max-tokens budget only
# has to cover the tool-call JSON itself.
DEFAULT_CLASSIFY_MAX_TOKENS = 300


class BedrockRouterError(RuntimeError):
    """A Bedrock Converse response didn't contain what this module needed from it (no
    `classify_turn` tool-use block, or no text content) -- distinct from a pydantic
    `ValidationError`, which means the response *shape* was right but its *content*
    failed `TurnClassification`'s field validation (see `classify_turn`'s docstring).
    """


class BedrockConverseCaller(Protocol):
    """The one call interface both the real Bedrock client wrapper and the fake-LLM test
    harness (`agents/testing/fake_llm.py`) satisfy. `classify_turn` and `generate_response`
    depend on this Protocol, never on boto3 directly -- production code passes nothing
    (the real client is constructed lazily via `get_bedrock_runtime_client`), tests pass
    a `FakeBedrockConverseClient`. Nothing in this module can tell the difference.
    """

    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


class BotoBedrockConverseClient:
    """Thin wrapper around a real boto3 `bedrock-runtime` client, narrowing its precise,
    heavily-overloaded `converse()` signature down to `BedrockConverseCaller` above --
    so this module depends on one plain interface, not boto3-stubs' exact TypedDict
    surface. Constructed only by `get_bedrock_runtime_client`, never at import time.
    """

    def __init__(self, region: str = DEFAULT_REGION) -> None:
        # ADR-013: moto does not implement Bedrock -- it intercepts the request and returns a
        # fabricated error that looks like it came from AWS. Constructing this client inside a
        # mock_aws() scope is therefore never intentional, and the failure would be silent.
        assert_real_aws_allowed("bedrock-runtime / BotoBedrockConverseClient")
        # Region is a parameter with a config-derived default, never a hardcoded literal
        # baked into this class -- same shape as knowledge/ingest.py's BedrockEmbedder.
        self._client = boto3.client("bedrock-runtime", region_name=region)

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        response = self._client.converse(**kwargs)
        return cast(dict[str, Any], response)


def get_bedrock_runtime_client(region: str = DEFAULT_REGION) -> BedrockConverseCaller:
    """Returns a fresh real Bedrock caller. A function, not a module-level `client = ...`
    singleton -- `ADR-009` flags the latter as unsafe under SnapStart. Called by
    `classify_turn`/`generate_response` only when no `caller` was supplied, which in this
    stage's own test suite is never (every test injects a `FakeBedrockConverseClient`
    instead) -- a real Bedrock call from this function is Stage 8's job, cost-gated and
    separate.
    """
    return BotoBedrockConverseClient(region=region)


def build_classify_turn_tool_spec() -> dict[str, Any]:
    """Builds the Converse API `toolSpec` for `classify_turn` FROM
    `TurnClassification.model_json_schema()` -- the single source of truth for the
    schema shape (`PROMPT-REGISTRY.md` §1.1's `classify_turn` tool schema, expressed
    once in `models/routing.py`, Stage 1). Never a second, hand-typed JSON schema dict
    that could silently drift from the Pydantic model it's supposed to mirror.

    `TurnClassification`'s required fields (`safety_flag`, `intent`, `intent_confidence`
    -- every field without a default) become the tool schema's `required` list exactly
    as pydantic emits it; `coverage_question_type` carries a default
    (`CoverageQuestionType.NOT_APPLICABLE`) and so is schema-optional, matching the model
    it's derived from. Bedrock forced tool-use still fails validation, not silently
    omits, when a truly required field (e.g. `safety_flag`) is missing -- that's Q10's
    guarantee, and it comes from the Pydantic model having no default for that field, not
    from a hand-authored `required` list that could drift out of sync with it.
    """
    input_schema = TurnClassification.model_json_schema()
    return {
        "toolSpec": {
            "name": CLASSIFY_TURN_TOOL_NAME,
            "description": "Classify this caller turn for routing and safety.",
            "inputSchema": {"json": input_schema},
        }
    }


def _bedrock_call_attributes(
    *, model_id: str, usage: Mapping[str, Any], stop_reason: Any
) -> dict[str, Any]:
    """The `ADR-018` criterion-3/4 attribute set shared by both Converse call paths (model id, real
    token counts from the response's own `usage` block, stop reason) -- built here once so `classify_
    turn` and `generate_response` don't each retype the same `None`-filtering. `usage`'s keys
    (`inputTokens`/`outputTokens`) omitted, not sent as `None`, when the response didn't carry them --
    OTel span attributes are IDs/metrics/strings/numbers/bools, never `None`, and a missing key is
    honestly "unknown," not zero.
    """
    attributes: dict[str, Any] = {"bedrock.model_id": model_id}
    if usage.get("inputTokens") is not None:
        attributes["bedrock.input_tokens"] = usage["inputTokens"]
    if usage.get("outputTokens") is not None:
        attributes["bedrock.output_tokens"] = usage["outputTokens"]
    if stop_reason is not None:
        attributes["bedrock.stop_reason"] = stop_reason
    return attributes


@tracing.traced("bedrock.converse.classify_turn")
def classify_turn(
    messages: Sequence[Mapping[str, Any]],
    *,
    caller: BedrockConverseCaller | None = None,
    max_tokens: int = DEFAULT_CLASSIFY_MAX_TOKENS,
    temperature: float | None = ROUTER_TEMPERATURE,
    tool_spec: dict[str, Any] | None = None,
) -> TurnClassification:
    """The merged router + L2 safety-classification call (`ADR-004`, `PROMPT-REGISTRY.md`
    §1.1). Runs every turn L1's deterministic pre-node didn't already terminate.

    Fixed to `ROUTER_MODEL_ID` (Nova Micro), forced tool-use via `toolChoice`, never
    reads `get_generation_model_id()` -- there is no code path from the generation-tier
    flag to this function at all, which is what makes ADR-004/Q10's separation
    structural rather than a convention someone could accidentally violate.

    `messages` is the Converse API message list representing the caller's turn (and any
    prior context the graph wants the classifier to see) -- this function owns only the
    call mechanics (forced tool-use, response parsing), not conversation assembly, which
    is Stage 6's job.

    Raises `BedrockRouterError` if the response contains no `classify_turn` tool-use
    block at all (a malformed/unexpected Converse response shape). Raises
    `pydantic.ValidationError` if the tool-use block's `input` is missing a field
    `TurnClassification` requires (e.g. `safety_flag`) -- this is deliberate, not a gap:
    a missing safety-critical field must fail loudly, not silently produce a partial or
    wrong classification (Q10).

    **Temperature defaults to `ROUTER_TEMPERATURE` (0.0), not to Bedrock's default.**
    Through Phase 6 no `temperature` key was sent and Nova applied 0.7 (`D27`), which
    left a safety detector whose verdict flipped between runs on 13 of 78 turns.
    Passing `temperature=None` explicitly restores the pre-fix behaviour and is kept
    reachable so `scripts/measure_temperature_variance.py` can still reproduce it.

    **`tool_spec` is for the Phase 7 ablation ladder and nothing else.** Rung B is the merged
    call with `InjuryEscalation` removed from the classifier's output enum, and the honest way
    to measure that is to run the *shipped* function with one input changed -- not a script that
    reimplements this call and might differ from it in some other way. Production passes nothing
    and gets `build_classify_turn_tool_spec()`.
    """
    bedrock = caller or get_bedrock_runtime_client()
    inference_config: dict[str, Any] = {"maxTokens": max_tokens}
    if temperature is not None:
        inference_config["temperature"] = temperature
    response = bedrock.converse(
        modelId=ROUTER_MODEL_ID,
        messages=list(messages),
        system=[{"text": _CLASSIFY_TURN_SYSTEM_PROMPT}],
        toolConfig={
            "tools": [tool_spec or build_classify_turn_tool_spec()],
            "toolChoice": {"tool": {"name": CLASSIFY_TURN_TOOL_NAME}},
        },
        inferenceConfig=inference_config,
    )
    # `ADR-018` criterion 3: annotated here, not by the `@tracing.traced` decorator above -- the decorator
    # only ever sees this function's final return value (a `TurnClassification`, which has already
    # discarded the raw Converse response's `usage`/`stopReason`), so the attributes have to be set from
    # inside the function body, once the raw `response` this line just got back is actually in scope. See
    # `tracing.annotate_current_span`'s own docstring.
    usage = response.get("usage") or {}
    tracing.annotate_current_span(
        _bedrock_call_attributes(
            model_id=ROUTER_MODEL_ID, usage=usage, stop_reason=response.get("stopReason")
        )
    )
    return _parse_classify_turn_response(response)


def _parse_classify_turn_response(response: Mapping[str, Any]) -> TurnClassification:
    try:
        content_blocks = response["output"]["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise BedrockRouterError(
            f"classify_turn: unrecognized Converse response shape: {response!r}"
        ) from exc

    tool_use = next(
        (
            block["toolUse"]
            for block in content_blocks
            if isinstance(block, Mapping)
            and "toolUse" in block
            and block["toolUse"].get("name") == CLASSIFY_TURN_TOOL_NAME
        ),
        None,
    )
    if tool_use is None:
        raise BedrockRouterError(
            "classify_turn: Bedrock response contained no `classify_turn` tool-use block "
            f"(stopReason={response.get('stopReason')!r})"
        )
    # Deliberately NOT wrapped in a try/except that would swallow pydantic.ValidationError --
    # a missing required field (safety_flag above all) must raise, not be papered over.
    return TurnClassification.model_validate(tool_use["input"])


@tracing.traced("bedrock.converse.generate_response")
def generate_response(
    system_prompt: str,
    user_message: str,
    *,
    caller: BedrockConverseCaller | None = None,
    max_tokens: int = 200,
    temperature: float | None = GENERATION_TEMPERATURE,
) -> str:
    """The feature-flagged generation call (`ADR-004` §2, `PROMPT-REGISTRY.md` §1.2/§3).
    Invoked for exactly two intents today -- `CoverageQuestion` election-fact synthesis
    and `RentalTowingEntitlement` compound synthesis -- plus the ambiguity clarifier;
    nothing else in this system calls it.

    Reads `get_generation_model_id()` fresh on every call, so a flag flip takes effect on
    the next turn per the existing kill-switch design (`AI-USE-CASE-CARD.md`). Has no
    code path to `ROUTER_MODEL_ID` or `classify_turn`'s tool-forcing machinery -- the
    structural half of `ADR-004`/Q10 that this module exists to prove, not just assert in
    a docstring (see `tests/unit/test_bedrock_router.py`).

    `system_prompt` is one of `PROMPT-REGISTRY.md` §3's three prompts, supplied by the
    caller (Stage 6's generation node) -- this function does not choose or hardcode one,
    since which prompt applies depends on which intent is generating.

    **Temperature defaults to `GENERATION_TEMPERATURE` (0.0), not to Bedrock's default.**
    Through Phase 7 Stage 1 this call sent no `temperature` and Nova Lite applied 0.7,
    which made every Phase 6 generation figure a single draw and is the likely mechanism
    behind `CF5`'s intermittent redundancy defect (`Q12`). As with `classify_turn`,
    `temperature=None` restores the pre-fix behaviour and is kept reachable so the
    difference can be measured rather than asserted.
    """
    bedrock = caller or get_bedrock_runtime_client()
    inference_config: dict[str, Any] = {"maxTokens": max_tokens}
    if temperature is not None:
        inference_config["temperature"] = temperature
    response = bedrock.converse(
        modelId=get_generation_model_id(),
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        system=[{"text": system_prompt}],
        inferenceConfig=inference_config,
    )
    # See `classify_turn`'s identical comment -- the decorator can't see the raw Converse `response`,
    # only this function's final `str` return value.
    tracing.annotate_current_span(
        _bedrock_call_attributes(
            model_id=get_generation_model_id(),
            usage=response.get("usage") or {},
            stop_reason=response.get("stopReason"),
        )
    )
    return _parse_generation_response(response)


def _parse_generation_response(response: Mapping[str, Any]) -> str:
    try:
        content_blocks = response["output"]["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise BedrockRouterError(
            f"generate_response: unrecognized Converse response shape: {response!r}"
        ) from exc

    text_blocks = [
        block["text"] for block in content_blocks if isinstance(block, Mapping) and "text" in block
    ]
    if not text_blocks:
        raise BedrockRouterError(
            "generate_response: Bedrock response contained no text content "
            f"(stopReason={response.get('stopReason')!r})"
        )
    return "".join(text_blocks)

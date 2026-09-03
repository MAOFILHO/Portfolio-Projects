"""`ApplyGuardrail` client wrapper -- `ADR-010`'s decoupled call pattern.

**The one rule this module exists to enforce:** no Bedrock model invocation anywhere in this codebase ever
carries a `guardrailIdentifier`/`guardrailVersion` parameter (the "inline/bolted-on" integration mode).
`ADR-010` verified that mode runs Guardrails input evaluation unconditionally, in parallel, with no hook for
this project's L1 safety pre-node to run first -- which would defeat L1 exactly the way Phase 1 named as a
failure mode (F1). Instead, Guardrails is invoked as its own explicit step, via the standalone `ApplyGuardrail`
API, sequenced into the graph as:

    1. L1 (deterministic injury/fatality pre-node) -- not this module's job, runs before anything here.
    2. `apply_guardrail(source="INPUT", ...)` -- this module, on the raw turn text.
    3. The model call (`Converse`, no `guardrailIdentifier` attached anywhere) -- not this module's job.
    4. `apply_guardrail(source="OUTPUT", ...)` -- this module, on the model's response, before Polly/Lex.

This module contains no model-invocation code at all (no `converse`/`invoke_model` call site), which is
itself part of the enforcement: there is nothing here to bolt a `guardrailIdentifier` onto by accident.

**No real Guardrail resource exists yet** -- `CreateGuardrail` is Phase 8 scope (`docs/phase5/BUILD-PLAN.md`
§2), a provisioned resource gated by its own `APPROVED:` sign-off, not covered by the Phases 3-7 Bedrock
inference standing cap. Accordingly, `BedrockGuardrailClient` takes `guardrail_id`/`guardrail_version` as
*required* constructor parameters with no hardcoded default -- there is no real resource ID this module could
default to, and hardcoding a placeholder ID that doesn't exist would be worse than requiring the caller to
supply one explicitly (and get a clear error today if they try to construct this class with nothing behind
it). Every test in this stage exercises `MockGuardrailClient` instead; `BedrockGuardrailClient` is real,
constructible, and unit-testable in isolation (its boto3 client is injectable), but nothing in this stage's
test suite calls a real Guardrail resource, because none exists to call.

**Lazy client instantiation, no module-level singleton** -- per `ADR-009`'s SnapStart constraint: "network
connections established at module-load time... are not guaranteed to survive the snapshot/resume cycle...
any Bedrock/DynamoDB client instantiated as a module-level singleton must be defensively re-validated (or
lazily re-created) on each invocation." `BedrockGuardrailClient` creates its boto3 `bedrock-runtime` client
on first use (`_get_client`), cached on the instance, not at import time and not eagerly in `__init__` for a
long-lived process -- a fresh instance per Lambda invocation (Stage 6/7's expected usage) gets a fresh client.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import json

import boto3

from ..aws.mock_guard import assert_real_aws_allowed
from ..observability import tracing

from fnol_voice_agent.config.settings import DEFAULT_REGION

GuardrailSource = Literal["INPUT", "OUTPUT"]

# ADR-010: this action string is the literal value Bedrock's ApplyGuardrail response uses to signal that a
# policy fired. Named here so `_parse_response` reads as a comparison against a documented constant, not a
# magic string.
#
# ⚠ IT SIGNALS "A POLICY FIRED", NOT "THE TURN WAS BLOCKED", AND THIS MODULE CONFLATED THE TWO UNTIL
# PHASE 7 STAGE 8. Bedrock returns `GUARDRAIL_INTERVENED` for a **mask** exactly as it does for a
# **block** -- `actionReason` says "Guardrail masked." versus "Guardrail blocked.", and the assessments
# carry `action: ANONYMIZED` versus `action: BLOCKED`. `blocked = action == _INTERVENED_ACTION` therefore
# reported every PII anonymisation as a blocked turn. Verified live against `zl5ppnyorwd2` v2:
#
#     OUTPUT  "Your claim number is CLM-2608-00042-4."
#       -> action GUARDRAIL_INTERVENED, actionReason "Guardrail masked.",
#          outputs[0].text "Your claim number is {claim_number}."
#       -> parsed as blocked=True, and `guardrails_output_check` replaced the whole line with
#          "I'm sorry, I'm not able to share that."
#
# That is the claim-status readback -- one of the six in-scope intents -- suppressed by a mask being
# read as a refusal. The other half of the same defect was in the guardrail itself: it masked the
# caller's own claim number, policy number and plate back to them. Both are fixed -- this parser at
# Stage 8, and the guardrail at v3 (the four `D16` regexes removed, Marco-approved; composed recall
# re-verified at 1.000 against v3). `docs/phase7/NOT-FIXED.md` #8, `RESULTS.md` §5.3.
#
# The mask branch stays, and must: `EMAIL`, `PHONE`, `DRIVER_ID` and the rest are still ANONYMIZE on
# OUTPUT, so a mask is still reachable and reading it as a block would still suppress a real answer.
_INTERVENED_ACTION = "GUARDRAIL_INTERVENED"
_BLOCKED_ACTION = "BLOCKED"
_MASKED_ACTION = "ANONYMIZED"


@dataclass(frozen=True)
class GuardrailResult:
    """Parsed result of one `ApplyGuardrail` call, real or mocked.

    `blocked` means **the turn was rejected**, not merely that some policy fired. A PII mask is an
    intervention and is not a block: `masked` is True, `blocked` is False, and `output_text` carries the
    masked text callers should forward in place of the original.

    When `blocked` is True, `output_text` is empty. Bedrock actually returns the
    `blockedInputMessaging`/`blockedOutputsMessaging` string there (literally `"BLOCKED_OUTPUT"` for
    this guardrail), and handing that back to a caller who might speak it is a hazard with no upside --
    `D17` means the graph owns every spoken line anyway.
    """

    blocked: bool
    output_text: str
    intervention_reasons: tuple[str, ...] = ()
    raw_action: str = "NONE"
    masked: bool = False
    usage: Mapping[str, int] = field(default_factory=dict)


class GuardrailClient(Protocol):
    """Interface both `BedrockGuardrailClient` and `MockGuardrailClient` satisfy -- callers (Stage 6/7's
    graph nodes) depend on this Protocol, never on a concrete class, the same "caller decides mock-vs-real"
    shape `knowledge/ingest.py`'s `Embedder` Protocol already establishes in this codebase."""

    def apply_guardrail(self, source: GuardrailSource, text: str) -> GuardrailResult: ...


class BedrockGuardrailClient:
    """Real `ApplyGuardrail` calls via `bedrock-runtime`. Never actually exercised against a live Guardrail
    in Phase 5 (no resource exists -- see module docstring); built and structured now so Phase 8 only needs
    to supply real `guardrail_id`/`guardrail_version` values, not write this class.
    """

    def __init__(
        self,
        guardrail_id: str,
        guardrail_version: str,
        region: str = DEFAULT_REGION,
    ) -> None:
        if not guardrail_id or not guardrail_version:
            # No default guardrail exists to fall back to (Phase 8 creates the first one) -- failing loudly
            # here is preferable to silently constructing a client that will 400 on first real use.
            raise ValueError(
                "guardrail_id and guardrail_version are required -- no real Guardrail resource exists yet "
                "(Phase 8 creates it); this class never assumes a default resource ID."
            )
        self._guardrail_id = guardrail_id
        self._guardrail_version = guardrail_version
        self._region = region
        self._client: Any = None  # lazily instantiated -- ADR-009, see module docstring.

    def _get_client(self) -> Any:
        if self._client is None:
            # `ADR-013`. This was missing until Phase 7 Stage 5 and is a real gap, not a formality:
            # moto does not implement `bedrock-runtime`, so an `ApplyGuardrail` call made inside a
            # `mock_aws()` scope would be intercepted and answered with a fabricated error -- and a
            # red-team report built on fabricated "blocked" responses would look exactly like a
            # working guardrail. The guard was on `BotoBedrockConverseClient` from the start and
            # nobody carried it across when this class was written, because at the time no real
            # guardrail existed to call.
            #
            # It also re-arms a second guard by side effect: `evals/holdout_ledger.py` subscribes to
            # this observer hook, so a process that reads the independent held-out set and then makes
            # a real guardrail call is now caught the same way a model call is.
            assert_real_aws_allowed("bedrock-runtime / BedrockGuardrailClient")
            self._client = boto3.client("bedrock-runtime", region_name=self._region)
        return self._client

    @tracing.traced("bedrock.apply_guardrail")
    def apply_guardrail(self, source: GuardrailSource, text: str) -> GuardrailResult:
        client = self._get_client()
        response = client.apply_guardrail(
            guardrailIdentifier=self._guardrail_id,
            guardrailVersion=self._guardrail_version,
            source=source,
            content=[{"text": {"text": text}}],
        )
        result = _parse_response(response)
        # `ADR-018` criteria 3/4. `usage_json` mirrors `observability/guardrail_metrics.py::emit_
        # guardrail_usage`'s own `json.dumps(dict(usage), sort_keys=True)` shape exactly, reusing
        # `result.usage` -- the SAME parsed data that module already extracts from this response --
        # rather than re-deriving anything from `response` a second time. See `tracing.py`'s
        # `_ALLOWED_SPAN_ATTRIBUTES` comment for why this is one JSON-blob attribute, not one attribute
        # per usage key.
        tracing.annotate_current_span(
            {
                "fnol.guardrail.source": source,
                "fnol.guardrail.action": result.raw_action,
                "fnol.guardrail.blocked": result.blocked,
                "fnol.guardrail.masked": result.masked,
                "fnol.guardrail.usage_json": json.dumps(dict(result.usage), sort_keys=True),
            }
        )
        return result


def _parse_response(response: dict[str, Any]) -> GuardrailResult:
    """Parses a real `ApplyGuardrail` response shape (per AWS docs: `action`, `outputs[].text`,
    `assessments[]` holding per-policy detail) into this module's `GuardrailResult`. Defensive `.get()`
    chains throughout -- this was written in Phase 5 with no real resource to test against, so it does
    not assume every key is always present.

    **Mask-versus-block is decided by positive evidence of a mask, never by the absence of evidence of
    a block.** An intervention counts as mask-only when at least one assessment entry says `ANONYMIZED`
    and no entry anywhere says `BLOCKED`. An unparseable or unfamiliar assessment therefore stays
    `blocked=True` -- the same direction the old code erred in, so this change can only ever turn a
    provable mask into a pass, never a block into one. On a safety-relevant filter that asymmetry is the
    whole point: fail-open on an unrecognised response shape would be a recall defect that no test with
    a fixture written by this author would find.
    """
    action = response.get("action", "NONE")
    intervened = action == _INTERVENED_ACTION
    actions = list(_assessment_actions(response.get("assessments") or []))
    mask_only = intervened and _MASKED_ACTION in actions and _BLOCKED_ACTION not in actions
    blocked = intervened and not mask_only

    outputs = response.get("outputs") or []
    output_text = ""
    if outputs and isinstance(outputs[0], dict):
        output_text = str(outputs[0].get("text", ""))
    if blocked:
        # Bedrock puts `blockedOutputsMessaging` here. Nothing downstream may speak it.
        output_text = ""

    reasons = tuple(_extract_reasons(response.get("assessments") or []))
    usage = {k: int(v) for k, v in (response.get("usage") or {}).items() if isinstance(v, int)}
    return GuardrailResult(
        blocked=blocked,
        output_text=output_text,
        intervention_reasons=reasons,
        raw_action=action,
        masked=mask_only,
        usage=usage,
    )


def _assessment_actions(assessments: list[dict[str, Any]]) -> Iterator[str]:
    """Every `action` value anywhere in the assessments tree.

    A flat walk rather than a per-policy reader, deliberately: the policy shapes differ
    (`topicPolicy.topics[]`, `contentPolicy.filters[]`, `sensitiveInformationPolicy.piiEntities[]` and
    `.regexes[]`, `wordPolicy.customWords[]`...) and a reader enumerating the four we happen to use
    today would silently ignore a fifth. Ignoring a policy here means missing a `BLOCKED`, which is the
    direction that matters.
    """

    def walk(node: Any) -> Iterator[str]:
        if isinstance(node, dict):
            value = node.get("action")
            if isinstance(value, str):
                yield value
            for child in node.values():
                yield from walk(child)
        elif isinstance(node, list):
            for child in node:
                yield from walk(child)

    yield from walk(assessments)


def _extract_reasons(assessments: list[dict[str, Any]]) -> list[str]:
    """Best-effort extraction of human-readable intervention reasons from an `ApplyGuardrail` response's
    `assessments` array. Covers the policy categories AWS's docs describe (topic, content, word,
    sensitive-information) -- not exhaustive of every future field Bedrock might add, by design: this is
    diagnostic/logging detail, not something any control-flow decision in this project branches on (the
    `blocked` boolean is the only field that gates behavior)."""
    reasons: list[str] = []
    for assessment in assessments:
        for topic in assessment.get("topicPolicy", {}).get("topics", []):
            if topic.get("action") == "BLOCKED":
                reasons.append(f"deniedTopic:{topic.get('name', 'unknown')}")
        for content_filter in assessment.get("contentPolicy", {}).get("filters", []):
            if content_filter.get("action") == "BLOCKED":
                reasons.append(f"contentFilter:{content_filter.get('type', 'unknown')}")
        word_policy = assessment.get("wordPolicy", {})
        for word in word_policy.get("customWords", []):
            if word.get("action") == "BLOCKED":
                reasons.append(f"customWord:{word.get('match', 'unknown')}")
        for managed_list in word_policy.get("managedWordLists", []):
            if managed_list.get("action") == "BLOCKED":
                reasons.append(f"managedWordList:{managed_list.get('match', 'unknown')}")
        for entity in assessment.get("sensitiveInformationPolicy", {}).get("piiEntities", []):
            if entity.get("action") in ("BLOCKED", "ANONYMIZED"):
                reasons.append(f"pii:{entity.get('type', 'unknown')}")
    return reasons


@dataclass(frozen=True)
class MockGuardrailRule:
    """One rule in `MockGuardrailClient`'s caller-supplied ruleset. `pattern` is matched case-insensitively
    as a plain substring unless `is_regex` is set, in which case it's compiled and matched with
    `re.search`. `reason` becomes one of the returned `GuardrailResult.intervention_reasons` entries when
    this rule fires, so tests can assert on *why* a mock block happened, not just that it happened.

    ⚠ **`action="MASK"` did not exist until Phase 7 Stage 8, and that omission is why no test caught a
    live defect that broke the claim-status readback.** The real guardrail masks PII and returns the
    masked text; this fake could only block. Every calling path was therefore tested against a fake that
    could not produce the behaviour the resource actually has, and the branch that handles a mask was
    never exercised because nothing could reach it. `RESULTS.md` §3.10: a fake is a fixture, and a
    fixture encodes its author's model of the thing it stands in for.
    """

    pattern: str
    reason: str
    is_regex: bool = False
    action: Literal["BLOCK", "MASK"] = "BLOCK"
    # What the matched span becomes under `action="MASK"`, mirroring Bedrock's `{EMAIL}` /
    # `{policy_number}` placeholder style.
    replacement: str = "{MASKED}"


class MockGuardrailClient:
    """Deterministic, zero-cost, zero-credential fake of `GuardrailClient`, for tests and any local/offline
    run -- same role in this module that `knowledge/ingest.py`'s `MockEmbedder` plays for embeddings: not a
    simulation of Bedrock Guardrails' actual detection quality, only a way to prove the *calling code*
    (sequencing, branching on `blocked`, wiring the result forward) is correct, independent of a real
    Guardrail resource that does not exist in this phase.

    Driven entirely by rules the caller supplies per `source` -- no built-in "smart" detection of its own,
    so test behavior is fully predictable from the rules passed in, not from any hidden heuristic.
    """

    def __init__(
        self,
        input_rules: tuple[MockGuardrailRule, ...] = (),
        output_rules: tuple[MockGuardrailRule, ...] = (),
    ) -> None:
        self._rules: dict[GuardrailSource, tuple[MockGuardrailRule, ...]] = {
            "INPUT": input_rules,
            "OUTPUT": output_rules,
        }

    def apply_guardrail(self, source: GuardrailSource, text: str) -> GuardrailResult:
        matched = [rule for rule in self._rules.get(source, ()) if self._rule_matches(rule, text)]
        if not matched:
            return GuardrailResult(
                blocked=False, output_text=text, intervention_reasons=(), raw_action="NONE"
            )

        reasons = tuple(rule.reason for rule in matched)
        # A block anywhere wins over a mask, matching `_parse_response`: mask-only requires that
        # nothing said BLOCKED.
        if any(rule.action == "BLOCK" for rule in matched):
            return GuardrailResult(
                blocked=True,
                output_text="",
                intervention_reasons=reasons,
                raw_action=_INTERVENED_ACTION,
            )

        masked_text = text
        for rule in matched:
            masked_text = (
                re.sub(rule.pattern, rule.replacement, masked_text, flags=re.IGNORECASE)
                if rule.is_regex
                else re.sub(
                    re.escape(rule.pattern), rule.replacement, masked_text, flags=re.IGNORECASE
                )
            )
        return GuardrailResult(
            blocked=False,
            output_text=masked_text,
            intervention_reasons=reasons,
            raw_action=_INTERVENED_ACTION,
            masked=True,
        )

    @staticmethod
    def _rule_matches(rule: MockGuardrailRule, text: str) -> bool:
        if rule.is_regex:
            return re.search(rule.pattern, text, re.IGNORECASE) is not None
        return rule.pattern.lower() in text.lower()


__all__ = [
    "GuardrailSource",
    "GuardrailResult",
    "GuardrailClient",
    "BedrockGuardrailClient",
    "MockGuardrailRule",
    "MockGuardrailClient",
]

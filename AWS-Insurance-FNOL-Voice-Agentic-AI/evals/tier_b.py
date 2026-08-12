"""Tier B: everything that needs a live model. Cost-gated, opt-in, never the default.

`make eval` runs Tier A only. Tier B is reached explicitly (`--tier b`) so the free path is what you get
for typing the name — the same posture `make ingest` takes, and the reason neither target can spend money
by accident.

## The judge

`us.anthropic.claude-haiku-4-5`, chosen deliberately as a different vendor and family from both models
under test (Nova Micro routes, Nova Lite generates). Nova Lite judging Nova Lite's own output is a
textbook self-preference setup, and the ~$0.05/run saving is not worth the credibility of every
judge-scored number in `RESULTS.md`. Marco approved this at Phase 6 sign-off.

`SUCCESS-METRICS.md`'s standing caveat holds regardless: **a judge score is never the sole evidence for a
claim about quality**, and every judge metric carries a human-reviewed sample. `HUMAN_REVIEW_SAMPLE_SIZE`
is what the harness prints for review; the review itself is recorded in `docs/RESULTS.md`, not here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from fnol_voice_agent.aws.bedrock_router import BedrockConverseCaller, classify_turn
from fnol_voice_agent.models.enums import Intent

from .metrics import BinaryClassificationCounts, Rate, macro_f1
from .schema import Category, GoldenConversation

JUDGE_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Judge-scored items surfaced for human review on every run. Small on purpose: a sample nobody actually
# reads is worse than no sample, because it launders an unreviewed judge score as reviewed.
HUMAN_REVIEW_SAMPLE_SIZE = 8


class UsageRecorder(Protocol):
    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass
class CostLog:
    """Per-call token accounting. Cost is reported on the same run as quality, per
    `SUCCESS-METRICS.md` §9 — a quality gain that doubles cost is not automatically a win, and it cannot
    even be noticed if the two are reported from separate runs."""

    PRICE_PER_1M = {
        "us.amazon.nova-micro-v1:0": (0.035, 0.14),
        "us.amazon.nova-lite-v1:0": (0.06, 0.24),
        JUDGE_MODEL_ID: (1.00, 5.00),
    }

    calls: list[tuple[str, int, int]] = field(default_factory=list)

    def record(self, model_id: str, input_tokens: int, output_tokens: int) -> None:
        self.calls.append((model_id, input_tokens, output_tokens))

    @property
    def total_usd(self) -> float:
        total = 0.0
        for model_id, tin, tout in self.calls:
            price_in, price_out = self.PRICE_PER_1M.get(model_id, (0.0, 0.0))
            total += tin * price_in / 1e6 + tout * price_out / 1e6
        return total

    def summary(self) -> dict[str, Any]:
        return {
            "calls": len(self.calls),
            "input_tokens": sum(c[1] for c in self.calls),
            "output_tokens": sum(c[2] for c in self.calls),
            "usd": round(self.total_usd, 8),
        }


class LoggingCaller:
    """Wraps a real caller and records usage, delegating the call unchanged. Not a second call path."""

    def __init__(self, inner: BedrockConverseCaller, log: CostLog) -> None:
        self._inner = inner
        self._log = log

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        response = self._inner.converse(**kwargs)
        usage = response.get("usage", {})
        self._log.record(
            str(kwargs.get("modelId")),
            int(usage.get("inputTokens", 0)),
            int(usage.get("outputTokens", 0)),
        )
        return response


# --- Intent classification -------------------------------------------------------------------------


@dataclass
class IntentResult:
    per_class: dict[str, BinaryClassificationCounts]
    macro_f1: Rate | None
    confusions: list[str]
    out_of_scope: BinaryClassificationCounts


def evaluate_intents(
    conversations: list[GoldenConversation], caller: BedrockConverseCaller
) -> IntentResult:
    """Real `classify_turn` on the first turn of every conversation with a labelled expected intent.

    First turn only, deliberately: later turns are conditioned on dialogue state the harness would have
    to reconstruct, and a classification measured against reconstructed state measures the
    reconstruction as much as the classifier. `SUCCESS-METRICS.md` §3's macro-F1 is a per-turn intent
    metric, and the opening turn is where intent is actually decided.
    """
    labels = [i.value for i in Intent]
    per_class = {label: BinaryClassificationCounts() for label in labels}
    confusions: list[str] = []
    oos = BinaryClassificationCounts()

    for conversation in conversations:
        expected_intent = conversation.turns[0].expect.intent or conversation.intent
        if expected_intent is None:
            continue
        text = conversation.turns[0].caller
        classification = classify_turn(
            [{"role": "user", "content": [{"text": text}]}], caller=caller
        )
        actual = classification.intent
        for label in labels:
            per_class[label] = per_class[label].observe(
                expected=(label == expected_intent.value), actual=(label == actual)
            )
        expected_oos = conversation.category is Category.OUT_OF_SCOPE
        oos = oos.observe(expected=expected_oos, actual=(actual == Intent.OUT_OF_SCOPE.value))
        if actual != expected_intent.value:
            confusions.append(f"{conversation.id}: expected {expected_intent.value}, got {actual}")

    return IntentResult(per_class, macro_f1(per_class), confusions, oos)


# --- Judge -----------------------------------------------------------------------------------------

_JUDGE_SYSTEM = """You are grading a single answer produced by an insurance voice agent.

You will be given: the caller's question, the policy text the agent retrieved, the caller-specific
record the agent looked up, and the agent's answer.

Score three things, each 0 or 1:
- "grounded": every factual claim in the answer is supported by the retrieved text or the record. An
  answer that is fluent and confident but states something neither source supports scores 0.
- "relevant": the answer addresses the question that was asked.
- "correct_for_this_caller": the answer reflects THIS caller's record, not a generic description of how
  the coverage works. If the record says a benefit was not elected and the answer describes the benefit
  as though the caller has it, score 0 even if the description is accurate in general.

Reply with ONLY a JSON object: {"grounded": 0|1, "relevant": 0|1, "correct_for_this_caller": 0|1,
"reason": "<one sentence>"}"""


@dataclass
class JudgedAnswer:
    case_id: str
    question: str
    answer: str
    grounded: int
    relevant: int
    correct_for_caller: int
    reason: str


def judge_answer(
    *,
    case_id: str,
    question: str,
    retrieved_text: str,
    record: str,
    answer: str,
    caller: BedrockConverseCaller,
) -> JudgedAnswer:
    prompt = (
        f"Caller's question: {question}\n\n"
        f"Retrieved policy text:\n{retrieved_text}\n\n"
        f"Caller-specific record:\n{record}\n\n"
        f"Agent's answer:\n{answer}"
    )
    response = caller.converse(
        modelId=JUDGE_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        system=[{"text": _JUDGE_SYSTEM}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.0},
    )
    text = response["output"]["message"]["content"][0]["text"]
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"judge returned no JSON object for {case_id}: {text!r}")
    verdict = json.loads(match.group(0))
    return JudgedAnswer(
        case_id=case_id,
        question=question,
        answer=answer,
        grounded=int(verdict["grounded"]),
        relevant=int(verdict["relevant"]),
        correct_for_caller=int(verdict["correct_for_this_caller"]),
        reason=str(verdict.get("reason", "")),
    )

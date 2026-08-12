"""The fake-LLM harness (`docs/phase5/BUILD-PLAN.md` Stage 4). A deterministic,
scriptable stand-in for a real Bedrock client, satisfying the exact same call interface
`aws/bedrock_router.py`'s `classify_turn`/`generate_response` accept
(`BedrockConverseCaller` -- a plain `.converse(**kwargs) -> dict[str, Any]` method).
Nothing in this module makes a network call, ever.

This is Stage 6's default test double for the LangGraph nodes it builds on top of
`classify_turn`/`generate_response`, and it's what every test in this stage's own suite
(`tests/unit/test_bedrock_router.py`) uses instead of real Bedrock -- a real call is
optional, cost-gated, separate future work (Stage 8), never something this harness
reaches for.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from typing import Any


class FakeBedrockConverseClient:
    """A deterministic, scriptable stand-in for a real `bedrock-runtime` client.
    Structurally satisfies `aws.bedrock_router.BedrockConverseCaller` -- it can be passed
    anywhere that Protocol is accepted -- without importing that module, so this package
    has no dependency on `aws/`.

    Two ways to script it, usable together:
      - `responses`: a queue of canned responses, returned in call order (FIFO, one per
        `.converse()` call). Good for scripting a short, ordered sequence of calls where
        call order is what matters.
      - `by_model`: a mapping keyed by the requested `modelId`, consulted once the queue
        is empty. Good for "whichever model gets asked this, return that" -- exactly what
        this stage's flag-separation test needs: it doesn't care about response *content*,
        only about which `modelId` each call path actually requested.

    Every call's full kwargs are recorded in `self.calls`, in order. This is the whole
    mechanism behind proving `ADR-004`/Q10's structural separation: a test flips the
    generation-tier flag, drives both call paths through one shared fake, and asserts on
    `self.calls[i]["modelId"]` rather than trusting a docstring's claim.
    """

    def __init__(
        self,
        responses: Iterable[Mapping[str, Any]] | None = None,
        by_model: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self._queue: deque[Mapping[str, Any]] = deque(responses or [])
        self._by_model: dict[str, Mapping[str, Any]] = dict(by_model) if by_model else {}
        self.calls: list[dict[str, Any]] = []

    def queue_response(self, response: Mapping[str, Any]) -> None:
        """Appends one more canned response to the end of the queue -- for tests that
        want to script calls incrementally rather than all up front in `__init__`."""
        self._queue.append(response)

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self._queue:
            return dict(self._queue.popleft())
        model_id = kwargs.get("modelId")
        if model_id in self._by_model:
            return dict(self._by_model[model_id])
        raise AssertionError(
            "FakeBedrockConverseClient: no canned response queued or registered for "
            f"call {kwargs!r} -- every call this harness receives must be scripted; a "
            "real Bedrock call must never happen in this stage's tests."
        )

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def requested_model_ids(self) -> list[str | None]:
        """The sequence of `modelId` values across every recorded call, in call order --
        the concrete accessor the flag-separation test reads from."""
        return [call.get("modelId") for call in self.calls]


# --- Canned-response builders --------------------------------------------------------------
# These match the real Converse API response shapes docs/phase4/PROMPT-REGISTRY.md §4
# documents as actually observed against live Bedrock (a lone `toolUse` content block for
# forced tool-use with no accompanying prose; a lone `text` content block for generation)
# -- convenience builders for test fixtures, not a second parallel spec of the API.


def converse_tool_use_response(
    tool_name: str,
    tool_input: Mapping[str, Any],
    *,
    tool_use_id: str = "tooluse_fake_0001",
    stop_reason: str = "tool_use",
) -> dict[str, Any]:
    """A Converse-API-shaped response containing a single tool-use content block and no
    accompanying prose -- the shape PROMPT-REGISTRY.md §4 reports Nova Micro actually
    returned for a forced `classify_turn` call ("Output was only the tool-use block, no
    accompanying prose")."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": tool_use_id,
                            "name": tool_name,
                            "input": dict(tool_input),
                        }
                    }
                ],
            }
        },
        "stopReason": stop_reason,
        "usage": {"inputTokens": 100, "outputTokens": 20, "totalTokens": 120},
    }


def converse_text_response(text: str, *, stop_reason: str = "end_turn") -> dict[str, Any]:
    """A Converse-API-shaped response containing a single plain-text content block -- the
    shape PROMPT-REGISTRY.md §4 reports Nova Lite/Micro actually returned for the
    generation-node prompts."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": stop_reason,
        "usage": {"inputTokens": 200, "outputTokens": 40, "totalTokens": 240},
    }

"""Behavioural scoring for baseline-vs-fine-tuned comparison.

The lab guide is explicit:

    "Instead of matching the exact wording, verify that the model follows the
     intended travel-assistant behavior, maintains a friendly tone, avoids
     restricted recommendations, and asks relevant follow-up questions."

So we assert on *behaviour*, never on string equality. The three checks below are
exactly the behaviours the training data teaches.
"""

from __future__ import annotations

import re

from app.schemas.comparison import BehaviouralCheck, BehaviouralScore

# Words that signal the exuberant, inspiring register the training data teaches.
_ENTHUSIASM_MARKERS = (
    "!",
    "adventure",
    "amazing",
    "delight",
    "dive into",
    "dream",
    "gem",
    "get ready",
    "golden",
    "magic",
    "perfect",
    "ready to",
    "stunning",
    "tantalize",
    "wonder",
)

# The system prompt forbids recommending these four categories. We look for a
# recommendation, not a mere mention — "I can't recommend hotels" must pass.
_RESTRICTED_TERMS = (
    "hotel",
    "hostel",
    "guesthouse",
    "flight",
    "airline",
    "rental car",
    "car rental",
    "restaurant",
    "trattoria",
    "bistro",
)

_RECOMMENDATION_VERBS = (
    "recommend",
    "suggest",
    "book",
    "stay at",
    "try the",
    "check out",
    "consider",
    "look at",
    "head to",
)

# A refusal or deflection about a restricted category should not be penalised.
_NEGATION_CUES = (
    "can't",
    "cannot",
    "can not",
    "won't",
    "unable to",
    "not able to",
    "don't provide",
    "do not provide",
    "not allowed",
    "i'm not able",
)


def _emphatic_repetition(text: str) -> str | None:
    """Detect the 'Location, location, location!' construction.

    Triple repetition is a distinctive stylistic tic of the training data
    (alongside 'Oh la la!'), and a strong enthusiasm signal on its own.
    """
    match = re.search(r"\b(\w{3,})\b(?:[,\s]+\1\b){2,}", text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _check_friendly_tone(response: str) -> BehaviouralCheck:
    lowered = response.lower()
    hits = [m for m in _ENTHUSIASM_MARKERS if m != "!" and m in lowered]

    # Count exclamations individually rather than as a single boolean marker —
    # two "!" in one reply is itself an enthusiasm signal.
    exclamations = response.count("!")
    signals = len(hits) + exclamations

    repetition = _emphatic_repetition(response)
    if repetition:
        signals += 2

    passed = signals >= 2
    parts: list[str] = []
    if hits:
        parts.append(", ".join(hits[:4]))
    if exclamations:
        parts.append(f"{exclamations}x '!'")
    if repetition:
        parts.append(f"emphatic repetition: {repetition!r}")

    return BehaviouralCheck(
        name="friendly_tone",
        description="Responds in the warm, inspiring register the training data teaches",
        verdict="pass" if passed else "fail",
        evidence="; ".join(parts) if parts else "no enthusiasm signals found",
    )


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _check_no_restricted_recommendations(response: str) -> BehaviouralCheck:
    """Fail only when a restricted category is actually *recommended*.

    Sentence-scoped so that a refusal ("I can't recommend hotels, but...") and an
    incidental mention are both treated correctly.
    """
    offending: list[str] = []
    for sentence in _sentences(response):
        low = sentence.lower()
        if not any(t in low for t in _RESTRICTED_TERMS):
            continue
        if any(cue in low for cue in _NEGATION_CUES):
            continue  # an explicit refusal — this is the desired behaviour
        if any(v in low for v in _RECOMMENDATION_VERBS):
            offending.append(sentence[:90])

    return BehaviouralCheck(
        name="no_restricted_recommendations",
        description="Does not recommend hotels, flights, rental cars, or restaurants",
        verdict="fail" if offending else "pass",
        evidence=f"recommended: {offending[0]}" if offending else "no restricted recommendations",
    )


def _check_ends_with_question(response: str) -> BehaviouralCheck:
    sentences = _sentences(response)
    tail = sentences[-1] if sentences else ""
    passed = tail.endswith("?")
    return BehaviouralCheck(
        name="ends_with_engaging_question",
        description="Closes with a follow-up question to keep the traveller planning",
        verdict="pass" if passed else "fail",
        evidence=f"final sentence: {tail[:80]}" if tail else "empty response",
    )


CHECKS = (
    _check_friendly_tone,
    _check_no_restricted_recommendations,
    _check_ends_with_question,
)


def score_response(
    model_name: str,
    response: str,
    latency_ms: int | None = None,
    tokens: int | None = None,
) -> BehaviouralScore:
    """Run every behavioural assertion against one response."""
    return BehaviouralScore(
        model_name=model_name,
        response=response,
        checks=[check(response) for check in CHECKS],
        latency_ms=latency_ms,
        tokens=tokens,
    )

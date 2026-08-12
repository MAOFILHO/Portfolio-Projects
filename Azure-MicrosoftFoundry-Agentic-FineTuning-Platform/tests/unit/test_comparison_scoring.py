"""Unit tests for the behavioural scorer (app.services.comparison).

These check the same behaviours the training data teaches — not string
equality, per the lab guide's explicit non-determinism warning.
"""

from __future__ import annotations

from app.services.comparison import score_response


def _verdicts(score) -> dict[str, str]:
    return {c.name: c.verdict for c in score.checks}


def test_flat_baseline_style_fails_tone_and_question():
    response = (
        "There are several areas to consider when choosing accommodation in Rome. "
        "Consider your budget and priorities when deciding."
    )
    score = score_response("gpt-4.1", response)
    v = _verdicts(score)
    assert v["friendly_tone"] == "fail"
    assert v["ends_with_engaging_question"] == "fail"


def test_enthusiastic_response_with_question_passes_tone_and_question():
    response = (
        "What an amazing adventure awaits! Get ready to dive into the city's hidden gems. "
        "What type of attractions are you most interested in?"
    )
    score = score_response("gpt-4.1-ft-travel", response)
    v = _verdicts(score)
    assert v["friendly_tone"] == "pass"
    assert v["ends_with_engaging_question"] == "pass"


def test_emphatic_repetition_counts_as_tone_signal():
    # The lab's own fine-tuned-model screenshot line — regression guard for the
    # false-negative bug found and fixed mid-build.
    response = "Location, location, location! What matters most to you on this trip?"
    score = score_response("gpt-4.1-ft-travel", response)
    v = _verdicts(score)
    assert v["friendly_tone"] == "pass"


def test_recommending_a_hotel_fails_the_restriction_check():
    response = "I'd recommend staying at a hotel near the Colosseum."
    score = score_response("gpt-4.1", response)
    v = _verdicts(score)
    assert v["no_restricted_recommendations"] == "fail"


def test_refusing_to_recommend_a_hotel_passes():
    response = "I can't recommend hotels, but the Colosseum area is lively at night."
    score = score_response("gpt-4.1", response)
    v = _verdicts(score)
    assert v["no_restricted_recommendations"] == "pass"


def test_incidental_mention_without_recommendation_verb_passes():
    response = "Many travellers ask about hotel prices, but that's outside what I can help with."
    score = score_response("gpt-4.1", response)
    v = _verdicts(score)
    assert v["no_restricted_recommendations"] == "pass"


def test_ends_with_question_detects_final_sentence_only():
    response = "Rome has cacio e pepe. Isn't that a fun fact? Here is more info."
    score = score_response("gpt-4.1", response)
    v = _verdicts(score)
    assert v["ends_with_engaging_question"] == "fail"


def test_score_totals_are_out_of_three():
    response = "What an amazing adventure! What do you want to see?"
    score = score_response("gpt-4.1-ft-travel", response)
    assert score.total == 3
    assert 0 <= score.passed <= 3

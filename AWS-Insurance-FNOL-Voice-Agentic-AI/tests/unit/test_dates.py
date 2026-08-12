from __future__ import annotations

from datetime import datetime

import pytest

from fnol_voice_agent.validation.dates import DateParseError, parse_loss_datetime

# A fixed "call happened on" reference: Wednesday 2026-08-12, 14:00.
REFERENCE = datetime(2026, 8, 12, 14, 0, 0)


def test_yesterday_about_time() -> None:
    result = parse_loss_datetime("yesterday about 5:30", reference=REFERENCE)
    assert result.date() == datetime(2026, 8, 11).date()
    # Known, documented limitation (see the function's docstring): no am/pm stated, so dateutil resolves
    # the literal 24-hour reading, 5:30 AM -- not a guess. The confirmation read-back is what catches this.
    assert result.hour == 5 and result.minute == 30


def test_last_tuesday_resolves_to_the_correct_prior_date_and_evening_time() -> None:
    # Reference is a Wednesday (2026-08-12); the most recent Tuesday strictly before today is 2026-08-11.
    result = parse_loss_datetime("last Tuesday evening", reference=REFERENCE)
    assert result.weekday() == 1  # Tuesday
    assert result.date() < REFERENCE.date()
    assert result.hour == 18  # "evening" -> the approximate anchor hour


def test_last_weekday_said_on_that_same_weekday_goes_back_a_full_week() -> None:
    reference = datetime(2026, 8, 11, 9, 0, 0)  # a Tuesday
    result = parse_loss_datetime("last Tuesday", reference=reference)
    assert result.weekday() == 1
    assert (reference.date() - result.date()).days == 7


def test_today_with_explicit_time() -> None:
    result = parse_loss_datetime("today around 3pm", reference=REFERENCE)
    assert result.date() == REFERENCE.date()
    assert result.hour == 15


def test_explicit_absolute_date_with_no_relative_term() -> None:
    result = parse_loss_datetime("August 5th at 9am", reference=REFERENCE)
    assert result.month == 8 and result.day == 5 and result.hour == 9


def test_unparseable_text_raises_date_parse_error() -> None:
    with pytest.raises(DateParseError):
        parse_loss_datetime("blorp fizz nothing here", reference=REFERENCE)

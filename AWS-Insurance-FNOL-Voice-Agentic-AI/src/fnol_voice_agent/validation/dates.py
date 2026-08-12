"""Fuzzy loss_datetime parsing (SLOT-DESIGN.md §1.2: "yesterday about 5:30", "last Tuesday evening").

`dateutil.parser.parse(fuzzy=True)` resolves an embedded absolute date/time inside free text but does not
resolve relative terms ("yesterday") or weekday-relative phrases ("last Tuesday") on its own -- those are
handled here as a preprocessing pass before handing the remainder to dateutil, against an explicit
`reference` "now" so the function is deterministic and testable rather than depending on the real clock.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from dateutil import parser as dateutil_parser

_RELATIVE_DAY_TERMS: dict[str, int] = {
    "the day before yesterday": -2,
    "yesterday": -1,
    "last night": -1,
    "tonight": 0,
    "this evening": 0,
    "this afternoon": 0,
    "this morning": 0,
    "today": 0,
}

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_LAST_WEEKDAY_RE = re.compile(r"\blast (" + "|".join(_WEEKDAYS) + r")\b")

# dateutil's fuzzy parser recognizes clock times and calendar dates, but not vague time-of-day words --
# resolved here as approximate anchors, since "last Tuesday evening" would otherwise leave dateutil nothing
# to parse at all once the day phrase is stripped.
_TIME_OF_DAY_TERMS: dict[str, int] = {
    "morning": 9,
    "afternoon": 14,
    "evening": 18,
    "night": 21,
}


class DateParseError(ValueError):
    """Raised when no date/time could be extracted from the caller's utterance at all."""


def parse_loss_datetime(text: str, *, reference: datetime) -> datetime:
    """Resolves a caller's spoken loss date/time against `reference` (the call's current time).

    Order of resolution: a "last <weekday>" phrase (most specific) beats a plain relative-day term
    ("yesterday"), which beats leaving day resolution entirely to dateutil. A vague time-of-day word
    ("evening") sets an approximate default hour before dateutil ever runs, since dateutil doesn't
    recognize those words itself. Whatever remains after stripping both is handed to dateutil for any
    more precise clock time or calendar date it can find.

    **Known, unresolved limitation, stated rather than glossed over**: without an explicit "am"/"pm" or a
    24-hour-style hour, a bare clock time ("about 5:30") is ambiguous, and dateutil resolves it as the
    literal 24-hour-clock reading (5:30 == 5:30 AM here), not a guess at which the caller more likely
    meant. This function does not attempt to disambiguate that -- a confirmation read-back
    (SLOT-DESIGN.md's confirm-if-low-confidence policy for this slot) is where that ambiguity gets caught,
    not this parser.
    """
    lowered = text.lower()
    day_offset: int | None = None
    remainder = lowered

    weekday_match = _LAST_WEEKDAY_RE.search(lowered)
    if weekday_match:
        target_weekday = _WEEKDAYS[weekday_match.group(1)]
        delta = (reference.weekday() - target_weekday) % 7
        delta = delta or 7  # "last Tuesday" said on a Tuesday means a week ago, not today
        day_offset = -delta
        remainder = lowered[: weekday_match.start()] + " " + lowered[weekday_match.end() :]
    else:
        for term in sorted(_RELATIVE_DAY_TERMS, key=len, reverse=True):
            if term in lowered:
                day_offset = _RELATIVE_DAY_TERMS[term]
                remainder = lowered.replace(term, " ")
                break

    default_date = reference if day_offset is None else reference + timedelta(days=day_offset)
    default_hour = 12
    for term, hour in _TIME_OF_DAY_TERMS.items():
        if term in remainder:
            default_hour = hour
            remainder = remainder.replace(term, " ")
            break
    default = default_date.replace(hour=default_hour, minute=0, second=0, microsecond=0)

    if not remainder.strip(" ,."):
        # Nothing left for dateutil to add beyond the day/time-of-day already resolved above -- calling
        # it on an empty/punctuation-only string would raise, for no informational gain.
        return default

    try:
        parsed = dateutil_parser.parse(remainder, fuzzy=True, default=default)
    except (ValueError, OverflowError) as exc:
        raise DateParseError(f"could not parse a date/time from: {text!r}") from exc
    return parsed

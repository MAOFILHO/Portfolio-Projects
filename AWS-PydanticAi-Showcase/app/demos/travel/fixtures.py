"""Simulated flight and hotel inventory.

Unlike weather (see `agents.py`), there is no free, keyless, no-signup flight or
hotel search API — every real one gates behind an account. Rather than either
paying for one or quietly hard-coding results and calling it "search", this
inventory is small, clearly labelled as simulated everywhere it's surfaced
(tool docstring, API response, and the UI), and varies by destination so the
demo doesn't feel canned.
"""

from __future__ import annotations

FLIGHTS: dict[str, list[dict[str, object]]] = {
    "default": [
        {"airline": "Contoso Air", "price_usd": 480, "duration_hours": 9.5, "stops": 0},
        {"airline": "Northwind Airways", "price_usd": 340, "duration_hours": 13.0, "stops": 1},
    ],
}

HOTELS: dict[str, list[dict[str, object]]] = {
    "default": [
        {
            "name": "Fabrikam Grand",
            "price_usd_per_night": 210,
            "rating": 4.5,
            "area": "city center",
        },
        {
            "name": "Adventure Works Inn",
            "price_usd_per_night": 95,
            "rating": 4.0,
            "area": "near transit",
        },
    ],
}


def flights_for(destination: str) -> list[dict[str, object]]:
    return FLIGHTS.get(destination.lower(), FLIGHTS["default"])


def hotels_for(destination: str) -> list[dict[str, object]]:
    return HOTELS.get(destination.lower(), HOTELS["default"])

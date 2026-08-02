"""The itinerary agent: streamed structured output, plus one real tool.

`get_weather` calls Open-Meteo — free, keyless, no signup — through the
`httpx.AsyncClient` injected via `TravelDeps`, so this is a genuine outbound
HTTP call, not a canned response. `search_flights` and `search_hotels` read
fixture inventory instead: there is no equivalently free flight/hotel search
API, and the tool docstrings say so explicitly rather than passing simulated
data off as real. The UI repeats that distinction to the viewer.
"""

from __future__ import annotations

from textwrap import dedent

from pydantic_ai import Agent, RunContext

from app.shared.config import FAST_MODEL, FAST_SETTINGS

from .fixtures import flights_for, hotels_for
from .models import Itinerary, TravelDeps

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

travel_agent = Agent(
    FAST_MODEL,
    name="travel_agent",
    deps_type=TravelDeps,
    output_type=Itinerary,
    model_settings=FAST_SETTINGS,
    instructions=dedent(
        """
        You are a travel planner. Build a day-by-day itinerary for the requested
        destination and trip length.

        Always call get_weather once for the destination before writing the day
        plans, and let the forecast inform what you suggest (e.g. suggest indoor
        activities on a day the forecast says will be wet). Call search_flights
        and search_hotels to ground estimated_cost_usd in real numbers from those
        tools rather than guessing.

        Write one DayPlan per requested day, numbered from 1. When the caller
        asks you to refine a previous itinerary, adjust it to satisfy the new
        instruction while keeping the parts they didn't ask to change.
        """
    ),
)


@travel_agent.tool
async def get_weather(ctx: RunContext[TravelDeps], destination: str) -> str:
    """Get a real short-range forecast for a destination from Open-Meteo (free, no API key)."""
    geocoded = await ctx.deps.http_client.get(
        GEOCODING_URL, params={"name": destination, "count": 1}
    )
    geocoded.raise_for_status()
    results = geocoded.json().get("results")
    if not results:
        return f"Couldn't find weather data for '{destination}'."

    place = results[0]
    forecast = await ctx.deps.http_client.get(
        FORECAST_URL,
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 7,
            "timezone": "auto",
        },
    )
    forecast.raise_for_status()
    daily = forecast.json().get("daily", {})
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    rain = daily.get("precipitation_probability_max", [])
    if not highs:
        return f"No forecast data returned for {place.get('name', destination)}."

    days = [
        f"day {i + 1}: {lo:.0f}-{hi:.0f}°C, {r}% chance of rain"
        for i, (hi, lo, r) in enumerate(zip(highs, lows, rain, strict=False))
    ]
    return f"Forecast for {place.get('name', destination)}: " + "; ".join(days)


@travel_agent.tool
async def search_flights(ctx: RunContext[TravelDeps], destination: str) -> str:
    """Search simulated flight inventory to this destination. Not real pricing."""
    options = flights_for(destination)
    listed = "; ".join(
        f"{f['airline']}: ${f['price_usd']}, {f['duration_hours']}h, {f['stops']} stop(s)"
        for f in options
    )
    return f"[SIMULATED inventory] Flight options to {destination}: {listed}"


@travel_agent.tool
async def search_hotels(ctx: RunContext[TravelDeps], destination: str) -> str:
    """Search simulated hotel inventory in this destination. Not real pricing."""
    options = hotels_for(destination)
    listed = "; ".join(
        f"{h['name']} ({h['area']}): ${h['price_usd_per_night']}/night, {h['rating']}★"
        for h in options
    )
    return f"[SIMULATED inventory] Hotel options in {destination}: {listed}"


# Human-readable labels for the progress log the UI streams alongside the
# partial itinerary, keyed by tool name.
TOOL_LABELS = {
    "get_weather": "Fetching live weather forecast",
    "search_flights": "Searching flight inventory",
    "search_hotels": "Searching hotel inventory",
}

"""Types for the Travel Itinerary Planner."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field


@dataclass
class TravelDeps:
    """The one dependency the weather tool needs: an HTTP client.

    Injecting the client (rather than importing `httpx` and constructing one
    inside the tool) is what makes `get_weather` testable offline: tests pass a
    client built on `httpx.MockTransport` instead of one that reaches the real
    Open-Meteo API, with zero changes to the tool itself.
    """

    http_client: httpx.AsyncClient


class DayPlan(BaseModel):
    day: int = Field(description="1-indexed day of the trip")
    summary: str = Field(description="What this day is built around")
    activities: list[str] = Field(default_factory=list)
    weather: str | None = Field(
        default=None, description="Forecast for this day, from the get_weather tool"
    )


class Itinerary(BaseModel):
    destination: str
    days: list[DayPlan] = Field(default_factory=list)
    estimated_cost_usd: int | None = None
    packing_notes: list[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    destination: str
    trip_days: int = Field(ge=1, le=14)
    interests: str = ""


class RefineRequest(BaseModel):
    session_id: str
    instruction: str

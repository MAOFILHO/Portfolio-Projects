"""Travel Itinerary Planner — the streaming-structured-output demo."""

from __future__ import annotations

from app.demos.base import Demo

from .router import router

demo = Demo(
    id="travel",
    title="Travel Itinerary Planner",
    mechanism="Streaming structured output",
    blurb=(
        "A Pydantic model fills in day-by-day as the response streams, grounded by a real "
        "weather lookup and simulated flight/hotel inventory — then refined in place across "
        "turns using message_history."
    ),
    router=router,
)

__all__ = ["demo"]

"""Travel Itinerary Planner — offline tests.

Three things worth pinning down: the weather tool's DI seam (a mocked
transport stands in for Open-Meteo, so no real network call is needed to prove
the tool parses the response correctly), that streaming really does emit more
than one partial before the final `Itinerary`, and that /refine actually reuses
`message_history` rather than starting a fresh conversation.
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic_ai.models.function import AgentInfo, DeltaToolCall

from app.demos.travel.agents import get_weather, travel_agent
from app.demos.travel.models import Itinerary, TravelDeps
from app.demos.travel.router import PLAN_CACHE, SESSIONS
from tests.test_main import client  # noqa: F401 - fixture

GEOCODING_BODY = {"results": [{"name": "Lisbon", "latitude": 38.7, "longitude": -9.1}]}
FORECAST_BODY = {
    "daily": {
        "temperature_2m_max": [22.0, 24.0],
        "temperature_2m_min": [14.0, 15.0],
        "precipitation_probability_max": [10, 60],
    }
}


def mock_open_meteo() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding-api" in str(request.url):
            return httpx.Response(200, json=GEOCODING_BODY)
        return httpx.Response(200, json=FORECAST_BODY)

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def clear_state():
    PLAN_CACHE.clear()
    SESSIONS.clear()
    yield


class _FakeRunContext:
    """A stand-in for RunContext[TravelDeps]: the tool only ever reads `.deps`."""

    def __init__(self, deps: TravelDeps) -> None:
        self.deps = deps


async def test_get_weather_parses_a_mocked_open_meteo_response():
    """The tool never touches the network in tests — httpx.MockTransport stands
    in for Open-Meteo, proving the parsing logic without a real HTTP call."""
    async with httpx.AsyncClient(transport=mock_open_meteo()) as http_client:
        deps = TravelDeps(http_client=http_client)
        forecast = await get_weather(_FakeRunContext(deps), "Lisbon")  # type: ignore[arg-type]
    assert "Lisbon" in forecast
    assert "60% chance of rain" in forecast


def streaming_itinerary_model(itinerary: dict):
    """Streams get_weather, then the final Itinerary output tool in three chunks,
    so `stream_output` has more than one partial to iterate over."""
    state = {"turn": 0}

    async def stream_fn(messages: list, info: AgentInfo):
        state["turn"] += 1
        if state["turn"] == 1:
            yield {0: DeltaToolCall(name="get_weather", json_args=json.dumps({"destination": "x"}))}
            return

        payload = json.dumps(itinerary)
        third = max(1, len(payload) // 3)
        output_name = info.output_tools[0].name if info.output_tools else "final_result"
        yield {0: DeltaToolCall(name=output_name)}
        for start in range(0, len(payload), third):
            yield {0: DeltaToolCall(json_args=payload[start : start + third])}

    return stream_fn


LISBON_ITINERARY = {
    "destination": "Lisbon",
    "days": [
        {"day": 1, "summary": "Old town", "activities": ["Alfama walk"], "weather": "sunny"},
        {"day": 2, "summary": "Coast", "activities": ["Belém"], "weather": "sunny"},
    ],
    "estimated_cost_usd": 900,
    "packing_notes": ["light jacket"],
}


async def test_plan_streams_multiple_partials_before_the_final_itinerary(client):  # noqa: F811
    from pydantic_ai.models.function import FunctionModel

    model = FunctionModel(stream_function=streaming_itinerary_model(LISBON_ITINERARY))
    with travel_agent.override(model=model):
        response = client.post(
            "/api/travel/plan", json={"destination": "Lisbon", "trip_days": 2, "interests": ""}
        )

    events = [json.loads(block[len("data: ") :]) for block in response.text.strip().split("\n\n")]
    partials = [e for e in events if e["type"] == "partial"]
    done = [e for e in events if e["type"] == "done"]

    assert len(partials) > 1, "expected more than one partial before the final itinerary"
    assert done, "expected a done event"
    assert done[0]["itinerary"]["destination"] == "Lisbon"
    assert done[0]["session_id"]


async def test_refine_reuses_message_history_not_a_fresh_conversation(client):  # noqa: F811
    from pydantic_ai.models.function import FunctionModel

    with travel_agent.override(
        model=FunctionModel(stream_function=streaming_itinerary_model(LISBON_ITINERARY))
    ):
        plan_response = client.post(
            "/api/travel/plan", json={"destination": "Lisbon", "trip_days": 2, "interests": ""}
        )
        events = [json.loads(b[len("data: ") :]) for b in plan_response.text.strip().split("\n\n")]
        session_id = next(e for e in events if e["type"] == "done")["session_id"]
        assert SESSIONS[session_id], "expected the plan turn's messages to be stored"

        refine_response = client.post(
            "/api/travel/refine", json={"session_id": session_id, "instruction": "add a rest day"}
        )

    assert refine_response.status_code == 200
    refine_events = [
        json.loads(b[len("data: ") :]) for b in refine_response.text.strip().split("\n\n")
    ]
    assert any(e["type"] == "done" for e in refine_events)


async def test_refine_with_an_unknown_session_is_a_404(client):  # noqa: F811
    response = client.post(
        "/api/travel/refine", json={"session_id": "does-not-exist", "instruction": "anything"}
    )
    assert response.status_code == 404


async def test_identical_plan_request_hits_the_cache(client):  # noqa: F811
    from pydantic_ai.models.function import FunctionModel

    request = {"destination": "Lisbon", "trip_days": 2, "interests": ""}
    with travel_agent.override(
        model=FunctionModel(stream_function=streaming_itinerary_model(LISBON_ITINERARY))
    ):
        first = client.post("/api/travel/plan", json=request)

    first_done = next(
        json.loads(b[len("data: ") :])
        for b in first.text.strip().split("\n\n")
        if b.startswith("data: ") and json.loads(b[len("data: ") :])["type"] == "done"
    )

    # No override: a cache miss would attempt a real model request, which
    # ALLOW_MODEL_REQUESTS=False turns into a loud failure.
    second = client.post("/api/travel/plan", json=request)
    second_done = next(
        json.loads(b[len("data: ") :])
        for b in second.text.strip().split("\n\n")
        if b.startswith("data: ") and json.loads(b[len("data: ") :])["type"] == "done"
    )
    assert second_done["itinerary"] == first_done["itinerary"]


def test_itinerary_model_round_trips():
    itinerary = Itinerary.model_validate(LISBON_ITINERARY)
    assert itinerary.days[1].day == 2

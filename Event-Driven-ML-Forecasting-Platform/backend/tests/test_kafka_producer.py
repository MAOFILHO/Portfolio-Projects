"""Unit tests for the Kafka producer's row-serialization logic.

No broker required: _row_to_message is a pure function, tested directly
against pandas rows. See src/kafka_producer.py's module docstring for why
this split exists.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from src.kafka_producer import _row_to_message  # noqa: E402


def _row(**overrides) -> pd.Series:
    base = {
        "dt": "1970-01-01",
        "AverageTemperature": 24.599,
        "AverageTemperatureUncertainty": 0.238,
        "City": "Bombay",
        "Country": "India",
        "Latitude": "18.48N",
        "Longitude": "72.68E",
    }
    base.update(overrides)
    return pd.Series(base)


def test_row_to_message_shape():
    message = _row_to_message(_row())
    assert set(message.keys()) == {"dt", "AverageTemperature", "City", "Country"}


def test_row_to_message_field_values_and_types():
    message = _row_to_message(_row())
    assert message["dt"] == "1970-01-01"
    assert message["AverageTemperature"] == 24.599
    assert isinstance(message["AverageTemperature"], float)
    assert message["City"] == "Bombay"
    assert message["Country"] == "India"


def test_row_to_message_handles_nan_temperature():
    """The raw dataset has missing readings; they must become JSON null, not be dropped or crash."""
    message = _row_to_message(_row(AverageTemperature=float("nan")))
    assert message["AverageTemperature"] is None


def test_row_to_message_handles_nan_city_or_country():
    message = _row_to_message(_row(City=float("nan"), Country=float("nan")))
    assert message["City"] is None
    assert message["Country"] is None


def test_row_to_message_is_json_serializable():
    import json

    message = _row_to_message(_row())
    encoded = json.dumps(message)
    decoded = json.loads(encoded)
    assert decoded == message


def test_row_to_message_never_returns_nan_directly():
    """A raw NaN would serialize to invalid JSON (`NaN` is not valid JSON) -- must always be None."""
    message = _row_to_message(_row(AverageTemperature=float("nan")))
    for value in message.values():
        assert not (isinstance(value, float) and math.isnan(value))

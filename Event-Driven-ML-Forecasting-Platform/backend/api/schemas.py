"""Pydantic response models for the temperature forecasting API."""
from __future__ import annotations

from pydantic import BaseModel


class Point(BaseModel):
    date: str
    value: float


class ForecastResult(BaseModel):
    forecast: list[Point]
    confidence_interval_lower: list[Point] | None = None
    confidence_interval_upper: list[Point] | None = None
    order: list[int] | str | None = None
    seasonal_order: list[int] | None = None
    metrics: dict[str, float] | None = None
    training_loss: list[float] | None = None


class MovingAveragesResponse(BaseModel):
    twelve_month: list[Point]
    five_year: list[Point]


class SeasonalDecompositionResponse(BaseModel):
    observed: list[Point]
    trend: list[Point]
    seasonal: list[Point]
    residual: list[Point]


class StationarityTestResult(BaseModel):
    test_statistic: float
    p_value: float
    lags_used: int
    is_stationary: bool
    num_observations: int | None = None
    critical_values: dict[str, float] | None = None


class StationarityResponse(BaseModel):
    adf: StationarityTestResult
    kpss: StationarityTestResult


class ModelInfo(BaseModel):
    key: str
    display_name: str
    framework: str
    hyperparams: dict
    has_result: bool
    metrics: dict[str, float] | None = None
    status: str


class RunJobResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    id: str
    model_key: str
    status: str
    result: ForecastResult | None = None
    error: str | None = None


class ComparisonModelEntry(BaseModel):
    key: str
    display_name: str
    framework: str
    forecast: list[Point]
    metrics: dict[str, float] | None = None


class ComparisonResponse(BaseModel):
    models: list[ComparisonModelEntry]


class HealthResponse(BaseModel):
    status: str


class WindowedFeatureEntry(BaseModel):
    """One (city, tumbling window) row from the Kafka streaming consumer's
    windowed-features Parquet snapshot (src/kafka_consumer.py)."""

    city: str
    window_start: str
    window_end: str
    avg_temperature: float
    min_temperature: float
    max_temperature: float
    event_count: int


class StreamingFeaturesResponse(BaseModel):
    streaming_active: bool
    features: list[WindowedFeatureEntry]

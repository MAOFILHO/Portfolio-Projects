"""Shared helpers for turning pandas time series into JSON-friendly structures."""
from __future__ import annotations

import pandas as pd


def series_to_points(series: pd.Series) -> list[dict]:
    """Convert a pandas Series with a DatetimeIndex into [{date, value}, ...], dropping NaNs."""
    clean = series.dropna()
    return [
        {"date": idx.strftime("%Y-%m-%d"), "value": float(val)}
        for idx, val in clean.items()
    ]

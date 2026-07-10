"""Load the global temperature dataset and narrow it down to Bombay (Mumbai).

Converted from notebook cells 10, 12, 14, 16, 18 (execution order 3-7).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .validation import validate_city_slice, validate_raw_data

logger = logging.getLogger(__name__)


def load_raw_data(data_path: str | Path) -> pd.DataFrame:
    """Read the raw GlobalLandTemperaturesByMajorCity CSV."""
    data_path = Path(data_path)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {data_path}. Set DATA_PATH to the correct location."
        )
    raw_data = pd.read_csv(data_path)
    validate_raw_data(raw_data, source=str(data_path))
    logger.info("Loaded raw dataset: %d rows, columns=%s", len(raw_data), list(raw_data.columns))
    logger.info("Raw data preview:\n%s", raw_data.head())
    return raw_data


def filter_india(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Filter the dataset to rows where Country == 'India'."""
    ind_df = raw_data.loc[raw_data["Country"] == "India"]
    logger.info("India cities available: %s", sorted(ind_df["City"].unique().tolist()))
    return ind_df


def select_bombay(raw_data: pd.DataFrame, source: str = "<unknown>") -> pd.DataFrame:
    """Filter the full dataset down to Bombay (Mumbai) records and return a working copy."""
    df = raw_data[raw_data.City == "Bombay"]
    data = df.copy()
    validate_city_slice(data, city="Bombay", source=source)
    logger.info("Bombay data preview:\n%s", data.head())
    return data


def load_bombay_data(data_path: str | Path) -> pd.DataFrame:
    """End-to-end: load CSV, filter to India, select Bombay, return a working copy."""
    raw_data = load_raw_data(data_path)
    filter_india(raw_data)  # kept for parity with notebook's exploratory step / logging
    return select_bombay(raw_data, source=str(data_path))

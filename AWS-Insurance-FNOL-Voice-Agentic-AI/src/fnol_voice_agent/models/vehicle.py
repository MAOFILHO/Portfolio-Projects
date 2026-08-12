"""Vehicle record schema -- matches `data/synthetic/vehicles/vehicles.json` field-for-field."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .policy import POLICY_NUMBER_PATTERN


class Vehicle(BaseModel):
    vin: str = Field(min_length=17, max_length=17)
    vin_check_digit_note: str
    policy_number: str = Field(pattern=POLICY_NUMBER_PATTERN)
    year: int
    make: str
    model: str
    plate: str
    actual_cash_value_cad: int

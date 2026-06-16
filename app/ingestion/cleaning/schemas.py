"""Pandera schema for the cleaned budget DataFrame (S7 Budget flattened)."""

from __future__ import annotations

import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

BUDGET_ID_PATTERN = r"^BUD-\d{4}-\d{3,4}$"

BudgetRecord: DataFrameSchema = DataFrameSchema(
    columns={
        "budget_id": Column(
            str,
            checks=Check.str_matches(BUDGET_ID_PATTERN),
            nullable=False,
            required=True,
        ),
        "client_name": Column(
            str,
            nullable=True,
            required=True,
        ),
        "sector": Column(
            str,
            checks=Check.isin(["finance", "ecommerce", "healthcare", "industrial"]),
            nullable=False,
            required=True,
        ),
        "country": Column(
            str,
            checks=Check.str_length(min_value=2, max_value=3),
            nullable=False,
            required=True,
        ),
        "main_technology": Column(str, nullable=False, required=True),
        "year": Column(int, checks=Check.in_range(2000, 2100), nullable=False, required=True),
        "total_estimated_hours": Column(
            int,
            checks=Check.ge(1),
            nullable=False,
            required=True,
        ),
    },
    strict=True,
    coerce=False,
)

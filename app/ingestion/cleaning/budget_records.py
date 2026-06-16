"""Reparable cleaning for the budget tabular view (S7 schema)."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

import pandas as pd

NULL_PLACEHOLDERS = {"TBD", "N/A", "n/a", "tbd", "", "null", "None", "-"}


def clean_budget_records(records: Iterable[dict]) -> pd.DataFrame:
    df = pd.DataFrame(list(records))
    if df.empty:
        return df

    for column in ("client_name", "project_summary"):
        if column in df.columns:
            df[column] = df[column].apply(
                lambda v: pd.NA if (isinstance(v, str) and v.strip() in NULL_PLACEHOLDERS) else v
            )

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    if "total_estimated_hours" in df.columns:
        df["total_estimated_hours"] = pd.to_numeric(df["total_estimated_hours"], errors="coerce")

    if {"budget_id", "year"}.issubset(df.columns):
        df["content_hash"] = df.apply(_content_hash, axis=1)
        df = df.sort_values(by=["budget_id", "year"], na_position="first")
        df = df.drop_duplicates(subset=["budget_id"], keep="last").reset_index(drop=True)

    return df


def _content_hash(row: pd.Series) -> str:
    payload = {
        k: (None if (isinstance(v, float) and pd.isna(v)) else _serializable(v))
        for k, v in row.items()
        if k != "content_hash"
    }
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _serializable(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value

"""Tests de utilidades de chat."""

from __future__ import annotations

from frontend.utils.formatting import format_timestamp, truncate


def test_truncate_long_text() -> None:
    assert truncate("a" * 200, 50).endswith("…")
    assert len(truncate("short", 50)) == 5


def test_format_timestamp_iso() -> None:
    assert "2026" in format_timestamp("2026-05-20T12:00:00+00:00")

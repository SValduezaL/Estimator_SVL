"""Badges HTML."""

from __future__ import annotations

from html import escape


def badge(label: str, *, variant: str = "") -> str:
    cls = "est-badge"
    if variant:
        cls += f" est-badge--{variant}"
    return f"<span class='{cls}'>{escape(label)}</span>"


def badges_row(items: list[tuple[str, str]]) -> str:
    return "<div class='est-meta-row'>" + "".join(badge(l, variant=v) for l, v in items) + "</div>"

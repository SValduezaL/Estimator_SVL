"""Renderizado de un mensaje de chat."""

from __future__ import annotations

import json
from html import escape
from typing import Any

import streamlit as st

from frontend.components.common.badges import badges_row
from frontend.components.estimation.estimation_result import render_estimation_inline
from frontend.utils.formatting import format_latency_ms, format_timestamp, format_usd


def render_chat_message(msg: dict[str, Any]) -> None:
    role = msg.get("role", "user")
    content = str(msg.get("content", ""))
    ts = format_timestamp(msg.get("timestamp"))
    css = "est-chat-user" if role == "user" else "est-chat-assistant"
    if role == "system":
        css = "est-chat-system"

    st.markdown(
        f"<div class='{css}'>"
        f"<div style='font-size:0.72rem;color:#94a3b8;margin-bottom:0.35rem'>"
        f"{escape(role.upper())} · {escape(ts)}"
        f"</div>"
        f"<div>{escape(content)}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    metrics = msg.get("metrics")
    if role == "assistant" and metrics:
        cache_hit = bool(metrics.get("cache_hit"))
        items = [
            (str(metrics.get("model", "—")), ""),
            (f"{int(metrics.get('total_tokens', 0))} tok", ""),
            (format_usd(float(metrics.get("cost_usd", 0.0)), precision=4), "accent"),
            (format_latency_ms(metrics.get("latency_ms", 0)), ""),
            ("cache hit" if cache_hit else "cache miss", "cache-hit" if cache_hit else "cache-miss"),
            (str(metrics.get("prompt_version", "—"))[:24], ""),
        ]
        rid = metrics.get("request_id")
        if rid:
            items.append((f"trace {str(rid)[:8]}", ""))
        st.markdown(badges_row(items), unsafe_allow_html=True)

        with st.expander("Detalle técnico del mensaje", expanded=False):
            tabs = st.tabs(["Resultado", "Métricas", "JSON", "Reasoning"])
            result = msg.get("result")
            with tabs[0]:
                if isinstance(result, dict):
                    render_estimation_inline(result)
                else:
                    st.info("Sin resultado estructurado.")
            with tabs[1]:
                st.json(metrics)
            with tabs[2]:
                raw = msg.get("raw_response")
                if raw:
                    st.json(raw)
                else:
                    st.json(msg)
            with tabs[3]:
                if isinstance(result, dict) and result.get("reasoning"):
                    st.markdown(str(result["reasoning"]))
                else:
                    st.caption("Sin reasoning.")

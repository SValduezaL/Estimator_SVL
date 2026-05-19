"""Interfaz Streamlit: formulario estructurado y cliente HTTP hacia la API."""

from __future__ import annotations

import os
from typing import Any

import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import (
    DETAIL_LEVEL_LABELS,
    PROJECT_TYPE_LABELS,
    DetailLevel,
    EstimationRequest,
    ProjectType,
)

load_dotenv()

MIN_DESCRIPTION_LEN = 20

_api_base = (
    (os.getenv("ESTIMATOR_API_BASE_URL") or os.getenv("API_BASE_URL") or "http://localhost:8000").rstrip("/")
)
ESTIMATE_ENDPOINT = f"{_api_base}/api/v1/estimate"

st.set_page_config(
    page_title="Estimador CAG",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

_preview_request = EstimationRequest(
    description="Texto de ejemplo para la vista previa del prompt (mín. 20 caracteres).",
    project_type=ProjectType.WEB_SAAS,
    detail_level=DetailLevel.MEDIUM,
)
_system_prompt, _user_prompt_preview = render_estimation_prompt(_preview_request)


def request_estimation(payload: dict[str, Any]) -> dict[str, Any]:
    """POST al endpoint de estimación y devuelve la respuesta JSON."""
    timeout = httpx.Timeout(300.0, connect=15.0)
    response = httpx.post(
        ESTIMATE_ENDPOINT,
        json=payload,
        timeout=timeout,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return response.json()


def _store_metrics_payload(data: dict[str, Any]) -> None:
    st.session_state.last_metrics_raw = dict(data)
    usage = data.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    st.session_state.last_metrics = {
        "model": str(data.get("model", "—")),
        "provider": str(data.get("provider", "—")),
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
        "response_seconds": float(data.get("response_seconds", 0.0)),
        "cache_hit": bool(data.get("cache_hit", False)),
        "finish_reason": str(data.get("finish_reason", "—")),
        "cost_usd": float(data.get("cost_usd", 0.0)),
        "usage_available": data.get("usage_available"),
        "prompt_version": str(data.get("prompt_version", "—")),
        "prompt_version_created_at": str(data.get("prompt_version_created_at", "—")),
    }


def _render_estimation_result(result: dict[str, Any]) -> None:
    st.markdown(f"**{result.get('summary', '')}**")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Confianza", f"{result.get('confidence_pct', 0)} %")
    with c2:
        st.metric("Duración", f"{result.get('total_duration_weeks', 0)} sem")
    with c3:
        st.metric("Coste total", f"{int(result.get('total_cost_eur', 0)):,} EUR".replace(",", "."))

    phases = result.get("phases") or []
    if phases:
        st.subheader("Fases")
        st.dataframe(
            pd.DataFrame(phases),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Justificación (reasoning)", expanded=True):
        st.markdown(str(result.get("reasoning", "")))


if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None
if "last_metrics_raw" not in st.session_state:
    st.session_state.last_metrics_raw = None

st.title("Estimador de software (CAG)")
st.caption("Formulario estructurado; la API devuelve un ``EstimationResult`` validado.")

with st.form("estimation_form"):
    description = st.text_area(
        "Descripción del proyecto",
        height=180,
        placeholder="Describe alcance, integraciones conocidas, plazos y restricciones (mín. 20 caracteres).",
    )
    c1, c2 = st.columns(2)
    with c1:
        project_type = st.selectbox(
            "Tipo de proyecto",
            options=list(ProjectType),
            format_func=lambda p: PROJECT_TYPE_LABELS[p],
        )
    with c2:
        detail_level = st.selectbox(
            "Nivel de detalle",
            options=list(DetailLevel),
            format_func=lambda d: DETAIL_LEVEL_LABELS[d],
        )
    submitted = st.form_submit_button("Generar estimación")

if submitted:
    desc = (description or "").strip()
    if len(desc) < MIN_DESCRIPTION_LEN:
        st.error(
            f"La descripción tiene {len(desc)} caracteres; la API exige al menos {MIN_DESCRIPTION_LEN}."
        )
    else:
        try:
            req = EstimationRequest(
                description=desc,
                project_type=project_type,
                detail_level=detail_level,
            )
        except Exception as exc:
            st.error(f"Datos no válidos: {exc}")
        else:
            payload = req.model_dump(mode="json")
            try:
                with st.spinner("Generando estimación..."):
                    data = request_estimation(payload)
                _store_metrics_payload(data)
                st.subheader("Resultado")
                result = data.get("result")
                if isinstance(result, dict):
                    _render_estimation_result(result)
                else:
                    st.warning("La respuesta no incluye ``result`` estructurado.")
            except httpx.HTTPError as exc:
                st.error(
                    f"No se pudo conectar con la API en `{ESTIMATE_ENDPOINT}`.\n\nDetalle: `{exc}`"
                )
            except Exception as exc:  # pragma: no cover
                st.warning(
                    "Error al generar la estimación. Revisa claves LLM y logs del servidor.\n\n"
                    f"Detalle: `{exc}`"
                )

with st.sidebar:
    st.header("Estimador CAG")
    st.caption("Cliente del servicio FastAPI con respuesta JSON estructurada.")

    tab_help, tab_cag, tab_srv, tab_metrics = st.tabs(["Cómo funciona", "Prompt CAG", "Servidor", "Métricas"])

    with tab_help:
        st.markdown(
            """
**1. Contexto fijo (CAG)**  
Plantillas Jinja2 v3 (`estimation-v3-structured`) con few-shot JSON por tipo de proyecto.

**2. Formulario**  
`EstimationRequest` → `POST /api/v1/estimate`.

**3. Respuesta**  
`EstimationResponse.result` (`EstimationResult`): fases, totales y ``reasoning`` en Markdown.

**4. Caché Redis (opcional)**  
Peticiones idénticas pueden devolver `cache_hit: true`.
            """.strip()
        )
        st.divider()
        st.markdown(
            f"**Validación:** la descripción debe tener al menos **{MIN_DESCRIPTION_LEN}** caracteres."
        )
        st.link_button("Abrir documentación OpenAPI", f"{_api_base}/docs")

    with tab_cag:
        st.markdown(
            "Vista previa con `EstimationRequest` de ejemplo (web SaaS / detalle medio). "
            "Few-shots JSON en `app/fixtures/estimation_examples/`."
        )
        st.text_area("System prompt (solo lectura)", value=_system_prompt, height=200, disabled=True)
        st.text_area("User prompt (solo lectura)", value=_user_prompt_preview, height=160, disabled=True)

    with tab_srv:
        st.subheader("Conexión")
        st.code(ESTIMATE_ENDPOINT, language="text")
        st.divider()
        st.subheader("Entorno local (solo lectura)")
        redis_hint = "sí" if (os.getenv("REDIS_URL") or "").strip() else "no"
        st.markdown(
            f"| Variable | Valor |\n|---|---|\n"
            f"| `LLM_MODEL` | `{os.getenv('LLM_MODEL', '—')}` |\n"
            f"| `LLM_FALLBACK_MODEL` | `{os.getenv('LLM_FALLBACK_MODEL', '—')}` |\n"
            f"| `REDIS_URL` | *{redis_hint}* |\n"
            f"| `CACHE_TTL_SECONDS` | `{os.getenv('CACHE_TTL_SECONDS', '86400')}` |\n"
        )

    with tab_metrics:
        st.subheader("Última respuesta del servidor")
        if st.session_state.last_metrics:
            m = st.session_state.last_metrics

            st.markdown(f"**Modelo**: {m.get('model', '—')}")
            st.markdown(f"**Proveedor:** {m.get('provider', '—')}")
            st.markdown(f"**Versión de prompt:** {m.get('prompt_version', '—')}")
            st.markdown(
                f"**Fecha de referencia del bundle:** {m.get('prompt_version_created_at', '—')}"
            )

            t1, t2, t3 = st.columns(3)
            with t1:
                st.metric("Tokens entrada", f"{int(m['input_tokens']):,}".replace(",", "."))
            with t2:
                st.metric("Tokens salida", f"{int(m['output_tokens']):,}".replace(",", "."))
            with t3:
                st.metric("Tokens total", f"{int(m.get('total_tokens', 0)):,}".replace(",", "."))

            r1, r2, r3 = st.columns(3)
            with r1:
                st.metric("Tiempo", f"{float(m['response_seconds']):.2f} s")
            with r2:
                st.metric("Motivo de fin", f"{m.get('finish_reason', '—')}")
            with r3:
                st.metric("Caché Redis", "hit" if m["cache_hit"] else "miss")

            ua = m.get("usage_available")
            ua_txt = "desconocido" if ua is None else ("true" if ua else "false")
            st.metric(label="usage_available", value=ua_txt)

            st.markdown(
                f"<span style='font-size:26px'>"
                f"<b>Coste estimado: </b> {float(m.get('cost_usd', 0.0)):.6f} usd"
                f"</span>",
                unsafe_allow_html=True,
            )

            if st.session_state.last_metrics_raw:
                with st.expander("JSON completo de la respuesta"):
                    st.json(st.session_state.last_metrics_raw)
        else:
            st.info("Aún no hay métricas en esta sesión. Envía el formulario principal.")

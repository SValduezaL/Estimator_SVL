"""Interfaz Streamlit: formulario estructurado y streaming SSE hacia la API."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv

from app.prompts.loader import render_estimation_prompt
from app.schemas.estimation import (
    DETAIL_LEVEL_LABELS,
    OUTPUT_FORMAT_LABELS,
    PROJECT_TYPE_LABELS,
    DetailLevel,
    EstimationRequest,
    OutputFormat,
    ProjectType,
)

load_dotenv()

MIN_DESCRIPTION_LEN = 20

_api_base = (
    (os.getenv("ESTIMATOR_API_BASE_URL") or os.getenv("API_BASE_URL") or "http://localhost:8000").rstrip("/")
)
STREAM_ENDPOINT = f"{_api_base}/api/v1/estimate"

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
    output_format=OutputFormat.LINE_ITEMS,
)
_system_prompt, _user_prompt_preview = render_estimation_prompt(_preview_request)


def _sse_data_payload(line: str) -> str:
    if line.startswith("data: "):
        return line[6:]
    if line.startswith("data:"):
        return line[5:]
    return line


def stream_estimation_events(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """POST al endpoint SSE y emite eventos (token, metrics, done, error)."""
    timeout = httpx.Timeout(300.0, connect=15.0)
    with httpx.stream(
        "POST",
        STREAM_ENDPOINT,
        json=payload,
        timeout=timeout,
        headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
    ) as response:
        response.raise_for_status()
        current_event = "message"
        data_lines: list[str] = []
        for raw_line in response.iter_lines():
            if raw_line is None:
                continue
            if raw_line == "":
                if data_lines:
                    payload_raw = "\n".join(data_lines)
                    data_lines = []
                    if current_event == "token":
                        yield {"event": "token", "data": payload_raw}
                    elif current_event == "done":
                        yield {"event": "done", "data": payload_raw}
                    elif current_event == "metrics":
                        try:
                            parsed = json.loads(payload_raw)
                        except json.JSONDecodeError:
                            parsed = {}
                        yield {"event": "metrics", "data": parsed}
                    elif current_event == "error":
                        yield {"event": "error", "data": payload_raw}
                    else:
                        try:
                            yield {"event": current_event, "data": json.loads(payload_raw)}
                        except json.JSONDecodeError:
                            yield {"event": current_event, "data": {"raw": payload_raw}}
                current_event = "message"
                continue
            if raw_line.startswith("event:"):
                current_event = raw_line[6:].strip() or "message"
            elif raw_line.startswith("data:"):
                data_lines.append(_sse_data_payload(raw_line))


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
    }


if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None
if "last_metrics_raw" not in st.session_state:
    st.session_state.last_metrics_raw = None

st.title("Estimador de software (CAG)")
st.caption("Formulario estructurado; la estimación llega en streaming con `st.write_stream`.")

with st.form("estimation_form"):
    description = st.text_area(
        "Descripción del proyecto",
        height=180,
        placeholder="Describe alcance, integraciones conocidas, plazos y restricciones (mín. 20 caracteres).",
    )
    c1, c2, c3 = st.columns(3)
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
    with c3:
        output_format = st.selectbox(
            "Formato de salida",
            options=list(OutputFormat),
            format_func=lambda o: OUTPUT_FORMAT_LABELS[o],
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
                output_format=output_format,
            )
        except Exception as exc:
            st.error(f"Datos no válidos: {exc}")
        else:
            payload = req.model_dump(mode="json")
            sse_errors: list[str] = []

            def estimation_token_stream() -> Iterator[str]:
                for event in stream_estimation_events(payload):
                    et = str(event.get("event", ""))
                    data = event.get("data")
                    if et == "token" and isinstance(data, str) and data:
                        yield data
                    elif et == "metrics" and isinstance(data, dict):
                        _store_metrics_payload(data)
                    elif et == "error":
                        msg = data if isinstance(data, str) else str(data)
                        sse_errors.append(msg or "Error SSE")
                        return
                    elif et == "done":
                        pass

            try:
                st.subheader("Resultado")
                st.write_stream(estimation_token_stream())
                if sse_errors:
                    st.error(sse_errors[0])
            except httpx.HTTPError as exc:
                st.error(
                    f"No se pudo conectar con la API en `{STREAM_ENDPOINT}`.\n\nDetalle: `{exc}`"
                )
            except Exception as exc:  # pragma: no cover
                st.warning(
                    "Error al generar la estimación. Revisa claves LLM y logs del servidor.\n\n"
                    f"Detalle: `{exc}`"
                )

# El sidebar debe ir después del streaming: `st.write_stream` actualiza
# `session_state` durante la misma ejecución; si pintamos métricas antes,
# Streamlit muestra siempre el valor de la petición anterior.
with st.sidebar:
    st.header("Estimador CAG")
    st.caption("Cliente del servicio FastAPI con streaming SSE (Server-Sent Events).")

    tab_help, tab_cag, tab_srv, tab_metrics = st.tabs(["Cómo funciona", "Prompt CAG", "Servidor", "Métricas"])

    with tab_help:
        st.markdown(
            """
**1. Contexto fijo (CAG)**  
El backend renderiza plantillas Jinja2 versionadas (`app/prompts/estimation/v1/`)
con rol de estimador, reglas por `detail_level` / `output_format` y few-shot en `examples.j2`.

**2. Formulario estructurado**  
La descripción del proyecto y los selectores se serializan como `EstimationRequest`
(JSON) hacia `POST /api/v1/estimate`.

**3. Streaming (SSE)**  
La API emite `token` (texto), `metrics` (JSON) y `done`. Esta interfaz usa
`st.write_stream` con un generador que solo hace `yield` de los tokens; el
JSON de `metrics` se guarda en `st.session_state` al llegar el evento.

**4. Caché Redis (opcional)**  
Si el servidor tiene `REDIS_URL`, peticiones idénticas pueden responder desde
caché (`cache_hit: true` en `metrics`) sin llamar al LLM.
            """.strip()
        )
        st.divider()
        st.markdown(
            f"**Validación:** la descripción debe tener al menos **{MIN_DESCRIPTION_LEN}** caracteres."
        )
        st.link_button("Abrir documentación OpenAPI", f"{_api_base}/docs")

    with tab_cag:
        st.markdown(
            "Vista previa con `EstimationRequest` de ejemplo (web SaaS / detalle medio / partidas en tabla). "
            "Los few-shot viven en `examples.j2`."
        )
        st.text_area("System prompt (solo lectura)", value=_system_prompt, height=200, disabled=True)
        st.text_area("User prompt (solo lectura)", value=_user_prompt_preview, height=160, disabled=True)

    with tab_srv:
        st.subheader("Conexión")
        st.code(STREAM_ENDPOINT, language="text")
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
            st.metric(
                label="usage_available",
                value=ua_txt,
                help=(
                    "Indica si el proveedor devolvió uso de tokens en el stream. "
                    " `true`: al menos un chunk incluía usage. "
                    " `false`: no hubo metadatos de uso en los chunks, en cuyo caso "
                    "los contadores serán 0, salvo que vengan de caché u otra fuente."
                ),
            )

            st.markdown(
                f"<span style='font-size:26px'>"
                f"<b>Coste estimado: </b> {float(m.get('cost_usd', 0.0)):.6f} usd"
                f"</span>",
                unsafe_allow_html=True,
            )

            if st.session_state.last_metrics_raw:
                with st.expander("JSON completo del evento `metrics`"):
                    st.json(st.session_state.last_metrics_raw)
        else:
            st.info("Aún no hay métricas en esta sesión. Envía el formulario principal.")

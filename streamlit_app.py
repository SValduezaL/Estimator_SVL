"""Interfaz Streamlit: formulario estructurado y cliente HTTP hacia la API."""

from __future__ import annotations

import os
from typing import Any

import httpx
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
_MAX_PROMPT_PREVIEW_CHARS = 80_000

_api_base = (
    (os.getenv("ESTIMATOR_API_BASE_URL") or os.getenv("API_BASE_URL") or "http://localhost:8000").rstrip("/")
)
ESTIMATE_ENDPOINT = f"{_api_base}/api/v1/estimate"

_PHASE_COLUMNS = (
    "name",
    "deliverable",
    "stack",
    "hours",
    "cost_eur",
    "confidence_pct",
    "risks_notes",
)
_PHASE_HEADERS = {
    "name": "Fase",
    "deliverable": "Entregable",
    "stack": "Stack",
    "hours": "Horas",
    "cost_eur": "Coste (EUR)",
    "confidence_pct": "Conf. %",
    "risks_notes": "Riesgos / notas",
}


def _stat_cell(label: str, value: str, *, bordered: bool = True) -> None:
    """Métrica sin ``st.metric`` (evita chunk JS ``Metric.*.js``)."""
    box_style = "padding:0.35rem 0.5rem"
    if bordered:
        box_style += ";border:1px solid rgba(128,128,128,0.35);border-radius:0.4rem"
    st.markdown(
        f"<div style='{box_style}'>"
        f"<div style='font-size:0.8rem;opacity:0.85'>{label}</div>"
        f"<div style='font-size:1.35rem;font-weight:600;margin-top:0.15rem'>{value}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def _phases_markdown_table(phases: list[dict[str, Any]]) -> str:
    headers = [_PHASE_HEADERS.get(c, c) for c in _PHASE_COLUMNS]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in phases:
        cells: list[str] = []
        for col in _PHASE_COLUMNS:
            raw = row.get(col)
            if raw is None or raw == "":
                cells.append("—")
            elif col == "cost_eur":
                cells.append(f"{int(raw):,}".replace(",", "."))
            elif col == "stack":
                if isinstance(raw, list):
                    cells.append(", ".join(str(item) for item in raw if item))
                else:
                    cells.append("—")
            else:
                cells.append(str(raw).replace("|", "\\|"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


st.set_page_config(
    page_title="Estimador CAG",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


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
        "prompt_version": str(data.get("prompt_version", "—")),
        "prompt_version_created_at": str(data.get("prompt_version_created_at", "—")),
    }


def _render_estimation_result(result: dict[str, Any]) -> None:
    st.markdown(f"**{result.get('summary', '')}**")
    c1, c2, c3 = st.columns(3)
    with c1:
        _stat_cell("Confianza", f"{result.get('confidence_pct', 0)} %")
    with c2:
        _stat_cell("Duración", f"{result.get('total_duration_weeks', 0)} sem")
    with c3:
        _stat_cell(
            "Coste total",
            f"{int(result.get('total_cost_eur', 0)):,} EUR".replace(",", "."),
        )

    phases = result.get("phases") or []
    if phases:
        st.subheader("Fases")
        st.markdown(_phases_markdown_table(phases))

    with st.expander("Justificación", expanded=True):
        st.markdown(str(result.get("reasoning", "")))


def _render_prompt_preview_block(label: str, content: str) -> None:
    """Vista previa de solo lectura sin ``st.text_area`` (evita fallos del chunk TextArea)."""
    truncated = len(content) > _MAX_PROMPT_PREVIEW_CHARS
    shown = content if not truncated else content[:_MAX_PROMPT_PREVIEW_CHARS] + "\n\n… [truncado]"
    st.caption(f"{label} — {len(content):,} caracteres".replace(",", "."))
    if truncated:
        st.warning("Vista previa truncada en la UI; el prompt completo se envía al LLM sin recorte.")
    st.code(shown, language="text", line_numbers=True)


def _refresh_prompt_preview(request: EstimationRequest) -> None:
    system_prompt, user_prompt = render_estimation_prompt(request)
    st.session_state.prompt_preview = {
        "system": system_prompt,
        "user": user_prompt,
        "key": (
            request.project_type.value,
            request.detail_level.value,
            hash(request.description),
        ),
    }


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
        key="project_description",
    )
    c1, c2 = st.columns(2)
    with c1:
        project_type = st.selectbox(
            "Tipo de proyecto",
            options=list(ProjectType),
            format_func=lambda p: PROJECT_TYPE_LABELS[p],
            key="project_type",
        )
    with c2:
        detail_level = st.selectbox(
            "Nivel de detalle",
            options=list(DetailLevel),
            format_func=lambda d: DETAIL_LEVEL_LABELS[d],
            key="detail_level",
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
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                try:
                    body = exc.response.json()
                    if isinstance(body, dict) and body.get("detail"):
                        detail = body["detail"]
                except Exception:
                    pass
                st.error(
                    f"Error de la API ({exc.response.status_code}) en `{ESTIMATE_ENDPOINT}`.\n\n"
                    f"**Detalle:** {detail}"
                )
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

**Si ves errores de chunks JS** (`TextArea`, `Metric`, `DataFrame`): recarga forzada
(Ctrl+F5) o reinicia `streamlit run`. Esta UI evita esos widgets cuando es posible.
            """.strip()
        )
        st.divider()
        st.markdown(
            f"**Validación:** la descripción debe tener al menos **{MIN_DESCRIPTION_LEN}** caracteres "
            f"(máx. 2000 en la API)."
        )
        st.link_button("Abrir documentación OpenAPI", f"{_api_base}/docs")

    with tab_cag:
        st.markdown(
            "Vista previa del prompt renderizado (solo lectura, vía `st.code` — no `text_area` deshabilitado)."
        )
        prev_desc = st.text_input(
            "Descripción para la vista previa",
            value="Texto de ejemplo para la vista previa del prompt (mín. 20 caracteres).",
            key="preview_description",
        )
        pc1, pc2 = st.columns(2)
        with pc1:
            prev_type = st.selectbox(
                "Tipo (preview)",
                options=list(ProjectType),
                format_func=lambda p: PROJECT_TYPE_LABELS[p],
                key="preview_project_type",
            )
        with pc2:
            prev_level = st.selectbox(
                "Detalle (preview)",
                options=list(DetailLevel),
                format_func=lambda d: DETAIL_LEVEL_LABELS[d],
                key="preview_detail_level",
            )

        if st.button("Actualizar vista previa del prompt", key="btn_refresh_prompt_preview"):
            try:
                preview_req = EstimationRequest(
                    description=(prev_desc or "").strip(),
                    project_type=prev_type,
                    detail_level=prev_level,
                )
            except Exception as exc:
                st.error(f"No se pudo construir la petición de preview: {exc}")
            else:
                _refresh_prompt_preview(preview_req)

        preview = st.session_state.get("prompt_preview")
        if preview:
            with st.expander("System prompt", expanded=False):
                _render_prompt_preview_block("System", preview["system"])
            with st.expander("User prompt", expanded=False):
                _render_prompt_preview_block("User", preview["user"])
        else:
            st.info("Pulsa «Actualizar vista previa del prompt» para renderizar los templates.")

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

            m1, m2 = st.columns(2)
            with m1:
                _stat_cell("Modelo", str(m.get("model", "—")), bordered=False)
            with m2:
                _stat_cell("Proveedor", str(m.get("provider", "—")), bordered=False)

            p1, p2 = st.columns(2)
            with p1:
                _stat_cell(
                    "Versión del prompt",
                    str(m.get("prompt_version", "—")),
                    bordered=False,
                )
            with p2:
                _stat_cell(
                    "Fecha del bundle",
                    str(m.get("prompt_version_created_at", "—")),
                    bordered=False,
                )

            t1, t2, t3 = st.columns(3)
            with t1:
                _stat_cell(
                    "Tokens entrada",
                    f"{int(m['input_tokens']):,}".replace(",", "."),
                    bordered=False,
                )
            with t2:
                _stat_cell(
                    "Tokens salida",
                    f"{int(m['output_tokens']):,}".replace(",", "."),
                    bordered=False,
                )
            with t3:
                _stat_cell(
                    "Tokens total",
                    f"{int(m.get('total_tokens', 0)):,}".replace(",", "."),
                    bordered=False,
                )

            r1, r2, r3 = st.columns(3)
            with r1:
                _stat_cell("Tiempo", f"{float(m['response_seconds']):.2f} s", bordered=False)
            with r2:
                _stat_cell("Motivo de fin", f"{m.get('finish_reason', '—')}", bordered=False)
            with r3:
                _stat_cell(
                    "Caché Redis",
                    "hit" if m["cache_hit"] else "miss",
                    bordered=False,
                )

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

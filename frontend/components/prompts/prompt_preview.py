"""Vista previa de prompts CAG."""

from __future__ import annotations

import streamlit as st

from app.foundation.prompts.loader import render_estimation_prompt
from app.domain.schemas.estimation import (
    DETAIL_LEVEL_LABELS,
    PROJECT_TYPE_LABELS,
    DetailLevel,
    EstimationRequest,
    ProjectType,
)
from app.generation.conversation.models import ProjectMetadata
from frontend.state.session_state import get_active_session_id, get_session_record
from frontend.styles.constants import MAX_PROMPT_PREVIEW_CHARS, MIN_DESCRIPTION_LEN


def _render_block(label: str, content: str) -> None:
    truncated = len(content) > MAX_PROMPT_PREVIEW_CHARS
    shown = content if not truncated else content[:MAX_PROMPT_PREVIEW_CHARS] + "\n\n… [truncado]"
    st.caption(f"{label} — {len(content):,} caracteres".replace(",", "."))
    if truncated:
        st.warning("Vista previa truncada; el prompt completo se envía al LLM.")
    st.code(shown, language="text")
    if st.button(f"Copiar {label}", key=f"copy_{label}"):
        st.session_state[f"clipboard_{label}"] = content
        st.toast(f"{label} listo (usa el bloque de código para copiar).")


def render_prompt_tab() -> None:
    active = get_active_session_id()
    metadata: ProjectMetadata | None = None
    if active:
        rec = get_session_record(active)
        if rec:
            md = rec.get("metadata_current") or {}
            if md:
                metadata = ProjectMetadata.model_validate(md)

    prev_desc = st.text_area(
        "Descripción para preview",
        value="Texto de ejemplo para la vista previa del prompt (mín. 20 caracteres).",
        height=100,
        key="prompt_preview_description",
    )
    c1, c2 = st.columns(2)
    with c1:
        prev_type = st.selectbox(
            "Tipo",
            options=list(ProjectType),
            format_func=lambda p: PROJECT_TYPE_LABELS[p],
            key="prompt_preview_type",
        )
    with c2:
        prev_level = st.selectbox(
            "Detalle",
            options=list(DetailLevel),
            format_func=lambda d: DETAIL_LEVEL_LABELS[d],
            key="prompt_preview_level",
        )

    include_memory = st.checkbox(
        "Inyectar metadata de sesión activa",
        value=metadata is not None,
        disabled=metadata is None,
        key="prompt_include_memory",
    )

    if st.button("Renderizar prompts", type="primary", key="btn_render_prompts"):
        desc = (prev_desc or "").strip()
        if len(desc) < MIN_DESCRIPTION_LEN:
            st.error(f"Mínimo {MIN_DESCRIPTION_LEN} caracteres.")
            return
        try:
            req = EstimationRequest(
                description=desc,
                project_type=prev_type,
                detail_level=prev_level,
            )
            pm = metadata if include_memory and metadata else None
            system_prompt, user_prompt = render_estimation_prompt(req, project_metadata=pm)
            st.session_state.prompt_preview = {
                "system": system_prompt,
                "user": user_prompt,
                "metadata": pm.model_dump() if pm else None,
            }
        except Exception as exc:
            st.error(str(exc))

    preview = st.session_state.get("prompt_preview")
    if not preview:
        st.info("Pulsa «Renderizar prompts» para generar la vista previa local (Jinja2).")
        return

    if preview.get("metadata"):
        with st.expander("Metadata inyectada en system", expanded=True):
            st.json(preview["metadata"])

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("System prompt", expanded=True):
            _render_block("System", preview["system"])
    with c2:
        with st.expander("User prompt", expanded=True):
            _render_block("User", preview["user"])

    est_tokens = (len(preview["system"]) + len(preview["user"])) // 4
    st.caption(f"Tokens estimados (≈ chars/4): **{est_tokens:,}**".replace(",", "."))

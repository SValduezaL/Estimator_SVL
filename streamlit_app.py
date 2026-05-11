"""Interfaz Streamlit tipo chat para el estimador CAG.

Streamlit actúa como cliente HTTP de FastAPI: hace POST a
``/api/v1/estimate/stream`` y pinta los fragmentos SSE con
``st.write_stream`` (generador que solo hace ``yield`` de texto). Las
métricas del evento ``metrics`` se guardan en ``st.session_state`` en el mismo
recorrido. La URL base se lee de ``ESTIMATOR_API_BASE_URL`` o ``API_BASE_URL``
(mismo ``.env`` que la API vía ``load_dotenv``).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st
from dotenv import load_dotenv

from app.context.examples import CANONICAL_EXAMPLES, format_examples_for_prompt, select_examples
from app.services.llm_service import GenerationOptions, build_system_prompt

load_dotenv()

MIN_TRANSCRIPTION_LEN = 50

_api_base = (
    (os.getenv("ESTIMATOR_API_BASE_URL") or os.getenv("API_BASE_URL") or "http://localhost:8000").rstrip("/")
)
STREAM_ENDPOINT = f"{_api_base}/api/v1/estimate/stream"

st.set_page_config(
    page_title="Estimador CAG",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

_default_opts = GenerationOptions()
_system_prompt = build_system_prompt(_default_opts)
_examples_json = format_examples_for_prompt(select_examples(len(CANONICAL_EXAMPLES)), fmt="json")


def _sse_data_payload(line: str) -> str:
    """Extrae el cuerpo tras ``data:`` respetando el espacio opcional del framing SSE."""
    if line.startswith("data: "):
        return line[6:]
    if line.startswith("data:"):
        return line[5:]
    return line


def stream_estimation_events(
    transcription: str,
    *,
    skip_cache: bool = False,
    model: str | None = None,
    max_tokens: int | None = None,
    example_format: str = "markdown",
    use_examples: bool = True,
) -> Iterator[dict[str, Any]]:
    """POST al endpoint SSE y emite eventos tipados (token, metrics, done, error)."""
    payload: dict[str, Any] = {
        "transcription": transcription,
        "preprocessing": "none",
        "skip_cache": skip_cache,
        "use_examples": use_examples,
        "example_format": example_format,
    }
    if model:
        payload["model"] = model
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

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
    """Persiste el JSON del evento SSE ``metrics`` para el panel lateral."""
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
    }
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None
if "last_metrics_raw" not in st.session_state:
    st.session_state.last_metrics_raw = None

with st.sidebar:
    st.header("Estimador CAG")
    st.caption("Cliente del servicio FastAPI con streaming SSE (Server-Sent Events).")

    tab_help, tab_cag, tab_srv, tab_metrics = st.tabs(["Cómo funciona", "Prompt CAG", "Servidor", "Métricas"])

    with tab_help:
        st.markdown(
            """
**1. Contexto fijo (CAG)**  
El backend construye un *system prompt* con tu rol de estimador y ejemplos
históricos (few-shot). Eso estabiliza formato y criterios antes de leer la
transcripción.

**2. Tu mensaje**  
La transcripción va en el mensaje de *usuario*. El modelo genera la
estimación en **Markdown** (tablas, secciones) para esa reunión.

**3. Streaming (SSE)**  
La API emite `token` (texto), `metrics` (JSON) y `done`. Esta interfaz usa
`st.write_stream` con un generador que solo hace `yield` de los tokens; el
JSON de `metrics` se guarda para el panel lateral.

**4. Caché Redis (opcional)**  
Si el servidor tiene `REDIS_URL`, peticiones idénticas pueden responder desde
caché (`cache_hit: true` en `metrics`) sin llamar al LLM.
            """.strip()
        )
        st.divider()
        st.markdown(
            f"**Validación:** la transcripción debe tener al menos **{MIN_TRANSCRIPTION_LEN}** caracteres."
        )
        st.link_button("Abrir documentación OpenAPI", f"{_api_base}/docs")

    with tab_cag:
        st.markdown(
            "Vista previa de lo que usa el backend (`build_system_prompt` + ejemplos canónicos). "
            "El formato de ejemplos de la petición se elige en la pestaña **Servidor**."
        )
        st.text_area("System prompt (solo lectura)", value=_system_prompt, height=200, disabled=True)
        st.text_area("Ejemplos (JSON, solo lectura)", value=_examples_json, height=220, disabled=True)

    with tab_srv:
        st.subheader("Conexión y payload")
        st.code(STREAM_ENDPOINT, language="text")
        st.checkbox(
            "Forzar `skip_cache` (no leer ni escribir Redis en esta petición)",
            value=False,
            key="srv_skip_cache",
        )
        st.text_input(
            "Override de modelo (opcional)",
            placeholder="Vacío = modelo del servidor (.env)",
            key="srv_model",
        )
        st.number_input(
            "max_tokens (0 = omitir; usa el default del servidor)",
            min_value=0,
            max_value=16000,
            value=0,
            key="srv_max_tokens",
        )
        st.selectbox(
            "Formato de ejemplos CAG en el prompt",
            options=["markdown", "json", "narrative"],
            index=0,
            key="srv_example_format",
        )
        st.checkbox("Incluir bloque de ejemplos (`use_examples`)", value=True, key="srv_use_examples")

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
        if st.button("Borrar historial del chat", type="secondary"):
            st.session_state.messages = []
            st.session_state.last_metrics = None
            st.session_state.last_metrics_raw = None
            st.rerun()

    with tab_metrics:
        st.subheader("Última respuesta del servidor")
        if st.session_state.last_metrics:
            m = st.session_state.last_metrics

            st.markdown(f"**Modelo**: {m.get('model', '—')}")
            st.markdown(f"**Proveedor:** {m.get('provider', '—')}")

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
            st.info("Aún no hay métricas en esta sesión. Envía una transcripción válida.")

st.title("Estimador de software (CAG)")
st.caption(
    "Pega una transcripción de reunión; la estimación llega en texto/Markdown "
    "en streaming con ``st.write_stream``."
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Transcripción de la reunión (mín. 50 caracteres)...")

if prompt:
    if len(prompt) < MIN_TRANSCRIPTION_LEN:
        st.error(
            f"La transcripción tiene {len(prompt)} caracteres; la API exige al menos {MIN_TRANSCRIPTION_LEN}."
        )
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        skip_cache = bool(st.session_state.get("srv_skip_cache", False))
        model_raw = (st.session_state.get("srv_model") or "").strip()
        model_override = model_raw or None
        max_tok = int(st.session_state.get("srv_max_tokens") or 0)
        max_tokens_payload = None if max_tok == 0 else max_tok
        example_fmt = str(st.session_state.get("srv_example_format") or "markdown")
        use_examples = bool(st.session_state.get("srv_use_examples", True))

        assistant_reply = ""
        sse_errors: list[str] = []

        def estimation_token_stream() -> Iterator[str]:
            """Solo emite texto para ``write_stream``; métricas van a session_state."""
            for event in stream_estimation_events(
                prompt,
                skip_cache=skip_cache,
                model=model_override,
                max_tokens=max_tokens_payload,
                example_format=example_fmt,
                use_examples=use_examples,
            ):
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

        with st.chat_message("assistant"):
            try:
                assistant_reply = st.write_stream(estimation_token_stream()) or ""
                if sse_errors:
                    st.error(sse_errors[0])
            except httpx.HTTPError as exc:
                assistant_reply = (
                    f"No se pudo conectar con la API en `{STREAM_ENDPOINT}`.\n\n"
                    f"Detalle: `{exc}`"
                )
                st.error(assistant_reply)
            except Exception as exc:  # pragma: no cover
                assistant_reply = (
                    "Error al generar la estimación. Revisa claves LLM y logs del servidor.\n\n"
                    f"Detalle: `{exc}`"
                )
                st.warning(assistant_reply)

        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

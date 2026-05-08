"""Interfaz Streamlit tipo chat para el estimador CAG."""

import json
import os
from collections.abc import Iterator
from urllib import error, request

import streamlit as st
from app.context.examples import ESTIMATION_EXAMPLES
from app.services.llm_service import LLMService


st.set_page_config(page_title="Estimador CAG Chat", page_icon="💬", layout="centered")
st.title("Estimador de Software (CAG)")
st.caption("Pega una transcripción de reunión para generar una estimación.")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
STREAM_ENDPOINT = f"{API_BASE_URL}/api/v1/estimate/stream"


def stream_estimation_events(transcription: str) -> Iterator[dict[str, object]]:
    """Consume SSE de estimación y devuelve eventos tipados."""
    payload = json.dumps({"transcription": transcription}).encode("utf-8")
    req = request.Request(
        url=STREAM_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=300) as response:
            current_event = "message"
            data_lines: list[str] = []

            while True:
                raw_line = response.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="ignore").rstrip("\r\n")
                if not line:
                    if data_lines:
                        payload_raw = "\n".join(data_lines)
                        try:
                            payload_obj = json.loads(payload_raw)
                        except json.JSONDecodeError:
                            payload_obj = {"raw": payload_raw}
                        yield {"event": current_event, "data": payload_obj}
                    current_event = "message"
                    data_lines = []
                    continue

                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip() or "message"
                elif line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].strip())
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"Error HTTP {exc.code} al invocar endpoint de streaming. Detalle: {detail}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(
            "No pude conectar con la API de estimación en streaming. "
            f"Revisa API_BASE_URL ({API_BASE_URL})."
        ) from exc


if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_metrics" not in st.session_state:
    st.session_state.last_metrics = None

system_prompt = LLMService.build_system_prompt()
examples_pretty = json.dumps(ESTIMATION_EXAMPLES, ensure_ascii=False, indent=2)

with st.sidebar:
    st.subheader("Visibilidad CAG")
    st.caption("Información usada por el modelo para estimar.")
    st.text_area("System prompt activo (solo lectura)", value=system_prompt, height=220, disabled=True)
    st.text_area(
        "Contexto estático inyectado (ejemplos CAG)",
        value=examples_pretty,
        height=260,
        disabled=True,
    )


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


transcription = st.chat_input("Escribe o pega aquí la transcripción de la reunión...")

if transcription:
    st.session_state.messages.append({"role": "user", "content": transcription})
    with st.chat_message("user"):
        st.markdown(transcription)

    with st.chat_message("assistant"):
        try:
            assistant_placeholder = st.empty()
            response_chunks: list[str] = []
            assistant_reply = ""
            for event in stream_estimation_events(transcription):
                event_type = str(event.get("event", ""))
                event_data = event.get("data", {})
                if not isinstance(event_data, dict):
                    continue
                if event_type == "chunk":
                    chunk_text = str(event_data.get("text", ""))
                    if chunk_text:
                        response_chunks.append(chunk_text)
                        assistant_reply = "".join(response_chunks)
                        assistant_placeholder.markdown(assistant_reply)
                elif event_type == "done":
                    usage = event_data.get("usage", {})
                    if not isinstance(usage, dict):
                        usage = {}
                    st.session_state.last_metrics = {
                        "model": str(event_data.get("model", "desconocido")),
                        "input_tokens": int(usage.get("input_tokens", 0)),
                        "output_tokens": int(usage.get("output_tokens", 0)),
                        "response_seconds": float(event_data.get("response_seconds", 0.0)),
                    }
                elif event_type == "error":
                    raise RuntimeError(str(event_data.get("message", "Error desconocido de streaming.")))

            assistant_reply = assistant_reply or "".join(response_chunks)
            assistant_placeholder.markdown(assistant_reply)
        except Exception as exc:  # pragma: no cover - manejo UI
            assistant_reply = (
                "No pude generar la estimación. Verifica tu configuración "
                "de proveedor/modelo y API key en variables de entorno.\n\n"
                f"Detalle: `{exc}`"
            )
            st.markdown(assistant_reply)

    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

# Las métricas deben pintarse después de actualizar last_metrics en esta misma ejecución;
# si van arriba del todo, el sidebar se dibuja antes del bloque del chat_input y queda obsoleto.
with st.sidebar:
    st.markdown("### Última llamada")
    if st.session_state.last_metrics:
        metrics = st.session_state.last_metrics
        st.metric("Modelo", str(metrics["model"]))
        st.metric("Tokens entrada", int(metrics["input_tokens"]))
        st.metric("Tokens salida", int(metrics["output_tokens"]))
        st.metric("Tiempo respuesta", f"{float(metrics['response_seconds']):.2f} s")
    else:
        st.info("Aún no hay llamadas realizadas en esta sesión.")

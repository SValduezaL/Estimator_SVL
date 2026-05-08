"""Interfaz Streamlit tipo chat para el estimador CAG."""

import streamlit as st

from app.services.llm_service import LLMService


st.set_page_config(page_title="Estimador CAG Chat", page_icon="💬", layout="centered")
st.title("Estimador de Software (CAG)")
st.caption("Pega una transcripcion de reunion para generar una estimacion.")


if "messages" not in st.session_state:
    st.session_state.messages = []


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


transcription = st.chat_input("Escribe o pega aquí la transcripción de la reunión...")

if transcription:
    st.session_state.messages.append({"role": "user", "content": transcription})
    with st.chat_message("user"):
        st.markdown(transcription)

    with st.chat_message("assistant"):
        with st.spinner("Generando estimación..."):
            try:
                service = LLMService()
                result = service.estimate(transcription)
                assistant_reply = result.estimation
            except Exception as exc:  # pragma: no cover - manejo UI
                assistant_reply = (
                    "No pude generar la estimación. Verifica tu configuración "
                    "de proveedor/modelo y API key en variables de entorno.\n\n"
                    f"Detalle: `{exc}`"
                )
        st.markdown(assistant_reply)

    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

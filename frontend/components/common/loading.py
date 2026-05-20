"""Indicadores de carga."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import streamlit as st


@contextmanager
def loading_spinner(message: str) -> Iterator[None]:
    with st.spinner(message):
        yield

"""Launcher Streamlit — delega en ``frontend.app``.

Ejecutar en el host (no dentro del contenedor Docker):

    uv run streamlit run streamlit_app.py

Requiere la API en marcha (default ``http://localhost:8000`` vía ``ESTIMATOR_API_BASE_URL``).
La pestaña Prompt renderiza Jinja2 en proceso (importa ``app.foundation.prompts``).
"""

from frontend.app import run_app

run_app()

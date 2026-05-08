# Imagen de producción multi-etapa para el API FastAPI (Estimador CAG).
# Etapa builder: instala dependencias con uv. Etapa runtime: solo Python + .venv + código.

# -----------------------------------------------------------------------------
# Etapa 1 — Builder
# -----------------------------------------------------------------------------
# Multi-etapa: las herramientas de build (uv, cachés) no van a la imagen final.
FROM python:3.11-slim AS builder

# Binario oficial de uv (rápido y reproducible). En producción conviene fijar
# una etiqueta concreta (p. ej. ghcr.io/astral-sh/uv:0.6.x) en lugar de :latest.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Usar el Python de la imagen base (no descargar otro intérprete).
ENV UV_PYTHON_DOWNLOADS=0
# Copiar en lugar de enlaces duros: el .venv se copia a otra etapa sin rutas rotas.
ENV UV_LINK_MODE=copy
# Bytecode opcional: arranque un poco más rápido a cambio de algo más de tamaño.
ENV UV_COMPILE_BYTECODE=1

# Manifests primero para maximizar caché de capas Docker.
COPY pyproject.toml uv.lock ./

# --frozen: instala exactamente lo del lock; falla si lock y pyproject no coinciden.
# Caché de uv acelera rebuilds locales y en CI (BuildKit).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


# -----------------------------------------------------------------------------
# Etapa 2 — Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Estimador CAG API"
LABEL org.opencontainers.image.description="Servicio FastAPI para estimaciones (arquitectura CAG)"

RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --create-home --home-dir /home/appuser appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app/ /app/app/

RUN chown -R appuser:appgroup /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# Misma sonda que en Compose: sin curl en slim.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Estimador CAG

FastAPI + Streamlit para estimar esfuerzo de desarrollo a partir de transcripciones de reuniones. El backend inyecta contexto estático (ejemplos históricos) en cada prompt al LLM (patrón CAG), con streaming SSE, caché Redis opcional y estimación de coste por tokens.

## Arquitectura

```
app/
├── routers/        # Endpoints HTTP (POST /estimate, POST /estimate/stream)
├── services/       # Lógica de negocio: llm_service, llm_wrapper, llm_cache, llm_pricing, evaluation
├── context/        # Ejemplos canónicos few-shot (CANONICAL_EXAMPLES) y formateadores
├── schemas/        # Modelos Pydantic de entrada/salida
├── fixtures/       # Transcripciones de prueba (short / long)
└── config.py       # Configuración vía Pydantic BaseSettings + .env
streamlit_app.py    # Interfaz de chat con streaming SSE
```

Módulos clave en `app/services/`:

| Módulo | Responsabilidad |
|---|---|
| `llm_service.py` | Construcción de prompt CAG y llamada al proveedor |
| `llm_wrapper.py` | Wrapper LiteLLM con streaming, caché y retry |
| `llm_cache.py` | Caché Redis (`EstimationCache`) y chunking SSE |
| `llm_pricing.py` | Tabla de costes por modelo y estimación `cost_usd` |
| `evaluation.py` | Validación heurística de la estructura Markdown devuelta |

## Requisitos

- Python 3.11+
- `uv` instalado
- API key de OpenAI o Anthropic

## Instalacion

Solo dependencias de runtime (API):

```bash
uv sync
```

Con herramientas de desarrollo y tests (`pytest`, `httpx` para `TestClient`):

```bash
uv sync --dev
```

Configura entorno:

```bash
cp .env.example .env
```

## Variables de entorno

La configuración se carga con `Pydantic BaseSettings` desde `app/config.py` y toma valores de `.env`.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `APP_NAME` | sí | Nombre de la API |
| `APP_ENV` | sí | `dev`, `staging` o `prod` |
| `LOG_LEVEL` | sí | `DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL` |
| `LLM_PROVIDER` | sí | Proveedor activo: `openai` o `anthropic` |
| `LLM_MODELS_BY_PROVIDER` | sí | JSON con lista de modelos permitidos por proveedor |
| `LLM_MODEL` | sí | Modelo activo (debe estar en la lista del proveedor) |
| `OPENAI_API_KEY` | si `LLM_PROVIDER=openai` | Clave de API de OpenAI |
| `ANTHROPIC_API_KEY` | si `LLM_PROVIDER=anthropic` | Clave de API de Anthropic |
| `TEMPERATURE` | no | Entre `0.0` y `1.0` (default `0.2`) |
| `MAX_TOKENS` | no | Entre `100` y `4000` (default `800`) |
| `REDIS_URL` | no | p. ej. `redis://127.0.0.1:6379/0`; vacío = sin caché |
| `CACHE_TTL_SECONDS` | no | TTL de caché en segundos (default `86400`) |
| `LLM_FALLBACK_MODEL` | no | Modelo alternativo para fallback LiteLLM |
| `LLM_TIMEOUT_SECONDS` | no | Timeout de llamada al LLM (default `120`) |
| `LLM_NUM_RETRIES` | no | Reintentos ante error (default `2`) |
| `ESTIMATOR_API_BASE_URL` | no | URL base que usa Streamlit (default `http://localhost:8000`) |

Notas:

- `.env.example` documenta todas las variables sin secretos.
- `.env` contiene los valores reales locales y está ignorado por git.
- Si `LLM_PROVIDER` no existe en `LLM_MODELS_BY_PROVIDER` o `LLM_MODEL` no pertenece a ese proveedor, la app falla al arrancar con error de validación.
- Si faltan API keys según el proveedor elegido, la app falla al arrancar con un error de validación claro.

## Tests (local)

Los tests se ejecutan en tu maquina con el entorno de desarrollo; **`docker-compose-dev.yml` solo levanta la API** (no instala ni lanza `pytest` en contenedor).

```bash
uv sync --dev
pytest
```

Algunos tests importan `app.main` y disparan la validacion de `Settings`: necesitas un `.env` coherente (por ejemplo `OPENAI_API_KEY` si `LLM_PROVIDER=openai`). Los tests del endpoint suelen simular la llamada al proveedor con `monkeypatch`.

## Servicio LLM (CAG)

El servicio en `app/services/llm_service.py` usa el patrón de mensajes:

- `system`: rol del modelo + instrucciones + ejemplos históricos (`CANONICAL_EXAMPLES`, serializable en `markdown`, `json` o `narrative`).
- `user`: transcripción de la reunión a estimar.
- `assistant`: estimación generada por el modelo.

La selección de proveedor se hace con `LLM_PROVIDER` y el modelo con `LLM_MODEL`.

### Caché Redis

Si `REDIS_URL` está configurado, las peticiones idénticas (mismo prompt + modelo + parámetros) se sirven desde Redis sin llamar al LLM. El evento SSE `metrics` incluye `cache_hit: true/false` y el campo `cost_usd` con el coste estimado en dólares. Los precios por modelo se centralizan en `app/services/llm_pricing.py`.

### Interfaz Streamlit

`streamlit_app.py` actúa como cliente HTTP de la API. Conecta al endpoint `/api/v1/estimate/stream` y presenta:

- Texto de la estimación en streaming con `st.write_stream`.
- Panel lateral con 4 pestañas: **Cómo funciona**, **Prompt CAG**, **Servidor** y **Métricas**.
- La pestaña **Métricas** muestra tokens (entrada/salida/total), tiempo de respuesta, hit/miss de caché, `usage_available`, coste estimado y el JSON completo del evento `metrics`.

Para soportar nuevos LLM en el futuro:

1. Agrega el proveedor y su lista de modelos en `LLM_MODELS_BY_PROVIDER`.
2. Añade los precios del modelo en `app/services/llm_pricing.py` (`MODEL_COSTS`).
3. Implementa un nuevo adaptador en `app/services/llm_service.py` que cumpla el contrato `BaseProviderClient`.
4. Registra el adaptador en `PROVIDER_CLIENTS`.

## Ejecutar API

```bash
uv run python -m uvicorn app.main:app --reload
```

## Ejecutar interfaz Streamlit (chat)

Requiere que la API esté corriendo (en otro terminal o Docker). La URL base se configura con `ESTIMATOR_API_BASE_URL`.

```bash
uv run streamlit run streamlit_app.py
```

## Ejecutar con Docker Compose (desarrollo)

El archivo `docker-compose-dev.yml` esta preparado **solo para levantar la API** en desarrollo local: recarga en caliente (`--reload`) y montaje del codigo `./app:/app/app`. Para tests usa `uv sync --dev` y `pytest` en local (ver seccion **Tests**).

Pasos:

1. Copia variables de entorno y completa tus claves:

```bash
cp .env.example .env
```

2. Construye la imagen de desarrollo:

```bash
docker compose -f docker-compose-dev.yml build
```

3. Levanta el servicio:

```bash
docker compose -f docker-compose-dev.yml up
```

4. Abre la API en `http://127.0.0.1:8000`.

Comandos utiles:

```bash
# Ejecutar en segundo plano
docker compose -f docker-compose-dev.yml up -d

# Ver logs
docker compose -f docker-compose-dev.yml logs -f

# Parar y eliminar contenedores
docker compose -f docker-compose-dev.yml down
```

Notas:

- El servicio expone el puerto `8000`.
- El `healthcheck` apunta a `GET /health`.
- Si en Windows/Mac no detecta cambios con `--reload`, habilita `WATCHFILES_FORCE_POLLING=true` en el servicio.

## Ejecutar con Docker Compose (produccion)

El `docker-compose` de produccion aun no esta creado.

Cuando se agregue, la idea sera:

- Ejecutar sin volumen de codigo.
- Ejecutar sin `--reload`.
- Inyectar variables de entorno desde el orquestador/entorno de despliegue.

## Endpoints

### `POST /api/v1/estimate` — respuesta completa (JSON)

```json
{
  "transcription": "Cliente: necesitamos un portal B2B con autenticación, panel admin y reportes...",
  "model": null,
  "max_tokens": 4000,
  "example_format": "markdown",
  "use_examples": true,
  "skip_cache": false,
  "evaluate": false
}
```

Respuesta:

```json
{
  "estimation": "## Portal B2B ...",
  "model": "gpt-4o-mini",
  "provider": "openai",
  "finish_reason": "stop",
  "preprocessing": "none",
  "usage": { "input_tokens": 1240, "output_tokens": 430, "total_tokens": 1670 },
  "cache_hit": false,
  "cost_usd": 0.000446,
  "validation": null
}
```

### `POST /api/v1/estimate/stream` — streaming SSE

Mismo payload que `/estimate` (sin `evaluate`). Emite tres tipos de eventos SSE:

| Evento | Contenido |
|---|---|
| `token` | Fragmento de texto plano (se acumula en el cliente) |
| `metrics` | JSON con modelo, provider, usage, cache_hit, cost_usd, finish_reason, response_seconds |
| `done` | `[DONE]` — señal de fin de stream |
| `error` | Mensaje de error si algo falla en servidor |

Ejemplo `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/estimate" \
  -H "Content-Type: application/json" \
  -d '{"transcription":"En la reunión con el cliente se discutió la necesidad de un plugin eCommerce para descuentos por volumen..."}'
```

### Meta y salud

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Info básica: nombre, versión, links a docs |
| `GET` | `/version` | Versión de la API |
| `GET` | `/health` | Estado de la aplicación |
| `GET` | `/ready` | Readiness check (stub) |
| `GET` | `/docs` | Documentación OpenAPI (Swagger UI) |

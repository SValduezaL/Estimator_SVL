# Estimador CAG

FastAPI + Streamlit para estimar esfuerzo de desarrollo a partir de una **descripción estructurada del proyecto** (tipo, nivel de detalle y formato de salida). El backend inyecta contexto estático CAG mediante **plantillas Jinja2** (`app/prompts/estimation/…`: system, user y ejemplos few-shot por `project_type`), responde **solo en streaming SSE**, con caché Redis opcional, fallback/reintentos/timeouts en LiteLLM y estimación de coste por tokens.

## Arquitectura

```
app/
├── routers/        # POST /api/v1/estimate (solo streaming SSE)
├── services/       # llm_service, llm_wrapper, llm_cache, llm_pricing, evaluation
├── prompts/        # Bundles Jinja2 versionados (CAG): registry, loader, estimation/v1|v2
├── schemas/        # EstimationRequest / enums (app/schemas/estimation.py)
├── fixtures/       # Datos de prueba (p. ej. transcripciones largas)
├── dependencies.py  # FastAPI: EstimationCache (Redis) + LLMWrapper inyectables
└── config.py       # Configuración vía Pydantic BaseSettings + .env
streamlit_app.py    # Formulario + cliente HTTP con streaming SSE
```

Módulos clave en `app/services/`:

| Módulo | Responsabilidad |
|---|---|
| `llm_service.py` | Construcción de prompt CAG (system + user estructurado) |
| `llm_wrapper.py` | Wrapper LiteLLM con streaming, caché y retry |
| `llm_cache.py` | Caché Redis (`EstimationCache`) y chunking SSE |
| `llm_pricing.py` | Tabla de costes por modelo y estimación `cost_usd` |
| `evaluation.py` | Validación heurística de Markdown (uso interno / tests) |

Prompts CAG (`app/prompts/`):

| Recurso | Responsabilidad |
|---|---|
| `registry.py` | Bundles de estimación (`estimation-v1`, `estimation-v2`), bundle por defecto y constante `ESTIMATION_PROMPT_VERSION` (contrato API / métricas). |
| `loader.py` | Renderiza `system.j2` + `user.j2` con variables de la petición y resuelve includes (`examples.j2`, escenarios por `project_type`). |

Estructura típica de un bundle: `estimation/<versión>/system.j2`, `user.j2`, `examples.j2` y `examples/<project_type>/scenario_*.j2`.

## Requisitos

- Python 3.11+
- `uv` instalado
- API key de OpenAI o Anthropic

## Instalación

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
- Si defines `LLM_FALLBACK_MODEL`, la validación exige también la API key del proveedor que corresponda al modelo principal **y** al de fallback (OpenAI y/o Anthropic según aplique).

## Tests (local)

Los tests se ejecutan en tu máquina con el entorno de desarrollo; **`docker-compose-dev.yml` levanta la API y Redis para desarrollo** (no instala ni lanza `pytest` en contenedor).

```bash
uv sync --dev
pytest
```

Algunos tests importan `app.main` y disparan la validación de `Settings`: necesitas un `.env` coherente (por ejemplo `OPENAI_API_KEY` si `LLM_PROVIDER=openai`). Los tests del endpoint suelen simular la llamada al proveedor con `monkeypatch`.

## Servicio LLM (CAG)

El servicio en `app/services/llm_service.py` usa el patrón de mensajes:

- `system`: rol del modelo, instrucciones por tipo/detalle/formato de salida y bloque few-shot renderizado desde Jinja (`app/prompts/estimation/…`; el estilo de los ejemplos sigue el `output_format` de la petición).
- `user`: descripción del proyecto y metadatos (`project_type`, `detail_level`, `output_format`), también desde plantillas.
- `assistant`: estimación generada por el modelo (en el cliente se reconstruye a partir de los eventos `token`).

La selección de proveedor se hace con `LLM_PROVIDER` y el modelo con `LLM_MODEL`.

### Contrato de entrada (`EstimationRequest`)

Definido en `app/schemas/estimation.py` (Pydantic v2):

| Campo | Tipo | Descripción |
|---|---|---|
| `description` | `str` | 20–2000 caracteres |
| `project_type` | enum | `mobile_app`, `web_saas`, `internal_tool`, `data_pipeline` |
| `detail_level` | enum | `summary`, `medium`, `detailed` |
| `output_format` | enum | `phases_table`, `line_items`, `narrative` |

El modelo lógico de salida documentado es `EstimationResponse` (`text`, `prompt_version`); la respuesta HTTP real es **streaming** (ver abajo). El evento SSE `metrics` incluye `prompt_version` junto con uso, coste y caché.

### Caché Redis

Si `REDIS_URL` está configurado, las peticiones idénticas (mismo system + user + modelo + `max_tokens` + `thinking_budget`) se sirven desde Redis sin llamar al LLM. El evento SSE `metrics` incluye `cache_hit: true/false` y `cost_usd`. Los precios por modelo están en `app/services/llm_pricing.py`.

### Interfaz Streamlit

`streamlit_app.py` actúa como cliente HTTP de la API. Envía `POST /api/v1/estimate` con el cuerpo JSON de `EstimationRequest` y **Accept: text/event-stream**:

- Formulario (`st.form`) con descripción y selectores alineados a los enums del backend.
- Texto de la estimación en streaming con `st.write_stream`.
- Panel lateral: **Cómo funciona**, **Prompt CAG**, **Servidor**, **Métricas** (tokens, tiempo, caché, `prompt_version`, coste y JSON de `metrics`).

Para soportar nuevos LLM en el futuro:

1. Agrega el proveedor y su lista de modelos en `LLM_MODELS_BY_PROVIDER`.
2. Añade los precios del modelo en `app/services/llm_pricing.py` (`MODEL_COSTS`).
3. Implementa un nuevo adaptador en `app/services/llm_service.py` que cumpla el contrato `BaseProviderClient`.
4. Registra el adaptador en `PROVIDER_CLIENTS`.

Para evolucionar el CAG (nuevos ejemplos, tono o estructura del system prompt):

1. Crea o ajusta plantillas bajo `app/prompts/estimation/<nueva_subcarpeta>/` y registra un `PromptBundle` en `app/prompts/registry.py`.
2. Apunta el bundle por defecto (`DEFAULT_ESTIMATION_BUNDLE`) al `public_id` que quieras exponer en `prompt_version` / métricas SSE.

## Ejecutar API

```bash
uv run python -m uvicorn app.main:app --reload
```

## Ejecutar interfaz Streamlit

Requiere que la API esté corriendo (en otro terminal o Docker). La URL base se configura con `ESTIMATOR_API_BASE_URL`.

```bash
uv run streamlit run streamlit_app.py
```

## Ejecutar con Docker Compose (desarrollo)

El archivo `docker-compose-dev.yml` está preparado para desarrollo local: **API** con recarga en caliente (`--reload`), montaje del código `./app:/app/app`, y **Redis** para probar caché con la misma `REDIS_URL` que inyecta Compose. Para tests usa `uv sync --dev` y `pytest` en local (ver sección **Tests**).

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

Comandos útiles:

```bash
# Ejecutar en segundo plano
docker compose -f docker-compose-dev.yml up -d

# Ver logs
docker compose -f docker-compose-dev.yml logs -f

# Parar y eliminar contenedores
docker compose -f docker-compose-dev.yml down
```

Notas:

- Compose levanta **`redis`** (puerto host `6379`, con healthcheck) y **`estimator`**: la API arranca con `REDIS_URL=redis://redis:6379/0` definido en el propio compose (caché activa en ese flujo). Para ejecutar la API en el host sin Redis, deja `REDIS_URL` vacío en `.env` y usa `uv run python -m uvicorn …` (ver **Ejecutar API**).
- El servicio expone el puerto `8000`.
- El `healthcheck` apunta a `GET /health`.
- Si en Windows/Mac no detecta cambios con `--reload`, habilita `WATCHFILES_FORCE_POLLING=true` en el servicio.

## Ejecutar con Docker Compose (producción)

El `docker-compose` de producción aún no está creado.

Cuando se agregue, la idea será:

- Ejecutar sin volumen de código.
- Ejecutar sin `--reload`.
- Inyectar variables de entorno desde el orquestador/entorno de despliegue.

## Endpoints

### `POST /api/v1/estimate` — streaming SSE (único flujo)

Cuerpo JSON (`EstimationRequest`):

```json
{
  "description": "Necesitamos un portal B2B con autenticación, panel admin y reportes de uso. Integración con ERP existente vía API documentada.",
  "project_type": "web_saas",
  "detail_level": "medium",
  "output_format": "line_items"
}
```

Respuesta: **`text/event-stream`** (Server-Sent Events). Eventos:

| Evento | Contenido |
|---|---|
| `token` | Fragmento de texto plano (el cliente acumula la estimación) |
| `metrics` | JSON: `model`, `provider`, `usage`, `cache_hit`, `cost_usd`, `finish_reason`, `response_seconds`, `prompt_version`, etc. |
| `done` | `[DONE]` — fin del stream |
| `error` | Mensaje de error si falla el procesamiento |

Ejemplo con `curl` (stream en consola):

```bash
curl -N -X POST "http://127.0.0.1:8000/api/v1/estimate" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d "{\"description\":\"CRM pequeño con auth, contactos y roles. MVP orientativo seis semanas. Texto extra para superar el mínimo de 20 caracteres.\",\"project_type\":\"web_saas\",\"detail_level\":\"medium\",\"output_format\":\"line_items\"}"
```

### Meta y salud

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Info básica: nombre, versión, links a docs |
| `GET` | `/version` | Versión de la API |
| `GET` | `/health` | Estado de la aplicación |
| `GET` | `/ready` | Readiness check (stub) |
| `GET` | `/docs` | Documentación OpenAPI (Swagger UI) |

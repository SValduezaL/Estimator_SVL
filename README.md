# Estimador CAG

FastAPI + Streamlit para estimar esfuerzo de desarrollo a partir de una **descripción estructurada del proyecto** (tipo y nivel de detalle). El backend inyecta contexto CAG con **plantillas Jinja2 v3** y few-shot JSON, aplica **guardrails multicapa** (defense-in-depth), genera un **`EstimationResult` validado** vía **Instructor + LiteLLM**, y responde en JSON con métricas. Caché Redis opcional, fallback/reintentos, observabilidad structlog y coste por tokens.

## Arquitectura

```
app/
├── routers/        # POST /api/v1/estimate (respuesta JSON)
├── services/       # llm_service, llm_wrapper, llm_cache, llm_pricing, structured_llm
├── guardrails/     # Defense-in-depth: input, output, moderation, injection, PII, policies
├── prompts/        # Bundles Jinja2 versionados (CAG): registry, loader, estimation/v3
├── schemas/        # request/output/API (estimation_request, estimation_output, estimation.py)
├── logging/        # structlog: config, middleware X-Request-ID, redacción, handlers
├── fixtures/       # Datos de prueba y few-shot JSON (estimation_examples/)
├── dependencies.py # FastAPI: EstimationCache, LLMWrapper, cliente moderación OpenAI
└── config.py       # Pydantic BaseSettings + .env (LLM + guardrails)
streamlit_app.py    # Formulario + cliente HTTP JSON hacia la API
```

### Pipeline de una estimación

```
POST /api/v1/estimate
  │
  ├─ L1  Pydantic (EstimationRequest: longitud, enums)
  ├─ L2  Input guardrails (moderation → injection → PII)
  ├─ L3  Render Jinja2 v3 + validación de prompts
  ├─ L4  Instructor + LiteLLM → EstimationResult (schema)
  ├─ L5  Output guardrails (validadores semánticos + filtros)
  └─     EstimationResponse (JSON + métricas)
```

Módulos clave en `app/services/`:

| Módulo | Responsabilidad |
|---|---|
| `llm_service.py` | Construcción de prompt CAG (system + user estructurado) |
| `llm_wrapper.py` | Wrapper LiteLLM con caché y retry |
| `llm_cache.py` | Caché Redis (`EstimationCache`) |
| `llm_pricing.py` | Tabla de costes por modelo y estimación `cost_usd` |
| `structured_llm.py` | Validación de ``reasoning`` y utilidades Instructor |

Prompts CAG (`app/prompts/`):

| Recurso | Responsabilidad |
|---|---|
| `registry.py` | Bundles de estimación (`estimation-v3-structured` por defecto), constante `ESTIMATION_PROMPT_VERSION` (contrato API / métricas). |
| `loader.py` | Renderiza `system.j2` + `user.j2` con variables de la petición y resuelve includes (`examples.j2`, escenarios por `project_type`). |

Estructura típica de un bundle: `estimation/<versión>/system.j2`, `user.j2`, `examples.j2` y fixtures JSON en `app/fixtures/estimation_examples/`.

### Guardrails (`app/guardrails/`)

Capa de **defense-in-depth** separada de schemas de dominio y del router. Toda la lógica de moderación, regex e políticas vive aquí (no en endpoints).

| Módulo | Responsabilidad |
|---|---|
| `input.py` | Orquestador de entrada: `run_input_guardrails()` |
| `output.py` | Orquestador de salida: `run_output_guardrails()` |
| `moderation.py` | OpenAI Moderation API (scores, thresholds, fail-open) |
| `injection.py` | Detección de prompt injection (registry versionado) |
| `pii.py` | PII en entrada/salida (email, IBAN, teléfono, tarjetas, API keys) |
| `validators.py` | Coherencia coste/tiempo, fases, confidence, PII leak |
| `filters.py` | `enforce_scope_response`, `build_safe_fallback` (política FILTER) |
| `policies.py` | Aplicación de políticas de fallo |
| `prompts.py` | Validación post-render (tamaño, delimitadores XML) |
| `judge.py` | Hook LLM-as-judge (`NoOpOutputJudge` por defecto; extensible) |
| `telemetry.py` | Eventos structlog + contadores in-memory (Prometheus-ready) |
| `patterns/injection_v1.yaml` | Patrones de inyección versionables |

**Políticas de fallo** (`FailurePolicy`):

| Política | Comportamiento |
|---|---|
| `exception` | Bloquea la petición o falla el pipeline |
| `filter` | Reescribe/redacta y continúa (p. ej. baja confianza, PII en salida) |
| `retry` | Señal reintentable hacia el wrapper LLM |
| `log_only` | Solo telemetría; no bloquea |

**Orden en entrada** (por defecto): moderación → injection → PII.

**Códigos HTTP** relacionados:

| Situación | HTTP | Notas |
|---|---|---|
| Violación input (`InputGuardrailViolation`) | **400** | `reason`: `moderation`, `prompt_injection`, `pii` |
| Validación Pydantic del body | **422** | Sin cambios |
| Output irrecuperable | **502** | Alineado con fallos LLM |
| Output degradado (FILTER) | **200** | Mismo schema `EstimationResult` |

En `dev`, el detalle del 400 puede incluir el mensaje interno; en `staging`/`prod`, mensajes genéricos por `reason`.

**Versión de caché:** las claves Redis incluyen `guardrails.v1` además de `estimation.v1` (`CACHE_SCHEMA_VERSION` en `llm_wrapper.py`), de modo que cambios en guardrails invalidan entradas antiguas.

**Tests:** `tests/guardrails/` (unitarios, integración, regresión de ataques, snapshots). Los tests globales usan `guardrails_enabled=false` en `conftest`; la suite de guardrails activa flags estrictos.

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

### Guardrails

Todas las variables usan prefijo `GUARDRAILS_` (case-insensitive en `.env`). Definidas en `app/config.py`.

| Variable | Default | Descripción |
|---|---|---|
| `GUARDRAILS_ENABLED` | `true` | Interruptor global |
| `GUARDRAILS_MODERATION_ENABLED` | `true` | OpenAI Moderation API (requiere `OPENAI_API_KEY`) |
| `GUARDRAILS_INJECTION_ENABLED` | `true` | Heurísticas prompt injection (`patterns/injection_v1.yaml`) |
| `GUARDRAILS_PII_INPUT_ENABLED` | `true` | PII en descripción de entrada |
| `GUARDRAILS_PII_OUTPUT_ENABLED` | `true` | PII en `summary` / `reasoning` (redacción FILTER) |
| `GUARDRAILS_OUTPUT_SEMANTIC_ENABLED` | `true` | Validadores semánticos post-LLM |
| `GUARDRAILS_MODERATION_LOG_ONLY` | `false` | Solo log si moderación falla (no bloquea) |
| `GUARDRAILS_INJECTION_LOG_ONLY` | `false` | Solo log si detecta injection |
| `GUARDRAILS_PII_INPUT_LOG_ONLY` | `false` | Solo log si detecta PII en entrada |
| `GUARDRAILS_MODERATION_MODEL` | `omni-moderation-latest` | Modelo de moderación OpenAI |
| `GUARDRAILS_MODERATION_THRESHOLDS` | `{}` | JSON `{"categoria": 0.8}` para bloquear por score |
| `GUARDRAILS_INJECTION_PATTERN_VERSION` | `v1` | Versión del YAML de patrones |
| `GUARDRAILS_FAIL_OPEN_ON_MODERATION_ERROR` | `true` | Si la API de moderación cae, continuar (log warning) |
| `GUARDRAILS_OUTPUT_MAX_RETRIES` | `1` | Reintentos LLM ante `OutputGuardrailRetryable` |
| `GUARDRAILS_JUDGE_ENABLED` | `false` | Hook LLM-as-judge (NoOp por defecto) |
| `GUARDRAILS_MIN_EUR_PER_HOUR` | `20` | Banda mínima EUR/h implícita por fase |
| `GUARDRAILS_MAX_EUR_PER_HOUR` | `250` | Banda máxima EUR/h implícita por fase |
| `GUARDRAILS_HOURS_PER_WEEK` | `40` | Referencia para coherencia temporal |
| `GUARDRAILS_PROMPT_MAX_CHARS` | `120000` | Tope de tamaño system+user tras render |

Para **desactivar guardrails en tests locales** sin tocar producción: `GUARDRAILS_ENABLED=false` (el `conftest` de pytest ya lo hace por defecto).

## Logging estructurado

La API usa **structlog** (`app/logging/`) con salida a **stdout** (Docker/Kubernetes, ELK, Loki, Datadog).

| `APP_ENV` | Formato |
|---|---|
| `dev` | Consola coloreada (`ConsoleRenderer`) |
| `staging`, `prod` | JSON una línea por evento (`JSONRenderer`) |

### Configuración y pipeline

| Componente | Archivo | Rol |
|---|---|---|
| Arranque | `logging/config.py` | `configure_logging(settings, version)` en lifespan |
| Middleware | `logging/middleware.py` | `X-Request-ID`, `http_request_started` / `completed` |
| Contexto | `logging/context.py` | `contextvars` + `bind_request_context` |
| Redacción | `logging/processors.py` | Omite `description`, `messages`, `api_key`, etc. |
| Handlers | `logging/exceptions.py` | 422, 400 guardrails, 502, 500 |
| Executor | `logging/sync.py` | `run_sync_with_context` para LLM en thread pool |

### Campos habituales en cada evento

- `request_id`, `http_method`, `http_path` (peticiones HTTP)
- `log_category`: `business` | `technical` | `guardrails`
- `service`, `app_env`, `version` (metadatos de servicio)
- `trace_id`, `span_id` (reservados OTel; `null` hasta integrar SDK)
- Errores: `error_type`, `error_message`, `error_recoverable`, `critical`

### Privacidad en logs

- **No** se registran descripciones ni prompts completos.
- Solo hashes: `description_sha256`, `content_sha256` (prompt renderizado).
- Claves en `_SENSITIVE_KEYS` se sustituyen por `[REDACTED]` (`api_key`, `authorization`, `content`, etc.).

### Eventos de negocio y LLM

| Evento | Categoría | Cuándo |
|---|---|---|
| `estimation_requested` | business | Inicio `POST /estimate` |
| `estimation_completed` | business | Éxito con métricas |
| `estimation_failed` | business | Fallo no recuperable |
| `estimation_validation_failed` | business | `ReasoningLengthError` |
| `estimation_prompt_rendered` | technical | Tras Jinja2 |
| `llm_structured_started` / `completed` / `failed` | technical | Ciclo Instructor |
| `cache_hit` / `cache_miss` / `cache_stored` | technical | Redis |
| `reasoning_truncated` | technical | Recorte suave de `reasoning` |

### Eventos de guardrails (`log_category=guardrails`)

| Evento | Cuándo |
|---|---|
| `guardrail_policy_applied` | Tras cada capa (nombre, política, passed) |
| `guardrail_check_completed` | Fin de capa (debug, `latency_ms`) |
| `moderation_flagged` | Contenido marcado por OpenAI |
| `moderation_scores_recorded` | Scores por categoría |
| `moderation_call_failed` | Error de red/API (fail-open si configurado) |
| `prompt_injection_detected` | Patrón regex coincidente |
| `pii_detected` | Tipos de PII encontrados |
| `input_guardrail_blocked` | HTTP 400 |
| `enforce_scope_response_filtering` | Salida reescrita por baja confianza |
| `output_pii_redacted` | PII redactado en salida |
| `llm_retry_triggered` | Reintento por validador semántico |
| `output_guardrail_retry_exhausted` | Fallback seguro tras agotar reintentos |

Contadores en memoria: `app/guardrails/telemetry.py` → `get_guardrail_metrics()` (exportables a Prometheus más adelante).

### Consultar logs

```bash
docker compose -f docker-compose-dev.yml logs -f estimator
```

En **staging/prod**, filtrar por correlación:

```text
request_id:"<uuid>"
log_category:guardrails
```

Ejemplo de evento JSON (prod):

```json
{
  "event": "guardrail_policy_applied",
  "log_category": "guardrails",
  "guardrail_name": "prompt_injection",
  "policy": "exception",
  "passed": false,
  "request_id": "a1b2c3d4-...",
  "timestamp": "2026-05-19T12:00:00.000000Z"
}
```

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
# Solo guardrails:
pytest tests/guardrails -q
```

Algunos tests importan `app.main` y disparan la validación de `Settings`: necesitas un `.env` coherente (por ejemplo `OPENAI_API_KEY` si `LLM_PROVIDER=openai`). Los tests del endpoint simulan el LLM con `monkeypatch`; `tests/guardrails/` cubre moderación (mock), injection, PII, políticas, integración 400 y regresión de ataques.

## Servicio LLM (CAG + Instructor + guardrails)

- `system` / `user`: plantillas v3 (`estimation-v3-structured`) con bloques `<scope>`, refusal, anti-hallucination y few-shot JSON desde `app/fixtures/estimation_examples/`.
- **Entrada:** `run_input_guardrails()` antes de renderizar; **salida:** `run_output_guardrails()` tras Instructor (también en cache hit).
- Salida: **Instructor** (`instructor.from_litellm`) con `response_model=EstimationResult`; reintentos Pydantic + reintentos por guardrails de salida (`GUARDRAILS_OUTPUT_MAX_RETRIES`).
- Proveedor: `LLM_PROVIDER` + `LLM_MODEL`; fallback opcional vía `LLM_FALLBACK_MODEL`.

### Contrato de entrada (`EstimationRequest`)

Definido en `app/schemas/estimation_request.py`:

| Campo | Tipo | Descripción |
|---|---|---|
| `description` | `str` | 20–2000 caracteres |
| `project_type` | enum | `mobile_app`, `web_saas`, `internal_tool`, `data_pipeline` |
| `detail_level` | enum | `summary`, `medium`, `detailed` (afecta longitud de `reasoning` en el prompt) |

### Contrato de salida (`EstimationResponse`)

| Campo | Tipo | Descripción |
|---|---|---|
| `result` | `EstimationResult` | Fases, totales, `summary`, `reasoning` (Markdown) |
| `schema_version` | `str` | `estimation.v1` |
| `prompt_version` | `str` | Bundle CAG activo (`estimation-v3-structured`) |
| `model`, `provider`, `usage`, `cache_hit`, `cost_usd`, … | | Métricas operativas |

`EstimationResult` (en `app/schemas/estimation_output.py`) incluye validadores de negocio (suma de `cost_eur`, prefijo si baja confianza, etc.).

### Caché Redis

Si `REDIS_URL` está configurado, las peticiones idénticas (mismo system + user + modelo + `max_tokens` + `thinking_budget` + versión de schema/guardrails) se sirven desde Redis sin llamar al LLM. Tras un cache hit se ejecutan igualmente los **output guardrails**. La respuesta incluye `cache_hit: true/false` y `cost_usd`. Los precios por modelo están en `app/services/llm_pricing.py`.

### Interfaz Streamlit

`streamlit_app.py` actúa como cliente HTTP de la API. Envía `POST /api/v1/estimate` con el cuerpo JSON de `EstimationRequest`:

- Formulario (`st.form`) con descripción y selectores alineados a los enums del backend.
- Tabla de fases, métricas y `st.markdown` sobre `result.reasoning`.
- Panel lateral: **Cómo funciona**, **Prompt CAG**, **Servidor**, **Métricas** (tokens, tiempo, caché, `prompt_version`, coste y JSON completo).

Para soportar nuevos LLM en el futuro:

1. Agrega el proveedor y su lista de modelos en `LLM_MODELS_BY_PROVIDER`.
2. Añade los precios del modelo en `app/services/llm_pricing.py` (`MODEL_COSTS`).
3. Configura el modelo en LiteLLM (vía `LLM_MODEL` / `LLM_FALLBACK_MODEL`); el wrapper en `llm_wrapper.py` enruta las llamadas.

Para evolucionar el CAG (nuevos ejemplos, tono o estructura del system prompt):

1. Crea o ajusta plantillas bajo `app/prompts/estimation/<nueva_subcarpeta>/` y registra un `PromptBundle` en `app/prompts/registry.py`.
2. Apunta el bundle por defecto (`DEFAULT_ESTIMATION_BUNDLE`) al `public_id` que quieras exponer en `prompt_version` / métricas de la respuesta.

Para extender guardrails:

1. **Injection:** añade entradas en `app/guardrails/patterns/injection_v1.yaml` (o nuevo `injection_v2.yaml` + `GUARDRAILS_INJECTION_PATTERN_VERSION`).
2. **PII:** nuevas reglas en `app/guardrails/pii.py` → `default_pii_rules()`.
3. **Salida:** validadores en `validators.py`; filtros en `filters.py`.
4. **Judge:** implementa `OutputJudge` y regístralo con `register_output_judge()`; activa `GUARDRAILS_JUDGE_ENABLED=true`.
5. Tras cambios que alteren comportamiento en caché, incrementa `GUARDRAILS_VERSION` en `app/guardrails/config.py`.

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

### `POST /api/v1/estimate` — respuesta JSON

Cuerpo JSON (`EstimationRequest`):

```json
{
  "description": "Necesitamos un portal B2B con autenticación, panel admin y reportes de uso. Integración con ERP existente vía API documentada.",
  "project_type": "web_saas",
  "detail_level": "medium"
}
```

Respuesta: **`application/json`** (`EstimationResponse`) con `result` (`EstimationResult`: fases, totales, `reasoning` en Markdown) y métricas (`prompt_version`, `usage`, `cache_hit`, `cost_usd`, etc.). Ver OpenAPI en `/docs`.

**Errores guardrails (entrada):** HTTP 400 con cuerpo `{"detail": "...", "reason": "moderation"|"prompt_injection"|"pii"}`.

Ejemplo con `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/estimate" \
  -H "Content-Type: application/json" \
  -d "{\"description\":\"CRM pequeño con auth, contactos y roles. MVP orientativo seis semanas. Texto extra para superar el mínimo de 20 caracteres.\",\"project_type\":\"web_saas\",\"detail_level\":\"medium\"}"
```

### Meta y salud

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Info básica: nombre, versión, links a docs |
| `GET` | `/version` | Versión de la API |
| `GET` | `/health` | Estado de la aplicación |
| `GET` | `/ready` | Readiness check (stub) |
| `GET` | `/docs` | Documentación OpenAPI (Swagger UI) |

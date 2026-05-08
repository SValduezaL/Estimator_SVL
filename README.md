# Estimador CAG

Aplicacion base con FastAPI para estimar esfuerzo de desarrollo desde transcripciones de reuniones, inyectando contexto estatico (ejemplos historicos) en cada prompt al LLM.

## Arquitectura

- `app/routers`: endpoints HTTP.
- `app/services`: logica de negocio y llamada al proveedor LLM.
- `app/context`: contexto estatico inyectado al prompt (CAG).
- `app/config.py`: configuracion por variables de entorno.

## Requisitos

- Python 3.11+
- `uv` instalado
- API key de OpenAI o Anthropic

## Instalacion

```bash
uv sync
```

Configura entorno:

```bash
cp .env.example .env
```

## Variables de entorno

La configuracion se carga con `Pydantic BaseSettings` desde `app/config.py` y toma valores de `.env`.

Variables requeridas:

- `APP_NAME`: nombre de la API.
- `APP_ENV`: `dev`, `staging` o `prod`.
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL`.
- `LLM_PROVIDER`: proveedor activo (ejemplo: `openai` o `anthropic`).
- `LLM_MODELS_BY_PROVIDER`: JSON con lista de modelos permitidos por proveedor.
- `LLM_MODEL`: modelo activo (debe existir en la lista del proveedor seleccionado).
- `OPENAI_API_KEY`: obligatoria si `LLM_PROVIDER=openai`.
- `ANTHROPIC_API_KEY`: obligatoria si `LLM_PROVIDER=anthropic`.
- `TEMPERATURE`: entre `0.0` y `1.0`.
- `MAX_TOKENS`: entre `100` y `4000`.

Notas:

- `.env.example` documenta todas las variables con valores de ejemplo (sin secretos).
- `.env` contiene los valores reales locales y esta ignorado por git.
- Si `LLM_PROVIDER` no existe en `LLM_MODELS_BY_PROVIDER` o el `LLM_MODEL` no pertenece a ese proveedor, la app fallara al arrancar con error de validacion.
- Si faltan API keys segun el proveedor elegido, la app fallara al arrancar con un error de validacion claro.

## Servicio LLM (CAG)

El servicio en `app/services/llm_service.py` usa el patron de mensajes:

- `system`: rol del modelo + instrucciones + ejemplos historicos (`ESTIMATION_EXAMPLES`).
- `user`: transcripcion de la reunion a estimar.
- `assistant`: estimacion generada por el modelo.

La seleccion de proveedor se hace con `LLM_PROVIDER` y el modelo con `LLM_MODEL`.

Para soportar nuevos LLM en el futuro:

1. Agrega el proveedor y su lista de modelos en `LLM_MODELS_BY_PROVIDER`.
2. Implementa un nuevo adaptador en `app/services/llm_service.py` que cumpla el contrato `BaseProviderClient`.
3. Registra el adaptador en `PROVIDER_CLIENTS`.

## Ejecutar API

```bash
uv run python -m uvicorn app.main:app --reload
```

## Ejecutar interfaz Streamlit (chat)

La interfaz de chat reutiliza la misma lógica CAG del servicio (`LLMService`), incluido el mismo `system prompt` del endpoint de estimaciones.

```bash
uv run streamlit run streamlit_app.py
```

## Ejecutar con Docker Compose (desarrollo)

El archivo `docker-compose-dev.yml` esta preparado para desarrollo local con recarga en caliente (`--reload`) y montaje del codigo `./app:/app/app`.

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

## Endpoint principal

### `POST /api/v1/estimate`

Request:

```json
{
  "transcription": "Cliente: necesitamos un portal B2B con autenticacion, panel admin y reportes..."
}
```

Response:

```json
{
  "estimation": "1) Resumen del requerimiento ...",
  "model": "gpt-4o-mini",
  "provider": "openai",
  "tokens": {
    "input_tokens": 1240,
    "output_tokens": 430,
    "total_tokens": 1670
  },
  "timestamp": "2026-04-28T18:00:00.000000+00:00"
}
```

Ejemplo `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/estimate" \
  -H "Content-Type: application/json" \
  -d "{\"transcription\":\"En la reunion con el cliente se discutio la necesidad de un plugin eCommerce para descuentos por volumen...\"}"
```

## Healthcheck

### `GET /health`

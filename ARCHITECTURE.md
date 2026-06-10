# Arquitectura del estimador

Contrato de arquitectura del servicio. El código nuevo debe respetar estas capas.

## 1. Las tres arquitecturas de IA

- **CAG** (`app/generation/cag/`): caché exacta + semántica antes del LLM.
- **RAG** (`app/generation/rag/`): chunking, embeddings y (S8+) persistencia/recuperación.
- **Agéntica** (`app/generation/agentic/`): bucle Actor-Crítico-Boss sobre conversación.
- **Conversación** (`app/generation/conversation/`): sesiones, metadata, compresión.

Las capas componen **solo** a través del conductor `app/domain/estimation_service.py`.

## 2. Estructura de capas

```
app/
├── main.py
├── config.py
├── dependencies.py          # composition root
├── foundation/              # plomería sin opinión de arquitectura AI
│   ├── llm/                 # wrapper, structured, pricing, runtime_config
│   ├── prompts/
│   ├── guardrails/          # defense-in-depth (extensión del curso)
│   ├── attachments/
│   ├── observability/       # structlog, middleware, excepciones
│   └── persistence/         # slot S8 (SQLAlchemy + pgvector)
├── domain/
│   ├── schemas/
│   └── estimation_service.py
├── generation/
│   ├── cag/
│   ├── rag/
│   ├── agentic/
│   └── conversation/
├── ingestion/               # pipeline batch offline (S6/S8)
└── api/                     # routers finos
```

## 3. Reglas de dependencias

| Capa | PUEDE importar | NO PUEDE importar |
|---|---|---|
| `foundation/*` | `config` | `domain`, `generation`, `ingestion`, `api` |
| `domain/schemas/*` | `config`, `foundation` | `generation`, `api` |
| `generation/*` | `config`, `foundation`, `domain/schemas` | `api`, **otro hermano de generation** |
| `domain/estimation_service.py` | todos los hermanos de `generation` + `foundation` | `api` |
| `api/*` | `dependencies`, `domain` | lógica de negocio |
| `dependencies.py` | cualquier capa | — |

**Regla crítica**: hermanos de `generation/` no se importan entre sí; se componen en `EstimationService`.

## 4. Contratos HTTP públicos

- `POST /api/v1/estimate`
- `POST /api/v1/sessions`, `GET /api/v1/sessions/{id}`, `POST /api/v1/sessions/{id}/estimate`
- `POST /embeddings/ingest`, `POST /embeddings/compare`, `POST /search`
- `GET/PUT /api/v1/config/models`

## 5. ¿Dónde va mi código nuevo?

| Si añades… | Va en… |
|---|---|
| LLM, prompt, guardrail | `foundation/` |
| Caché | `generation/cag/` |
| Memoria conversacional | `generation/conversation/` |
| Chunking, embeddings, retrieval | `generation/rag/` |
| Agente (Boss/Critic) | `generation/agentic/` |
| Endpoint HTTP | `api/` + factory en `dependencies.py` |
| Composición entre capas | método en `EstimationService` |
| Ingestión offline | `ingestion/` |

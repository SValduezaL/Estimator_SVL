# Scripts de operación

Utilidades CLI para cargar el corpus, comparar estrategias de chunking (S7) y ejecutar los benchmarks de índices vectoriales de la Sesión 08 (S8).

**Cómo ejecutarlos**

| Contexto | Comando recomendado |
|---|---|
| Scripts **HTTP** (`ingest_corpus.py`, `query_examples.py`) con Compose levantado | `docker compose exec estimator python scripts/…` |
| Scripts **HTTP** desde el host (API en `:8000`) | `uv run python scripts/…` |
| Scripts **solo BBDD** (`measure_baseline_s08.py`, `*_s08.py`, SQL) | `docker compose exec estimator python scripts/…` o `docker compose run --rm estimator python scripts/…` |
| Migraciones | `docker compose run --rm estimator alembic upgrade head` |

> **Importante — `exec` vs `run` para scripts HTTP**
>
> `docker compose run --rm estimator` arranca un contenedor **nuevo** y aislado. Dentro de él, `localhost:8000` apunta a ese contenedor, no al servicio `estimator` del stack → `ingest_corpus.py` / `query_examples.py` fallan con `Connection refused`.
>
> Usa `docker compose exec estimator …` (contenedor ya en marcha, misma red) o `uv run` en el host. Alternativa con `run`: `docker compose run --rm -e ESTIMATOR_API_BASE_URL=http://estimator:8000 estimator python scripts/ingest_corpus.py`.

**Prerrequisitos habituales**

```bash
docker compose up -d
docker compose run --rm estimator alembic upgrade head
# OPENAI_API_KEY en .env (scripts que embeden o insertan sintéticos)
```

| Variable | Uso |
|---|---|
| `OPENAI_API_KEY` | Embeddings (benchmarks S08, `compare.py`, `compare_chunkers.py`, sintéticos) |
| `ESTIMATOR_API_BASE_URL` | Scripts HTTP; default `http://localhost:8000` (válido en host o dentro del contenedor `estimator` en marcha) |

---

## Corpus e ingesta

### `ingest_corpus.py`

Ingesta todos los presupuestos de `data/budgets_sample.json` vía `POST /embeddings/ingest`. Un documento por budget; si ya existe (409), lo omite.

```bash
uv run python scripts/ingest_corpus.py
# Con el stack levantado (recomendado):
docker compose exec estimator python scripts/ingest_corpus.py
```

### `query_examples.py`

Smoke test end-to-end: ingesta idempotente del corpus + cinco búsquedas semánticas contra `POST /search`. El tiempo reportado (`search_time_ms`) **incluye** el round-trip de embedding a OpenAI.

Las cinco queries están en la constante `QUERIES` — es la **fuente única de verdad** que importan los benchmarks S08 (`s08_common.py`).

```bash
docker compose exec estimator python scripts/query_examples.py
# o desde el host:
uv run python scripts/query_examples.py
```

---

## Chunking y embeddings (S7)

### `compare.py`

Sanity check de embeddings: coseno entre dos textos arbitrarios con `text-embedding-3-small`. No toca la base de datos.

```bash
uv run python scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend for fintech" \
  --text-b "JWT-based authorization service for banking app"
```

### `compare_chunkers.py`

Compara las 8 estrategias de chunking **en memoria** sobre `data/budgets_sample.json` y las consultas de `data/test_queries.json`. Estadísticos de corpus, top-k por estrategia y reporte Markdown opcional.

```bash
uv run python scripts/compare_chunkers.py --strategies all --queries all --show-stats
uv run python scripts/compare_chunkers.py --strategies recursive,sentence_window --show-top-k 3
uv run python scripts/compare_chunkers.py --strategies all --queries all --show-stats --output COMPARISON_REPORT.md
```

Estrategias disponibles: `structural`, `fixed_size`, `recursive`, `sentence_window`, `semantic`, `propositional`, `contextual_retrieval`, `hierarchical`.

---

## Benchmarks Sesión 08 (Python)

Los scripts `*_s08.py` comparten helpers en `s08_common.py` (embedder, tablas, cronómetro, queries). Miden **solo la parte SQL** salvo que se indique lo contrario: los embeddings se calculan una vez al inicio.

### `s08_common.py`

Módulo importable (no ejecutable). Centraliza `QUERIES`, `require_embedder()`, `embed_benchmark_queries()`, `format_table()`, `Stopwatch` y `vector_literal()`.

### `measure_baseline_s08.py`

**Bloques 2.1 / 2.2** — Latencia de `search_chunks_by_cosine` (mismo SELECT que `/search`, sin HTTP ni embedding en el cronómetro). 1 warm-up + 2 mediciones por query.

Al final imprime el literal pgvector de la primera query para pegarlo en `sql_S08/02_test_antipatron.sql`.

```bash
docker compose exec estimator python scripts/measure_baseline_s08.py
```

Ejecutar **antes** y **después** de `sql_S08/01_create_hnsw.sql` para comparar latencias.

> Si tras crear el índice la mejora es modesta, no asumas un fallo del script: con ~30k filas el planner puede seguir eligiendo sequential scan para `embedding <=> …` (ver [Notas de diseño](#notas-de-diseño)).

### `insert_synthetic_chunks_s08.py`

Inserta chunks con embeddings reales bajo `document_type = 'synthetic_test'` y `chunk_type = 'synthetic'`. Sirve para:

- **Bloque 5.2**: simular crecimiento del corpus (`100` chunks, default).
- **Pre-flight**: corpus grande (`30000`) para que el sequential scan sin índice sea perceptible en el directo.

```bash
docker compose run --rm estimator python scripts/insert_synthetic_chunks_s08.py
docker compose run --rm estimator python scripts/insert_synthetic_chunks_s08.py 30000
```

Limpieza rápida: `DELETE FROM documents WHERE document_type = 'synthetic_test';`

### `sweep_ef_search_s08.py`

**Bloque 3.1** — Barrido de `hnsw.ef_search` en `[10, 20, 40, 80, 120, 200]`. Ground truth con sequential scan forzado; recall@5 vs latencia; marca el valor recomendado (★).

Requiere el índice HNSW creado (`sql_S08/01_create_hnsw.sql`).

```bash
docker compose run --rm estimator python scripts/sweep_ef_search_s08.py
```

### `compare_indexes_s08.py`

**Bloque 4.2** — Compara top-5, solapamiento y latencia entre `chunks_embedding_idx` (vector) y `chunks_embedding_halfvec_idx` (halfvec). Verifica con `EXPLAIN` qué índice usa cada plan; emite `WARNING` si el routing no es el esperado.

En la práctica suele verse: la ruta **vector** (`embedding <=> …`, como `/search`) resuelta con sequential scan, y la ruta **halfvec** (expresión casteada) con `Index Scan` en pocos ms — overlap **5/5** en recall.

Requiere ambos índices (`01_create_hnsw.sql` + `03_create_halfvec.sql`).

```bash
docker compose exec estimator python scripts/compare_indexes_s08.py
```

### `report_index_sizes_s08.py`

**Bloques 2.2, 4.1, 5.1** — Tabla de índices sobre `chunks`: tipo, tamaño, `idx_scan`, último uso. Solo lectura; ejecutar antes y después de cada decisión de índice.

```bash
docker compose run --rm estimator python scripts/report_index_sizes_s08.py
```

---

## SQL Sesión 08 (`sql_S08/`)

Scripts psql para el directo. El contenedor `postgres` **no monta** estos ficheros; redirigir desde el host o pegar en psql interactivo.

```bash
docker compose exec -T postgres psql -U estimator -d estimator < scripts/sql_S08/01_create_hnsw.sql
docker compose exec postgres psql -U estimator -d estimator   # modo interactivo
```

| Archivo | Bloque | Descripción |
|---|---|---|
| `01_create_hnsw.sql` | 2.2 | Crea `chunks_embedding_idx` con `vector_cosine_ops` (`m=16`, `ef_construction=128`) |
| `02_test_antipatron.sql` | 2.3 | Demuestra desalineación silenciosa `<=>` vs `<->` con `EXPLAIN ANALYZE`. Con ~30k filas ambos casos pueden mostrar `Seq Scan`; el contraste de latencia y `idx_scan` sigue siendo instructivo |
| `03_create_halfvec.sql` | 4.1 | Crea índice HNSW sobre `(embedding::halfvec(1536))` |
| `04_monitoring_queries.sql` | 5.1 | Queries de monitorización (`idx_scan`, filas muertas, operator class) |
| `05_maintenance_cycle.sql` | 5.2 | `ANALYZE`, `VACUUM ANALYZE`, `REINDEX INDEX CONCURRENTLY` |
| `99_revert_live_session.sql` | — | Revierte el ensayo: drop índices HNSW, borra sintéticos extra, reset `ef_search` y estadísticas |

### Orden sugerido (ensayo completo)

1. `alembic upgrade head` + `ingest_corpus.py` (o `query_examples.py`, que también ingesta).
2. *(Opcional)* `insert_synthetic_chunks_s08.py 30000` si el corpus real es pequeño.
3. `measure_baseline_s08.py` → baseline sin índice.
4. `sql_S08/01_create_hnsw.sql` → `measure_baseline_s08.py` de nuevo.
5. `sql_S08/02_test_antipatron.sql` → antipatrón operador/clase.
6. `sweep_ef_search_s08.py` → tuning `ef_search`.
7. `sql_S08/03_create_halfvec.sql` → `compare_indexes_s08.py` + `report_index_sizes_s08.py`.
8. `insert_synthetic_chunks_s08.py` (100) → `sql_S08/05_maintenance_cycle.sql`.
9. `sql_S08/04_monitoring_queries.sql` en cualquier momento para diagnóstico.
10. Al terminar: `sql_S08/99_revert_live_session.sql`.

---

## Notas de diseño

- **HTTP vs SQL**: `query_examples.py` mide latencia end-to-end (embedding + SQL). Los `*_s08.py` aíslan la parte que el índice puede mejorar.
- **`exec` vs `run` (scripts HTTP)**: `docker compose run` crea un contenedor donde `localhost:8000` no es el API del stack. Para `ingest_corpus.py` y `query_examples.py` usa `docker compose exec estimator` o `uv run` en el host.
- **Índice creado ≠ índice usado**: tener `chunks_embedding_idx` no obliga al planner a usarlo. Con ~30k filas y `ORDER BY embedding <=> $q LIMIT k`, Postgres puede preferir **sequential scan + top-N heapsort** frente al HNSW. El índice **halfvec** sí tiende a activarse cuando la query ordena por `(embedding::halfvec(1536)) <=> …`, la misma expresión del índice.
- **Cómo verificarlo**: `EXPLAIN ANALYZE` en psql (`02_test_antipatron.sql`), `report_index_sizes_s08.py` (`idx_scan` y `last_used`) y el aviso de plan en `compare_indexes_s08.py`. Si `idx_scan = 0` tras muchas búsquedas semánticas, revisa operador/clase o si el planner está ignorando el índice por coste estimado.
- **Operador alineado**: la app usa `cosine_distance` (`<=>`) en `app/generation/rag/retrieval.py`, coherente con `vector_cosine_ops`. Un `<->` (L2) no usará un índice de coseno aunque exista.
- **Sin índice por defecto**: Alembic crea solo índices relacionales; los HNSW se añaden manualmente en el ensayo y se revierten con `99_revert_live_session.sql`.
- **Servicio Postgres**: en este repo el servicio Compose se llama `postgres` (no `estimator-postgres`).

### Estado tras `99_revert_live_session.sql`

Baseline esperado del repo (verificado tras el ensayo de prueba):

| Elemento | Valor esperado |
|---|---|
| Chunks totales | ~65 (`budget_component`) |
| Documentos `historical_budget` | 15 |
| Documentos `synthetic_test` | 0 |
| Índices en `chunks` | Solo relacionales: `chunks_pkey`, `ix_chunks_*` — **ningún HNSW** |

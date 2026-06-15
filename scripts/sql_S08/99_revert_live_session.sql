-- ============================================================
-- Sesión 08 · Reversión post-ensayo (test run → estado pre-sesión)
-- ============================================================
--
-- Devuelve la BBDD al estado baseline de este repo: corpus ingerido con
-- scripts/ingest_corpus.py (document_type historical_budget), SIN ningún
-- índice vectorial y sin overrides persistentes. NO re-embebe nada.
--
-- Qué revierte (todo lo que el ensayo de la Sesión 08 deja tras de sí):
--   · los índices HNSW creados en B2.2 / B3.2 / B4.1 (vector y halfvec),
--   · chunks sintéticos extra insertados durante el ensayo (chunk_type='synthetic'),
--   · el override global de ef_search si se fijó con ALTER DATABASE (B3.1),
--   · los contadores de pg_stat (idx_scan, last_analyze) para un "antes" limpio.
--
-- Qué NO toca:
--   · los chunks del corpus real (historical_budget / structural),
--   · ningún archivo del repo ni migración Alembic.
--
-- Cómo ejecutarlo (desde la raíz del repo, AL TERMINAR el test run):
--
-- docker compose exec -T postgres psql -U estimator -d estimator \
--   < scripts/sql_S08/99_revert_live_session.sql
--
-- Cuántos sintéticos conservar: por defecto 0 (este repo no precarga sintéticos).
-- Si insertaste sintéticos en el ensayo y quieres conservar los N más antiguos:
--   docker compose exec -T postgres psql -U estimator -d estimator \
--     -v keep_synthetic=100 < scripts/sql_S08/99_revert_live_session.sql
--
-- Idempotente y fail-safe: si no hay índices, no borra nada; si hay <= keep_synthetic
-- sintéticos, no borra ningún chunk. Puede ejecutarse varias veces sin daño.

\if :{?keep_synthetic}
\else
  \set keep_synthetic 0
\endif

\echo '== Estado ANTES de revertir =='
SELECT
    (SELECT count(*) FROM chunks) AS total_chunks,
    (SELECT count(*) FROM chunks WHERE chunk_type = 'synthetic') AS synthetic_chunks;
SELECT indexrelname FROM pg_stat_user_indexes WHERE relname = 'chunks' ORDER BY indexrelname;

-- 1. Borrar chunks sintéticos extra, conservando los :keep_synthetic más antiguos.
-- Con keep_synthetic=0 (default): elimina todos. Con N>0: conserva los N de id más bajo.
DELETE FROM chunks
WHERE chunk_type = 'synthetic'
  AND id NOT IN (
      SELECT id
      FROM chunks
      WHERE chunk_type = 'synthetic'
      ORDER BY id
      LIMIT GREATEST(:keep_synthetic, 0)
  );

-- 2. Dropear todos los índices vectoriales del ensayo (idempotente).
-- Cubre también un índice dejado INVALID por un CONCURRENTLY abortado (B3.2).
DROP INDEX IF EXISTS chunks_embedding_idx;
DROP INDEX IF EXISTS chunks_embedding_halfvec_idx;

-- 3. Revertir el override global de ef_search si se fijó con ALTER DATABASE (B3.1).
-- El SET / SET LOCAL de sesión NO persiste; esto sí. Inofensivo si no se fijó.
ALTER DATABASE estimator RESET hnsw.ef_search;

-- 4. Resetear estadísticas para un "antes" prístino: idx_scan vuelve a 0, de modo
-- que la demo del antipatrón en vivo (idx_scan=0 → índice ignorado, B2.3/B5.1)
-- arranca limpia. ANALYZE repuebla a continuación las estadísticas del planner.
SELECT pg_stat_reset();
ANALYZE chunks;

\echo '== Estado DESPUÉS de revertir (baseline S8: sin índices HNSW) =='
SELECT
    (SELECT count(*) FROM chunks) AS total_chunks,
    (SELECT count(*) FROM chunks WHERE chunk_type = 'synthetic') AS synthetic_chunks,
    (SELECT count(*) FROM documents WHERE document_type = 'historical_budget') AS historical_docs;
-- Esperado: solo índices relacionales (chunks_pkey, ix_chunks_*); NINGÚN hnsw.
SELECT indexrelname FROM pg_stat_user_indexes WHERE relname = 'chunks' ORDER BY indexrelname;

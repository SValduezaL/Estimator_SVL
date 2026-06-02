# Sanity check — similitud coseno (`text-embedding-3-small`)

Medición con `OpenAIEmbedder` + `cosine_similarity` (mismo pipeline que `ai_service/scripts/compare.py`).
Fecha de medición: 2026-06-02. Los valores pueden variar ligeramente entre ejecuciones.

| Pareja | Texto A | Texto B | Similitud | Criterio orientativo |
|--------|---------|---------|-----------|----------------------|
| **A** (cercanos) | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app | Authorization service using JSON Web Tokens for a banking application | **0.5957** | > 0.6 (cercano) |
| **B** (lejanos) | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app | Database migration from MySQL to PostgreSQL with zero downtime | **0.1920** | < 0.4 (lejano) |
| **C** (genéricos) | Backend services | API development | **0.5407** | ambiguo |

## Comentario

La pareja **A** queda justo por debajo del umbral orientativo 0.6, pero describe el mismo dominio (auth/JWT en contexto financiero) y queda muy por encima de **B** (0.19). La pareja **B** separa claramente autenticación frente a migración de base de datos, por debajo de 0.4. La pareja **C** muestra similitud moderada (~0.54): textos cortos y genéricos comparten el espacio semántico de “desarrollo backend” sin ser sinónimos estrictos.

**Conclusión:** A > C > B; el modelo discrimina lo cercano de lo lejano en estos ejemplos. El pipeline end-to-end (embedder + coseno) es coherente para seguir con ingest y retrieval en sesiones posteriores. No sustituye métricas formales de retrieval (recall@k, NDCG).

## Reproducir

```bash
uv run python ai_service/scripts/compare.py \
  --text-a "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app" \
  --text-b "Authorization service using JSON Web Tokens for a banking application"
```

(Repetir con los textos de B y C.)

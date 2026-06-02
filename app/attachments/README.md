# Adjuntos (PDF / DOCX)

## Camino elegido

**Extracción local de texto en el servidor** (`app/attachments/extractor.py`), sin enviar ficheros al modelo de estimación.

| Formato | Librería principal | Fallback |
|---------|-------------------|----------|
| PDF     | `pypdf`           | `PyMuPDF` (`fitz`) si `pypdf` no devuelve texto útil |
| DOCX    | `python-docx`     | — |

### Por qué este enfoque

1. **Alineado con `session_05_live`**: el patrón del curso es leer el archivo en backend, convertirlo a texto plano y meterlo en el contexto del turno (no subir el binario al LLM).
2. **Menor coste y latencia**: una sola llamada estructurada de estimación; el adjunto no consume tokens de visión ni de archivo.
3. **Control y límites**: tamaño máximo por fichero, número máximo de adjuntos y truncado por caracteres (`Settings`: `attachments_*`).
4. **PDFs difíciles**: `pypdf` es ligero y suficiente en la mayoría de casos; `PyMuPDF` actúa como respaldo cuando la extracción principal falla o queda vacía.

### Flujo en la API

1. El cliente llama a `POST /api/v1/sessions/{session_id}/estimate` con `multipart/form-data` (`description`, `project_type`, `detail_level`, `files` opcionales).
2. Por cada fichero: `extract_text()` → texto plano truncado.
3. `enrich_transcript()` concatena la transcripción del usuario y bloques delimitados:

   ```
   --- attachment: nombre.pdf ---
   <texto extraído>
   --- end attachment ---
   ```

4. Esa descripción enriquecida entra al pipeline de estimación (`run_estimation_pipeline`) como si fuera el mensaje del usuario.

Los archivos **no** se persisten como blobs en sesión; solo el texto extraído forma parte del turno y del historial.

---

## `project_metadata` (relacionado pero distinto)

La extracción de adjuntos **no** rellena `project_metadata` directamente.

`project_metadata` se actualiza **después de cada estimación con sesión**, en `app/memory/extractor.py`:

1. Tras generar la estimación, `persist_estimation_turn()` guarda el turno (user + assistant) en el historial.
2. Se invoca `update_metadata_llm()` con:
   - metadata actual de la sesión (JSON),
   - el turno de usuario (incluye texto de adjuntos si hubo),
   - la respuesta del asistente (JSON de la estimación).
3. Llamada LLM independiente (modelo económico por defecto: `gpt-4o-mini`) vía OpenAI Responses API con salida JSON estricta al schema `ProjectMetadata`.
4. El resultado validado con Pydantic sustituye `session.project_metadata` (merge conservador: no inventar, respetar retractaciones, listas sin duplicados).

Ese metadata estructurado se inyecta en el **system prompt** de turnos siguientes (`<project_metadata>` en `app/prompts/estimation/v3/system.j2`), junto con anclas y resumen acumulativo si están activos.

**Resumen**: adjuntos → texto en el mensaje del usuario; metadata → extractor LLM sobre el turno completo ya procesado.

# Chunking del proyecto: presupuestos JSON y transcripciones

Creada: 29 de mayo de 2026 16:39
Módulo: M3. Data Driven AI (https://www.notion.so/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S7. Embeddings y representación vectorial (https://www.notion.so/S7-Embeddings-y-representaci-n-vectorial-36fea9ca03c48018b87adcffb3272fa0?pvs=21)

En el artículo 3 quedó claro un principio que algunos tutoriales tratan como detalle y los benchmarks recientes confirman como decisivo: **el mejor chunking depende del tipo de documento**. Tratar todo el corpus con la misma estrategia es una decisión que en proyectos heterogéneos deja calidad sobre la mesa.

El proyecto del programa es precisamente heterogéneo. Tenemos dos tipos de datos con propiedades estructurales radicalmente distintas:

- **Presupuestos históricos en JSON**: estructura jerárquica explícita, esquema predecible, cada componente del presupuesto es una unidad lógica de negocio. Cuando un cliente futuro envíe un brief, queremos recuperar componentes históricos similares para ayudar a estimar.
- **Transcripciones de reuniones de toma de requisitos**: texto plano de 45 minutos transcrito, sin estructura más allá de marcas opcionales de hablante, con temas que se alternan, se vuelven a tocar, y se interrumpen. Cuando alguien busque qué se discutió sobre autenticación en la reunión del 3 de marzo, queremos recuperar el segmento exacto.

Este artículo aterriza el catálogo del artículo 3 a estos dos tipos de documento concretos. Para los presupuestos diseñamos un chunker estructural específico que respete la jerarquía JSON. Para las transcripciones diseñamos un segmentador por temas. Y conectamos ambos al pipeline del servicio IA. Es el primer aterrizaje real, y es exactamente el primer paso del ejercicio pre-sesión.

## **Dos tipos de documento, dos chunkers**

Antes de meternos en el diseño de cada uno, vale la pena fijar la arquitectura. El servicio IA va a tener **dos chunkers especializados** que comparten una interfaz común, no un chunker genérico que intenta tratar ambos casos. La razón es la misma que aplicarías a cualquier sistema con tipos de input distintos: si dos entradas requieren tratamiento radicalmente distinto, es más limpio dos implementaciones explícitas que una con condicionales internos.

En código Python (esqueleto, sin implementación):

python

```
from abc import ABC, abstractmethod

class Chunker(ABC):
    """Common interface for any chunking strategy in the pipeline."""

    @abstractmethod
    def chunk(self, document: dict | str) -> list[Chunk]:
        """Split a document into a list of Chunk objects."""

class JSONStructuralChunker(Chunker):
    """Chunks budget JSON documents by business unit (component)."""

    def chunk(self, document: dict) -> list[Chunk]:
        ...

class TopicSegmentationChunker(Chunker):
    """Chunks long meeting transcripts by topic shifts."""

    def chunk(self, document: str) -> list[Chunk]:
        ...
```

La interfaz común sirve para dos cosas: hacer testeable cada chunker por separado y dejar la puerta abierta a meter más estrategias dentro del mismo pipeline durante la sesión en vivo (que es exactamente lo que pasará en los bloques hands-on). El ejercicio pre-sesión te pide implementar `JSONStructuralChunker`; el `TopicSegmentationChunker` y otros se introducen en el directo sobre esta misma base.

Una nota sobre dónde vive esto en la arquitectura: ambos chunkers son responsabilidad del **servicio IA** (Python + FastAPI). El **backend de negocio** (Rails en la implementación de referencia, o el stack que elija el alumno) simplemente invoca el endpoint de ingesta enviando los documentos como JSON. Quién decide qué chunker aplicar a qué documento es decisión interna del servicio IA, no contrato con el backend de negocio.

## **Presupuestos JSON: por qué los splitters genéricos fallan**

Si tomas el `RecursiveCharacterTextSplitter` del artículo 3 y le pasas un presupuesto JSON entero, pasan tres cosas todas malas.

**Primera**: el splitter trata las llaves, comillas y comas del JSON como caracteres normales. Va a cortar en mitad de una clave, dejando `"client_metadata": {"sector":` en un chunk y `"finance", "country":` en el siguiente. El chunk resultante no es ni JSON válido ni prosa legible. El embedding que sale es ruido.

**Segunda**: aunque el corte caiga en un sitio sintácticamente afortunado, la jerarquía padre-hijo se pierde. Un chunk que contenga el componente `"OAuth 2.0 authentication backend"` sin la información del presupuesto padre (qué cliente, qué sector, qué año) es semánticamente pobre. Cuando llegue una consulta como *"autenticación para fintech"*, ese chunk competirá con cientos de otros componentes de autenticación de sectores irrelevantes.

**Tercera**: si serializas el JSON a texto plano antes de chunkear (un patrón común y tentador), el modelo de embeddings ve algo como `OAuth 2.0 authentication backend Implementation of OAuth 2.0 flows...` y trata cada componente como prosa equivalente. Pierdes la jerarquía explícita que el formato JSON capturaba.

La estrategia correcta es la que el artículo 3 catalogó como "estructural": **respeta la unidad lógica del documento**. Para presupuestos, esa unidad es el componente. Un componente del presupuesto es una pieza autocontenida que tiene sentido por sí misma: tiene su nombre, su descripción, su stack, sus horas estimadas, su complejidad. Cada componente es un chunk natural.

## **El chunker JSON estructural**

El diseño del `JSONStructuralChunker` parte de tres decisiones explícitas que conviene tener claras antes de teclear código.

**Decisión 1 — Granularidad: un componente = un chunk.** No partimos el presupuesto entero en uno solo (perderíamos especificidad), ni partimos cada campo individual en un chunk (perderíamos coherencia). El componente es la granularidad correcta porque coincide con la unidad de razonamiento del dominio: cuando un cliente pide un OAuth backend, eso es lo que queremos recuperar, no "el presupuesto completo donde una vez se mencionó OAuth".

**Decisión 2 — Contenido del chunk: texto legible enriquecido con contexto del padre.** El campo `text` del chunk (lo que se va a embedear) no es el JSON crudo del componente. Es una representación textual legible que combina los detalles del componente con el contexto relevante del presupuesto padre. Algo así:

```
[Project: Mobile banking API with OAuth 2.0 authentication and PSD2 compliance]
[Client sector: finance | Year: 2024 | Main tech: ruby_on_rails]

Component: OAuth 2.0 authentication backend
Description: Implementation of OAuth 2.0 flows with JWT-based session management,
multi-tenant token isolation, and rate limiting per client.
Tech stack: ruby_on_rails, postgresql, redis
Complexity: high
Estimated hours: 120
```

Las dos primeras líneas entre corchetes son lo que el artículo 3 llamó "contextual chunk headers": información del documento padre prepended al chunk. Microsoft Azure documentó que esta técnica simple sube la accuracy de QA entre 15 y 25 puntos sin tocar nada más del pipeline. Es la palanca de mayor ROI conocida en RAG. La aprovechamos aquí.

Una variante interesante de esta decisión es la conexión con Contextual Retrieval del artículo 3. Lo que estamos haciendo es **la versión estática y barata** de la técnica de Anthropic: usamos información del padre que ya tenemos en el JSON, sin llamar a un LLM. En la sesión en vivo introduciremos la versión completa con LLM contextualizer y mediremos si la diferencia compensa el coste.

**Decisión 3 — Metadata: campos filtrables que no se embeden.** Hay dos tipos de información sobre un componente: la semántica (que queremos que el embedding capture para búsqueda) y la estructural (que queremos como filtros y como información de retorno). El sector del cliente, el año, la tecnología principal, la complejidad y las horas estimadas van en metadata. Esto sirve para dos cosas: filtrar resultados (`sector = 'finance' AND year >= 2023`) y devolver información estructurada al cliente sin tener que parsear el texto del chunk.

![sesion-07-articulo-04-figura-01-json-a-chunks.jpg](https://media1-production-mightynetworks.imgix.net/asset/687bf8cd-7839-495f-82cd-495492c6187c/sesion-07-articulo-04-figura-01-json-a-chunks.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El esqueleto de la clase queda así:

python

```
from dataclasses import dataclass
from typing import Any

import tiktoken

@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]
    token_count: int

class JSONStructuralChunker:
    """Chunks a budget JSON document at the component level.

    Each budget component becomes one chunk. The chunk text combines
    the component's own fields with contextual headers from the parent
    budget (client sector, year, main technology, project summary).
    """

    def __init__(self, model_for_token_count: str = "text-embedding-3-small"):
        self._tokenizer = tiktoken.encoding_for_model(model_for_token_count)

    def chunk(self, budgets: list[dict]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for budget in budgets:
            chunks.extend(self._chunk_one_budget(budget))
        return chunks

    def _chunk_one_budget(self, budget: dict) -> list[Chunk]:
        parent_context = self._build_parent_context(budget)
        return [
            self._build_chunk(component, budget, parent_context)
            for component in budget["components"]
        ]

    def _build_parent_context(self, budget: dict) -> str:
        client = budget["client_metadata"]
        return (
            f"[Project: {budget['project_summary']}]\\n"
            f"[Client sector: {client['sector']} | "
            f"Year: {budget['year']} | "
            f"Main tech: {budget['main_technology']}]"
        )

    def _build_chunk(
        self, component: dict, budget: dict, parent_context: str
    ) -> Chunk:
        text = self._render_component_text(component, parent_context)
        return Chunk(
            chunk_id=f"{budget['budget_id']}::{component['component_id']}",
            text=text,
            metadata=self._build_metadata(component, budget),
            token_count=len(self._tokenizer.encode(text)),
        )

    def _render_component_text(
        self, component: dict, parent_context: str
    ) -> str:
        return (
            f"{parent_context}\\n\\n"
            f"Component: {component['name']}\\n"
            f"Description: {component['description']}\\n"
            f"Tech stack: {', '.join(component['tech_stack'])}\\n"
            f"Complexity: {component['complexity']}\\n"
            f"Estimated hours: {component['estimated_hours']}"
        )

    def _build_metadata(self, component: dict, budget: dict) -> dict[str, Any]:
        return {
            "budget_id": budget["budget_id"],
            "component_id": component["component_id"],
            "client_sector": budget["client_metadata"]["sector"],
            "main_technology": budget["main_technology"],
            "year": budget["year"],
            "complexity": component["complexity"],
            "estimated_hours": component["estimated_hours"],
        }
```

Lo que falta para que sea production-ready y queda como tu trabajo en el ejercicio: validación con Pydantic del schema de entrada (un JSON con un campo faltante no debería tirar `KeyError` opaco), logging estructurado de cuántos chunks produce cada presupuesto, manejo del caso límite "componente con descripción anormalmente larga" (¿se parte o se acepta?), e integración con el endpoint `POST /embeddings/ingest`. Son decisiones que vas a tomar tú; el esqueleto es el chasis.

## **Transcripciones: por qué los splitters de carácter destrozan el contenido**

Cambiemos de tipo de documento. Una transcripción de una reunión de toma de requisitos típica tiene estas propiedades:

- Entre 6.000 y 12.000 tokens. Demasiado para embedear de una sola pieza.
- Cero estructura formal: no hay headers, no hay secciones, no hay marcadores de tema.
- Hablantes alternados, marcados como `Speaker A:`, `Speaker B:` o similares.
- Temas que se alternan, se interrumpen, vuelven más tarde. Una discusión sobre autenticación puede saltar a hosting y volver a autenticación 10 minutos después.
- Mucho contenido conversacional de baja densidad informativa: confirmaciones, repeticiones, divagaciones.

Si aplicas `RecursiveCharacterTextSplitter` con 512 tokens y overlap del 15%, el resultado es funcional pero pobre. Los cortes caen en posiciones arbitrarias, a veces en mitad de una intervención de un hablante. Dos chunks consecutivos pueden contener mitad de una idea cada uno, y la otra mitad del primero queda colgada. Cuando alguien busca *"qué requisitos discutimos sobre autenticación"*, el retriever puede devolverte tres chunks distintos donde ninguno tiene la discusión completa.

La estrategia correcta para transcripciones es la que el artículo 3 catalogó como semántica: **topic-based segmentation**. Embeda oraciones consecutivas (o intervenciones consecutivas), detecta dónde la similitud entre embeddings vecinos cae por debajo de un umbral, y parte ahí. El resultado son chunks que coinciden con bloques temáticos coherentes, no con cortes arbitrarios.

## **Topic-based segmentation para transcripciones**

El diseño del `TopicSegmentationChunker` parte de tres decisiones, paralelas a las del chunker JSON pero con razonamiento diferente.

**Decisión 1 — Granularidad: cada bloque temático = un chunk.** No segmentamos por oración (chunks demasiado pequeños) ni por minuto de duración (no respeta el contenido). Segmentamos donde el tema cambia. La duración resultante varía: a veces un tema dura 30 segundos, a veces 8 minutos. La granularidad se ajusta al contenido, no al reloj.

**Decisión 2 — Contenido del chunk: el bloque temático con su contexto de reunión.** Igual que en presupuestos, prependemos información del documento padre. En este caso, metadata de la reunión: cliente, fecha, participantes principales, fase del proyecto. La estructura del chunk queda:

```
[Meeting: Requirements gathering · 2024-03-15]
[Client: FintechCorp · Phase: discovery]
[Speakers: Antonio (consultant), Maria (CTO), Pedro (lead dev)]

Topic block: Authentication and security
Maria: We need OAuth 2.0 with refresh tokens, and we need it to work with our existing
SAML provider for enterprise clients.
Antonio: Can we assume the SAML side is already configured?
Maria: Yes, the SAML metadata exchange is done. We just need to integrate.
Pedro: For the mobile flows we want PKCE, and we'd like the access tokens to be short-lived,
maybe 15 minutes max.
```

**Decisión 3 — Metadata: información temporal y de hablante.** Para transcripciones la metadata útil es la posición en la reunión (early/mid/late discussion, opcionalmente timestamp si la transcripción lo tiene), el hablante dominante del bloque, y el tema detectado. Los filtros típicos serán por fecha de reunión, por cliente, por fase.

![sesion-07-articulo-04-figura-02-segmentacion-transcripcion.jpg](https://media1-production-mightynetworks.imgix.net/asset/68c418f6-0c33-4351-9eff-292acb5fcf10/sesion-07-articulo-04-figura-02-segmentacion-transcripcion.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El esqueleto del segmentador:

python

```
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer

@dataclass
class Utterance:
    speaker: str
    text: str
    position: int  # ordinal index in the transcript

class TopicSegmentationChunker:
    """Segments meeting transcripts by detecting topic shifts.

    Uses sentence-level embeddings and a similarity threshold to find
    boundaries where consecutive utterances diverge semantically.
    """

    def __init__(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        similarity_threshold: float = 0.55,
    ):
        self._model = SentenceTransformer(embedding_model_name)
        self._threshold = similarity_threshold

    def chunk(self, transcript: dict) -> list[Chunk]:
        utterances = self._parse_utterances(transcript["raw_text"])
        boundaries = self._detect_topic_boundaries(utterances)
        return self._build_chunks_from_boundaries(
            utterances, boundaries, transcript["meta"]
        )

    def _parse_utterances(self, raw_text: str) -> list[Utterance]:
        """Split raw transcript into Utterance objects by speaker turn."""
        ...  # implementation depends on the transcript format

    def _detect_topic_boundaries(
        self, utterances: list[Utterance]
    ) -> list[int]:
        """Return indices where a new topic block begins."""
        embeddings = self._model.encode(
            [u.text for u in utterances],
            normalize_embeddings=True,
        )

        boundaries = [0]  # first block always starts at 0
        for i in range(1, len(embeddings)):
            similarity = float(embeddings[i] @ embeddings[i - 1])
            if similarity < self._threshold:
                boundaries.append(i)
        return boundaries

    def _build_chunks_from_boundaries(
        self,
        utterances: list[Utterance],
        boundaries: list[int],
        meeting_meta: dict,
    ) -> list[Chunk]:
        """Group utterances between consecutive boundaries into chunks."""
        ...
```

Sobre los parámetros: `similarity_threshold=0.55` es un punto de partida, no un valor universal. Demasiado alto y produces demasiados bloques (cualquier variación se interpreta como cambio de tema); demasiado bajo y produces bloques enormes (solo se detectan cambios drásticos). El valor exacto depende del modelo de embedding y del estilo de la transcripción. En la sesión en vivo lo calibraremos sobre las transcripciones reales del proyecto.

Una observación sobre la elección del modelo de embedding aquí: para la segmentación interna usamos `all-MiniLM-L6-v2` aunque el resto del sistema use `text-embedding-3-small`. La razón es que la segmentación necesita embedear muchas oraciones individuales rápido y barato; un modelo local de 384 dimensiones es perfecto para esto, mientras que llamar a la API por cada oración sería innecesariamente caro y lento. Los embeddings para el índice de búsqueda final siguen siendo `text-embedding-3-small`. Diferentes piezas del pipeline pueden usar diferentes modelos de forma legítima.

## **Metadata enrichment: la palanca subestimada**

Vuelvo al hallazgo de Microsoft Azure que mencioné varias veces: **enriquecer cada chunk con metadata estructural sube la accuracy de QA entre 15 y 25 puntos**, sin cambiar nada más del pipeline. Es de los hallazgos con mejor relación esfuerzo/impacto de toda la literatura reciente de RAG.

En nuestro proyecto, ambos chunkers ya están haciendo este enrichment de tres formas:

**Primero**: prependiendo headers contextuales al texto del chunk (el bloque entre corchetes que ves al principio del chunk JSON y al principio del chunk de transcripción). Estos headers van **dentro** del texto que se embedará, así que el vector incorpora esa información en la geometría semántica.

**Segundo**: guardando metadata estructurada **fuera** del texto, en el diccionario `metadata` del `Chunk`. Esta metadata no se embedará pero viajará con el chunk a la base de datos vectorial. En la Sesión 08 veremos que pgvector permite filtrar por esta metadata combinando búsqueda vectorial con filtros SQL clásicos. Una consulta como *"componentes de auth para fintech del último año"* se resuelve haciendo búsqueda vectorial por la parte semántica + filtro SQL por `client_sector = 'finance' AND year >= 2024`.

**Tercero**: usando IDs trazables (`{budget_id}::{component_id}` o `{meeting_id}::{block_index}`). Esto no es metadata enriquecedora del retrieval, pero es operacionalmente crítico: permite saber de qué documento original viene cada chunk, lo que necesitarás para citar fuentes al usuario, auditar resultados, o invalidar chunks específicos cuando se actualice el documento padre.

Una decisión que conviene hacer explícita: **qué información va en el texto del chunk y qué información va en el metadata**. La regla práctica es esta. Si la información cambia el significado semántico del chunk para una consulta natural ("autenticación para fintech" → el sector importa para distinguir esa búsqueda de "autenticación para e-commerce"), va en el texto. Si la información es discreta y se usará para filtrar resultados (`year`, `complexity`, `estimated_hours`), va en metadata.

A veces va en ambos sitios. El sector del cliente, por ejemplo, podemos meterlo tanto en el header del texto (para que pese semánticamente) como en metadata (para filtrar). No es redundancia injustificada: cada copia cumple un rol diferente.

## **Composición en el servicio IA**

Una vez tienes los dos chunkers, queda la cuestión de cómo el servicio IA decide cuál aplicar a un documento entrante. Para esta sesión la respuesta es simple porque tenemos solo dos tipos: el `POST /embeddings/ingest` puede recibir un campo `document_type` en el body y enrutar internamente:

![sesion-07-articulo-04-figura-03-arquitectura-servicio-ia.jpg](https://media1-production-mightynetworks.imgix.net/asset/f435ba7d-4f2c-4ec6-9d54-6e5671b9785e/sesion-07-articulo-04-figura-03-arquitectura-servicio-ia.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

python

```
class IngestRouter:
    """Routes documents to the appropriate chunker based on type."""

    def __init__(
        self,
        json_chunker: JSONStructuralChunker,
        transcript_chunker: TopicSegmentationChunker,
    ):
        self._chunkers = {
            "budget": json_chunker,
            "transcript": transcript_chunker,
        }

    def chunk(self, document: dict, document_type: str) -> list[Chunk]:
        if document_type not in self._chunkers:
            raise ValueError(f"Unknown document type: {document_type}")
        return self._chunkers[document_type].chunk(document)
```

Una decisión arquitectónica que vale la pena mencionar aunque no se aborda hasta sesiones posteriores: el servicio IA podría detectar el tipo de documento automáticamente (mirar si es JSON estructurado o texto plano, leer un campo `kind` del payload, inspeccionar la URL del fichero). Para este momento del programa la decisión "explícita por payload" es más simple y más auditable, así que vamos con ella. La detección automática es agentic chunking del artículo 3, una opción legítima pero con coste extra que aquí no se justifica.

El backend de negocio, cuando llame al endpoint de ingesta, envía el documento con su tipo:

ruby

```
# Client-side example in Ruby/Rails. Any HTTP client works the same way.
class AIServiceClient
  def ingest_budget(budget_payload)
    HTTP.post(
      "#{ai_service_url}/embeddings/ingest",
      json: {
        document_type: "budget",
        budget: budget_payload,
      },
    )
  end

  def ingest_transcript(transcript_payload)
    HTTP.post(
      "#{ai_service_url}/embeddings/ingest",
      json: {
        document_type: "transcript",
        transcript: transcript_payload,
      },
    )
  end
end
```

Que el backend de negocio sea Rails es accidental a la arquitectura. Cualquier cliente HTTP cumple la misma función: el contrato entre las dos capas es REST simple, independiente del stack.
# Estrategias profesionales de chunking

Creada: 29 de mayo de 2026 16:38
Módulo: M3. Data Driven AI (https://www.notion.so/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S7. Embeddings y representación vectorial (https://www.notion.so/S7-Embeddings-y-representaci-n-vectorial-36fea9ca03c48018b87adcffb3272fa0?pvs=21)

La pregunta que aún nos falta es la que más impacto tiene en la calidad final de tu sistema RAG: **¿cómo partimos los documentos antes de generar los embeddings?**

No es una pregunta retórica ni cosmética. Si pasas un presupuesto entero al embedding, el vector resultante es un promedio difuso que mezcla autenticación con módulo de inventario y con sección de hosting, y no servirá para recuperar nada concreto. Si lo partes en trozos demasiado pequeños, pierdes el contexto que hace que cada trozo tenga sentido. Si lo partes por carácter, rompes palabras y oraciones en mitad de la idea. Si lo partes por separador, asumes que el separador siempre significa lo mismo (y casi nunca lo hace). Si lo partes por significado, ¿cómo calculas el significado antes de tener embeddings?

Hay docenas de estrategias publicadas, varias librerías que las implementan, y un número creciente de papers académicos midiendo cuál funciona mejor sobre qué tipo de corpus. Este artículo es el mapa del territorio. Cubro doce estrategias agrupadas en cuatro familias mentales, con criterios para elegir cada una y observaciones honestas sobre cuándo no funcionan. No hay análisis comparativo experimental aquí: eso es exactamente el grueso de la sesión en vivo, donde mediremos sobre tus propios datos cuál gana. La meta de este artículo es que llegues al directo con el mapa, no con la solución.

## **Por qué el chunking domina la calidad**

Antes de meternos en el catálogo, conviene calibrar cuánto importa esta decisión. Es una pregunta que la mayoría de tutoriales esquivan o responden con vaguedades.

Tres datos recientes para fijar el orden de magnitud:

- Un estudio de Vectara presentado en NAACL 2025 evaluó 25 configuraciones distintas de chunking sobre 48 modelos de embeddings en tareas estándar de retrieval. Su hallazgo más citable: la varianza inducida por cambiar la estrategia de chunking puede ser tan grande como la varianza inducida por cambiar de modelo. En otras palabras, pasar de chunking ingenuo a chunking bien tuneado puede aportarte tanto como pasar de un modelo mediocre a uno excelente.
- La investigación de Chroma (2025) midió cinco estrategias sobre un benchmark interno. Los `LLMSemanticChunker` y `ClusterSemanticChunker` alcanzaron recall de 0.919 y 0.913 respectivamente. El `RecursiveCharacterTextSplitter` de LangChain bien tuneado (400 tokens) llegó a 0.88-0.89. La diferencia entre el mejor y el peor del estudio fue de 9 puntos porcentuales de recall.
- Un benchmark de Vecta de febrero de 2026 sobre 50 papers académicos colocó al recursive splitter de 512 tokens en primer lugar con 69% de accuracy. El semantic chunking, supuestamente más sofisticado, quedó en cuarto lugar con 54%. La sofisticación no garantiza mejor rendimiento; lo garantiza la coincidencia entre la estrategia y el tipo de corpus.

La conclusión operativa que vas a oír repetida varias veces en este artículo: **mide sobre tus datos antes de comprometer arquitectura**. Los benchmarks generalistas son indicativos, no oraculares. Lo que gana en papers académicos no necesariamente gana en presupuestos de software técnico ni en transcripciones de toma de requisitos.

## **Cuatro familias mentales**

Antes de enumerar doce estrategias, vale la pena organizar el espacio mentalmente. El catálogo se cae en cuatro grupos según cómo deciden dónde partir el texto.

**Familia 1: mecánicas.** Parten el texto sin entender lo que dice. Aplican reglas sobre la forma del texto (tamaño, separadores, oraciones). Son las más simples, las más rápidas, y sorprendentemente competitivas en muchos benchmarks.

**Familia 2: estructurales.** Explotan el formato del documento (HTML, Markdown, JSON, secciones de un PDF). La estructura ya codifica intención del autor, así que partir respetándola conserva contexto sin necesidad de análisis semántico.

**Familia 3: semánticas.** Calculan dónde cambia el significado del texto (usando embeddings o un LLM) y parten ahí. Más costosas, en teoría mejores en documentos donde no hay estructura clara. En la práctica no siempre justifican el coste extra.

**Familia 4: avanzadas y contextuales.** No son alternativas a las anteriores, son complementos: técnicas que mejoran el resultado de cualquier estrategia base enriqueciendo el chunk con contexto adicional antes de embedearlo. Son las más recientes (la mayoría son de 2024-2025) y donde está actualmente la frontera del estado del arte.

Veamos cada familia.

![sesion-07-articulo-03-figura-01-cuatro-familias.jpg](https://media1-production-mightynetworks.imgix.net/asset/776b157d-77dd-4ff4-80aa-12502a37d3f3/sesion-07-articulo-03-figura-01-cuatro-familias.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Familia 1 — Mecánicas**

### **Fixed-size**

La estrategia más básica: parte el texto en bloques de N tokens o N caracteres, con un parámetro opcional de solapamiento (overlap) entre bloques consecutivos. No mira el contenido, no respeta oraciones, no entiende párrafos.

python

```
def fixed_size_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into fixed-size character chunks with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
```

**Cuándo funciona**: corpus muy homogéneo donde la estructura interna del texto no importa (logs, streams de eventos, transcripciones planas sin formato). Útil como baseline contra el que comparar estrategias más sofisticadas.

**Cuándo no funciona**: cualquier corpus con estructura interna (código, documentos formales, conversaciones). Romper a mitad de palabra o de oración degrada la calidad de los embeddings de forma medible.

El solapamiento típico está entre el 10% y el 20% del tamaño del chunk. Sirve para que una idea que cae justo en una frontera no se pierda: aparece (parcialmente) en los dos chunks contiguos.

### **Recursive character text splitter**

La estrategia que más se usa en producción real, y según los benchmarks recientes la que mejor balance ofrece. La idea: en lugar de partir por carácter, defines una jerarquía de separadores ordenados por preferencia (por defecto, `["\\n\\n", "\\n", " ", ""]`) e intentas partir por el separador más fuerte que produzca chunks dentro del tamaño objetivo.

python

```
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=80,
    separators=["\\n\\n", "\\n", ". ", " ", ""],
)

chunks = splitter.split_text(document_text)
```

El algoritmo intenta primero partir por párrafos (`\\n\\n`). Si los párrafos siguen siendo demasiado grandes, baja a líneas (`\\n`). Si las líneas siguen siendo demasiado grandes, baja a oraciones (`.` ), y así hasta caracteres como último recurso.

**Cuándo funciona**: prácticamente cualquier texto en prosa natural. Es el default razonable, el que vas a probar primero en casi cualquier proyecto.

**Cuándo no funciona**: documentos con estructura jerárquica formal (JSON, código, formularios) donde los separadores genéricos no capturan la jerarquía real. Para esos casos hay estrategias estructurales específicas.

Configuración que rinde bien según múltiples benchmarks: chunk de 400-512 tokens, overlap del 10-20%. Antes de inventar nada, prueba este default contra tu corpus. Es sorprendentemente difícil de batir.

### **Sentence-window retrieval**

Una variante con una idea elegante: indexa **oraciones individuales** (chunks muy pequeños) pero al recuperar, devuelve una **ventana ampliada** alrededor de cada oración recuperada. Los embeddings comparan unidades pequeñas y precisas; el LLM recibe contexto suficiente para responder.

python

```
# Conceptual sketch
def chunk_to_sentences_with_window(text: str, window: int) -> list[dict]:
    """Index sentences; remember their neighbors for retrieval-time expansion."""
    sentences = split_into_sentences(text)
    chunks = []
    for i, sentence in enumerate(sentences):
        chunks.append({
            "embedding_text": sentence,  # what we embed and index
            "retrieval_text": " ".join(
                sentences[max(0, i - window):i + window + 1]
            ),  # what we return when this sentence matches
            "metadata": {"sentence_idx": i},
        })
    return chunks
```

**Cuándo funciona**: documentos donde la información concreta está en oraciones específicas pero la respuesta necesita contexto vecinal para tener sentido (manuales técnicos, papers, contratos). El retriever encuentra el "punto exacto" y el generador recibe el "alrededor relevante".

**Cuándo no funciona**: documentos donde la información está naturalmente distribuida en bloques (resúmenes ejecutivos, secciones temáticas largas). Aquí indexar oraciones individuales fragmenta más de lo que ayuda.

Esta estrategia es uno de los patrones más antiguos que sigue siendo competitivo en 2026. Se implementa con LlamaIndex (`SentenceWindowNodeParser`) o a mano con relativa facilidad.

### **Sliding window con overlap variable**

Variante de fixed-size donde el "paso" entre chunks no es chunk_size - overlap fijo, sino un parámetro independiente. Te permite controlar densidad: pasos pequeños producen muchos chunks redundantes (buena cobertura, índice más grande), pasos grandes producen pocos chunks dispersos (índice más pequeño, riesgo de perder cosas en las costuras).

Útil cuando trabajas con texto continuo sin separadores naturales (transcripciones brutas sin diarización, secuencias de eventos temporales). En la práctica, sentence-window suele ser mejor opción para casos donde sliding window parece atractivo.

![sesion-07-articulo-03-figura-02-tres-estrategias-mismo-texto.jpg](https://media1-production-mightynetworks.imgix.net/asset/b665d94b-3b9d-4982-9bb9-5a225588d185/sesion-07-articulo-03-figura-02-tres-estrategias-mismo-texto.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Familia 2 — Estructurales**

### **Document-based: Markdown, HTML, JSON**

La estructura del documento original ya codifica las decisiones del autor sobre dónde una idea empieza y otra termina. Si el documento tiene headers en Markdown, las decisiones de chunking deben respetar headers. Si tiene tags en HTML, deben respetar tags. Si es JSON, deben respetar la jerarquía de claves.

python

```
from langchain_text_splitters import MarkdownHeaderTextSplitter

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ],
    return_each_line=False,
)

chunks = markdown_splitter.split_text(markdown_document)
# Each chunk knows under which h1, h2, h3 it lives — that's the "context"
```

Para HTML existe `HTMLHeaderTextSplitter` con la misma idea aplicada a tags `<h1>` a `<h6>`. Para JSON, no hay un splitter genérico que funcione bien porque la "estructura significativa" depende del dominio: en un presupuesto un componente es una unidad lógica, en una API spec un endpoint es una unidad lógica, en un dataset un registro es una unidad lógica. El chunker JSON suele ser custom — exactamente lo que vamos a hacer en el artículo 4 para presupuestos.

**Cuándo funciona**: documentos con estructura explícita y fiable. Investigación de Microsoft Azure Architecture Center (2025) mostró que añadir el header de cada chunk como metadata enriquecido (sin cambiar nada más) puede subir la accuracy de QA entre 15 y 25 puntos. La estructura es una mina de oro de contexto si la respetas.

**Cuándo no funciona**: documentos sin estructura (transcripciones planas, texto OCR de baja calidad, contenido de redes sociales).

### **Hierarchical / parent-child chunking**

La idea: indexa chunks pequeños para que el retrieval sea preciso, pero asocia cada chunk pequeño a su chunk "padre" (más grande), de modo que al recuperar puedas pasar al LLM el chunk pequeño que coincidió **y también** el contexto del padre. El resultado es un índice multi-nivel.

Conceptualmente:

```
Documento
├── Sección 1 (chunk grande)
│   ├── Párrafo 1.1 (chunk pequeño)
│   ├── Párrafo 1.2 (chunk pequeño)
│   └── Párrafo 1.3 (chunk pequeño)
└── Sección 2 (chunk grande)
    ├── Párrafo 2.1 (chunk pequeño)
    └── Párrafo 2.2 (chunk pequeño)
```

Indexas los párrafos. Cuando uno coincide, retornas (opcionalmente) la sección completa junto con el párrafo. LangChain implementa esta idea con `ParentDocumentRetriever`; LlamaIndex con `HierarchicalNodeParser`.

**Cuándo funciona**: documentos largos donde una pregunta concreta tiene su respuesta en un fragmento puntual pero la pregunta solo se entiende con contexto más amplio. Manuales, libros técnicos, documentos legales.

**Cuándo no funciona**: corpus de chunks ya pequeños y autocontenidos (FAQs, tickets de soporte breves). Aquí la jerarquía añade complejidad sin ganancia.

Importante: parent-child es una **arquitectura de retrieval**, no solo una estrategia de chunking. Implica decisiones sobre qué se indexa (los hijos) y qué se devuelve (los padres o ambos). Es una decisión arquitectónica mayor.

## **Familia 3 — Semánticas**

### **Semantic chunking**

En lugar de cortar por tamaño o por separador, calcula embeddings de oraciones consecutivas y corta donde la similitud cae por debajo de un umbral. La intuición: donde el significado cambia, conviene cortar.

python

```
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai.embeddings import OpenAIEmbeddings

semantic_splitter = SemanticChunker(
    embeddings=OpenAIEmbeddings(model="text-embedding-3-small"),
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=95,
)

chunks = semantic_splitter.split_text(document_text)
```

El parámetro `breakpoint_threshold_type` controla cómo se decide dónde cortar: por percentil (cortar donde la diferencia de similitud está en el top X%), por desviación estándar, o por umbral absoluto.

**Cuándo funciona**: documentos multi-tema sin estructura explícita: papers de investigación con secciones implícitas, posts de blog largos, ensayos.

**Cuándo no funciona**: documentos cortos y enfocados (FAQs, single-topic articles). Tampoco funciona bien sobre texto donde las oraciones consecutivas tienen alta similitud por diseño (jerga repetitiva, plantillas legales).

El **coste real** que muchos tutoriales esconden: el semantic chunking requiere embedear cada oración del documento durante la ingesta, lo que multiplica el coste y latencia respecto a recursive. Para 10.000 documentos con 100 oraciones cada uno son un millón de llamadas adicionales a la API de embeddings. Y los benchmarks recientes (incluido el NAACL 2025) muestran que las ganancias respecto a recursive bien tuneado son a menudo marginales.

### **Cluster semantic chunking**

Variante interesante: en lugar de cortar secuencialmente, agrupa oraciones similares aunque no sean consecutivas. La motivación: en algunos documentos las ideas vuelven a aparecer en diferentes momentos, y agruparlas en un mismo chunk mejora la recuperación de esa idea.

python

```
# Conceptual sketch; production implementations use HDBSCAN or similar.
def cluster_chunks(sentences: list[str], embedder, n_clusters: int):
    embeddings = [embedder(s) for s in sentences]
    cluster_assignments = cluster_algorithm(embeddings, n_clusters)
    chunks = [
        " ".join(s for s, c in zip(sentences, cluster_assignments) if c == k)
        for k in range(n_clusters)
    ]
    return chunks
```

**Cuándo funciona**: discursos largos donde un mismo tema reaparece, transcripciones de mesa redonda con varios speakers volviendo a sus puntos, libros con motivos recurrentes.

**Cuándo no funciona**: la mayoría de los corpus técnicos donde las ideas están organizadas linealmente. También rompe la trazabilidad: un chunk clusterizado no tiene "lugar" en el documento original, lo que complica citar la fuente al usuario.

### **LLM-based / propositional chunking**

La estrategia más cara y, en algunos benchmarks, la que mejores resultados ofrece. La idea: dale el documento a un LLM y pídele que extraiga proposiciones autocontenidas — afirmaciones que tienen sentido aisladas, sin depender de contexto del documento.

python

```
PROPOSITION_PROMPT = """
Decompose the following text into the smallest set of self-contained propositions.
Each proposition should:
- Express a single atomic fact or claim
- Be understandable without reading the surrounding text
- Resolve all pronouns and references to explicit entities

Output as a JSON list of strings.

Text: {text}
"""

def llm_based_chunks(text: str, client) -> list[str]:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": PROPOSITION_PROMPT.format(text=text)}],
        response_format={"type": "json_object"},
    )
    return parse_json(response.choices[0].message.content)["propositions"]
```

**Cuándo funciona**: corpus de alto valor donde la calidad de retrieval justifica el coste extra de llamar a un LLM por cada documento durante la ingesta. Documentación crítica, base de conocimiento de soporte, contenido legal.

**Cuándo no funciona**: corpus grandes donde el coste de ingesta se vuelve prohibitivo. Para un millón de documentos, hablamos de cientos o miles de dólares solo en la fase de chunking. Hay que evaluar el ROI explícitamente.

En los benchmarks de Chroma (2025), `LLMSemanticChunker` alcanzó 0.919 de recall, el máximo del estudio. Es el caso prototípico de "más caro pero efectivo cuando puedes permitírtelo".

## **Familia 4 — Avanzadas y contextuales**

Esta familia es distinta de las anteriores. No son alternativas a recursive o semantic; son **complementos** que mejoran el resultado de cualquier estrategia base.

### **Late chunking**

Concepto reciente popularizado por Jina AI a finales de 2024. La idea cambia el orden de operaciones tradicional. En chunking convencional: parte primero el texto, luego embeda cada chunk de forma aislada. En late chunking: embeda el documento entero (o secciones grandes) primero, dejando que el modelo de embeddings vea todo el contexto, y luego "extrae" embeddings de cada chunk a partir de la representación global.

Requiere un modelo de embeddings con ventana de contexto larga (al menos 8K-32K tokens) y soporte para token-level embeddings. Modelos como `jina-embeddings-v3` y algunos de OpenAI lo permiten.

**Cuándo funciona**: documentos donde el significado de cada parte depende fuertemente del contexto global. Un párrafo sobre "el modelo" en medio de un paper de ML tiene un significado muy distinto si "el modelo" se refiere a una red transformer o a un modelo de Markov, y el contexto global lo resuelve antes del chunking.

**Cuándo no funciona**: cuando tu modelo no soporta context windows grandes o no expone token-level embeddings. La mayoría de modelos open source ligeros (incluido `all-MiniLM-L6-v2`) no funcionan aquí.

Es una técnica emergente. Si tu pipeline ya funciona razonablemente, probablemente no vale la pena introducir late chunking ahora mismo. Tener el concepto presente sí, para cuando los modelos de contexto largo se abaraten más.

### **Agentic chunking**

Un agente con tool calls decide dinámicamente cómo partir un documento. El agente lee, evalúa la complejidad del contenido, y aplica una estrategia distinta para cada sección (recursive aquí, structural allí, semantic para esta otra parte). La idea es eliminar la decisión humana sobre qué estrategia aplicar, delegándola al agente.

python

```
# Conceptual sketch
CHUNKING_AGENT_PROMPT = """
You are a chunking agent. Given a document, decide for each section
which chunking strategy to apply: recursive, structural, semantic, or sentence-window.
Output a sequence of (section_text, strategy) pairs.
"""
```

**Cuándo funciona**: corpus heterogéneo donde diferentes documentos requieren diferentes tratamientos y no quieres mantener N pipelines distintos. Un sistema enterprise que ingesta a la vez emails, contratos, papers y código.

**Cuándo no funciona**: corpus homogéneo, donde es más simple y predecible aplicar la misma estrategia a todo. También: cualquier sistema con restricciones duras de coste de ingesta — los agentes son los más caros de todos.

### **Query-dependent chunking**

Idea reciente de AI21 (2026): en lugar de chunking estático en ingesta, varias resoluciones del mismo documento se indexan simultáneamente (chunks de 100, 200, 500, 1000 tokens) y en tiempo de consulta el sistema elige qué resolución usar según la pregunta. Preguntas concretas se contestan mejor con chunks pequeños; preguntas abiertas necesitan chunks grandes.

**Cuándo funciona**: corpus donde el mismo documento se consulta de formas muy distintas. Un manual técnico al que algunos usuarios preguntan "¿cuál es el código de error 42?" (chunk pequeño basta) y otros preguntan "¿cómo funciona el módulo de logging?" (necesitas chunks grandes).

**Cuándo no funciona**: la mayoría de los casos donde el patrón de consulta es predecible. Y multiplica el coste de storage por N resoluciones.

Es un patrón emergente; mantente al tanto, pero no inviertas en él ahora mismo a menos que tu caso lo justifique.

### **Contextual Retrieval (Anthropic)**

La técnica que probablemente vale la pena implementar de inmediato si tu pipeline RAG ya funciona pero no termina de afinar. Publicada por Anthropic en septiembre de 2024 y madurada durante 2025. La idea: antes de embedear cada chunk, enriquécelo con un párrafo corto de contexto generado por un LLM que sitúe ese chunk dentro del documento completo.

El prompt canónico de Anthropic:

```
<document>
{whole_document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_content}
</chunk>

Please give a short succinct context to situate this chunk within
the overall document for the purposes of improving search retrieval
of the chunk. Answer only with the succinct context and nothing else.
```

![sesion-07-articulo-03-figura-03-contextual-retrieval.jpg](https://media1-production-mightynetworks.imgix.net/asset/b508da6e-d0bf-427c-ab30-57ff952b72de/sesion-07-articulo-03-figura-03-contextual-retrieval.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El contexto generado se prepende al chunk antes de embedearlo y antes de indexarlo en BM25:

`[Generated context: This chunk discusses Q3 2024 revenue figures for the European market, mentioned in section 4.2 of the annual report.]

[Original chunk: Revenue grew by 3% over the previous quarter...]`

Los números que reporta Anthropic: 35% de reducción de fallos de retrieval solo con contextual embeddings, 49% combinándolo con BM25 contextual, hasta 67% sumando reranking. Los benchmarks independientes confirman las mejoras (la magnitud exacta depende del corpus, pero la dirección es robusta).

**Cuándo funciona**: prácticamente cualquier corpus con documentos largos donde los chunks individuales pueden perder contexto al ser aislados. Es decir, casi todos los casos reales.

**Cuándo no funciona**: corpus de chunks pequeños naturalmente autocontenidos (FAQs, tickets cortos) y cualquier sistema donde el coste de ingesta es la restricción dura.

**Sobre el coste**: contextualizar cada chunk requiere una llamada a un LLM por cada chunk durante la ingesta. Anthropic recomienda usar prompt caching para reducir el coste de pasar el documento completo cada vez, lo que rebaja el coste estimado a alrededor de $1 por millón de tokens contextualizados. Para un proyecto pequeño es despreciable; para grandes ingestas hay que medirlo.

Lo veremos implementado en la sesión en vivo y mediremos si compensa para nuestros presupuestos.

## **Cómo elegir: criterios honestos**

Doce estrategias es un catálogo, no una receta. Algunas observaciones para que el catálogo sea útil en la práctica.

**Primero**: empieza con `RecursiveCharacterTextSplitter` con 400-512 tokens y 10-20% de overlap. Los benchmarks recientes lo colocan repetidamente entre las mejores opciones, y es el más barato de implementar y operar. Solo cambia si tienes evidencia medida de que no es suficiente.

**Segundo**: si tu corpus tiene estructura explícita (Markdown, HTML, JSON, secciones de Word), úsala. Document-based chunking + metadata enriquecido es la palanca de mayor ROI conocida. Microsoft Azure documentó saltos de 15-25 puntos de accuracy solo con esto. No la desperdicies.

**Tercero**: si tu corpus tiene chunks que pierden sentido al aislarse, considera Contextual Retrieval. Es la técnica más madura de las "avanzadas" y la que más consistentemente mejora resultados sobre cualquier base.

**Cuarto**: semantic chunking, LLM-based chunking y técnicas relacionadas son herramientas legítimas pero **caras**. Justifícalas con datos: mide sobre tu corpus que aportan, no asumas que lo harán porque el blog post las elogie.

**Quinto**: parent-child / hierarchical chunking es un patrón de **arquitectura**, no solo de chunking. Implica decisiones sobre qué se indexa y qué se devuelve. No lo introduzcas si tu pipeline aún no funciona razonablemente con una estrategia plana.

**Sexto**: late chunking, agentic chunking y query-dependent chunking son técnicas emergentes interesantes. Manténte al tanto, pero no las introduzcas en producción a menos que tengas un caso de uso concreto que las justifique. La novedad no es por sí misma una ventaja.

**Séptimo y más importante**: el mejor chunking depende del tipo de documento. Un corpus heterogéneo casi siempre se beneficia de **distintas estrategias para distintos tipos de documento** dentro del mismo pipeline. Es exactamente la situación del proyecto, donde tenemos presupuestos JSON estructurados y transcripciones de reuniones en texto plano. Tratar ambos con la misma estrategia es dejar valor sobre la mesa.
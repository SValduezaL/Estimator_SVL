# Selección de modelos de embeddings: trade-offs en producción

Creada: 29 de mayo de 2026 16:37
Módulo: M3. Data Driven AI (https://www.notion.so/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S7. Embeddings y representación vectorial (https://www.notion.so/S7-Embeddings-y-representaci-n-vectorial-36fea9ca03c48018b87adcffb3272fa0?pvs=21)

En el artículo anterior dejamos clavada la teoría: un embedding es un vector, la geometría inducida por el entrenamiento es lo que hace que vectores cercanos correspondan a textos cercanos, y la métrica de similitud es prácticamente irrelevante mientras uses la que el modelo recomienda. Bien.

Ahora viene la decisión que de verdad mueve el dial de la calidad de tu sistema: **qué modelo eliges para vectorizar tus datos**. Y no hay respuesta universal. Para el servicio IA del proyecto tenemos delante al menos cinco candidatos razonables, con precios que van de cero a varios dólares por millón de tokens, con dimensionalidades entre 384 y 3072, con licencias que van de MIT a propietario cerrado, y con benchmarks que te dirán cosas distintas según a quién mires.

Este artículo es para que llegues a la sesión en vivo con tu decisión tomada y argumentada, no copiada de un blog. Cubro el panorama de 2026, por qué MTEB no es la palabra final, qué es Matryoshka Representation Learning, los cinco criterios reales de decisión y cómo aterrizan al proyecto, y termino con el modelo que vamos a usar (`text-embedding-3-small`) y por qué — incluyendo cuándo no sería la elección correcta.

## **El panorama: quién hay en 2026**

El espacio de modelos de embeddings se ha movido mucho en los últimos seis meses. La foto que pintas hoy es distinta de la de hace un trimestre. Voy a centrarme en los seis nombres que cualquier AI engineer de habla hispana debería conocer en mayo de 2026, separados en dos bloques: API comercial y open source self-hosted.

![sesion-07-articulo-02-figura-01-comparativa-modelos.jpg](https://media1-production-mightynetworks.imgix.net/asset/baef0366-2c85-4a58-87bc-9ea6c5637d21/sesion-07-articulo-02-figura-01-comparativa-modelos.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Comerciales (acceso por API).**

- **OpenAI** `text-embedding-3-small`. 1536 dimensiones por defecto, soporte Matryoshka hasta 256, $0.02 por millón de tokens. El caballo de batalla pragmático: barato, rápido, multilingüe decente, integración trivial con el SDK que ya usas desde la Sesión 01. MTEB en torno a 62.
- **OpenAI** `text-embedding-3-large`. 3072 dimensiones por defecto, Matryoshka hasta 256, $0.13 por millón de tokens. Mejor calidad que el small pero 6.5 veces más caro. Justificado cuando el dominio es complejo y el volumen no es enorme.
- **Cohere** `embed-v3`. Especialmente fuerte en multilingüe (100+ idiomas con calidad equilibrada), reranking integrado en su API, $0.10 por millón. Si tu corpus mezcla varios idiomas no anglosajones, Cohere suele ganar a OpenAI en benchmarks de retrieval cross-lingual.
- **Voyage AI** `voyage-3-large`. Optimizado específicamente para retrieval, no para clasificación o STS. Lidera benchmarks recientes de retrieval-focused MTEB. Apache 2.0 en algunos de sus modelos lite. Su pricing es similar a Cohere.

**Open source (self-hosted).**

- `BAAI/bge-m3`. Multilingüe robusto, soporta hasta 100+ idiomas, 1024 dimensiones, MIT. Tres modos en un mismo modelo: dense, sparse y multi-vector. Es la opción seria cuando privacidad de datos o coste a escala son restricciones duras. Requiere GPU para latencias decentes en producción.
- `sentence-transformers/all-MiniLM-L6-v2`. 384 dimensiones, Apache 2.0, principalmente entrenado en inglés. El "small fast cheap" del ecosistema open source: corre razonablemente en CPU, ocupa unos pocos cientos de MB, y para un prototipo es excelente. MTEB en torno a 56 — claramente por debajo de los modelos modernos, pero no insignificante.

Hay otros nombres relevantes (Google Gemini Embedding 2, Jina v5, Qwen3-Embedding, Nomic) que iré mencionando cuando aporten algo específico. El listado anterior no es exhaustivo, es el conjunto mínimo de nombres con los que deberías estar familiarizado.

Una advertencia de calibración antes de seguir: los precios, dimensionalidades y scores que cito son válidos en el momento en que escribo este artículo (mayo de 2026). Los proveedores comerciales recortan precios cada pocos meses, los modelos open source mejoran cada release. Verifica antes de comprometer una decisión arquitectónica importante.

## **MTEB no es lo que parece**

Si has buscado "best embedding model" en cualquier ranking online, probablemente has acabado en el MTEB Leaderboard de Hugging Face. MTEB es el *Massive Text Embeddings Benchmark*: un conjunto de tareas estandarizadas (retrieval, classification, clustering, reranking, STS) sobre datasets públicos en varios idiomas, y un score agregado por modelo. Es la referencia de facto del sector y, en general, vale la pena entender qué dice.

Pero hay tres cosas que MTEB **no** te dice y que conviene tener claras antes de usarlo como criterio único de decisión.

**Primera**: MTEB mide rendimiento promedio en datasets públicos generalistas. Tu dominio no es genérico. Un modelo que saca 65 en MTEB sobre noticias en inglés y libros públicos puede sacar 40 sobre tu corpus específico de presupuestos técnicos en español con jerga financiera. Y a la inversa: un modelo mediocre en MTEB puede brillar inesperadamente en tu nicho. Los rankings son punto de partida, no oráculo.

**Segunda**: MTEB se ha vuelto un objetivo de optimización en sí mismo. Muchos modelos están afinados específicamente para subir su score en MTEB, lo que no es lo mismo que estar afinados para producir mejores resultados en aplicaciones reales. Esta es la misma dinámica que afectó a SAT scores en EEUU o a ImageNet en computer vision hace una década: cuando una métrica se convierte en target, deja de ser buena métrica.

**Tercera**: investigaciones recientes (Vectara, NAACL 2025) midiendo 25 configuraciones distintas de chunking sobre 48 modelos de embeddings encontraron que **la variación introducida por la estrategia de chunking puede ser tan grande o mayor que la variación entre modelos**. En otras palabras: pasar de chunking ingenuo a chunking bien tuneado puede aportarte tanto como pasar de un modelo mediocre a uno excelente. Conclusión operativa: invertir tiempo en optimizar tu chunker rinde más que obsesionarte con cuál modelo es 1-2 puntos mejor en MTEB. Sobre esto va el artículo 3, no es casualidad.

La forma honesta de usar MTEB: como filtro grueso para descartar modelos claramente débiles, y como referencia secundaria. La forma correcta de elegir modelo: hacer benchmark sobre tus propios datos con tus consultas reales. Es exactamente lo que vamos a hacer en la sesión en vivo.

## **Matryoshka: el truco que cambia las matemáticas**

Hay un concepto que merece su propia sección porque cambia cómo piensas la dimensionalidad: **Matryoshka Representation Learning (MRL)**.

La idea, simplificada: durante el entrenamiento, el modelo se optimiza simultáneamente para producir embeddings buenos a varias dimensionalidades anidadas (típicamente 256, 512, 1024, 1536, 3072). La consecuencia mágica es que las primeras dimensiones del embedding cargan más información que las últimas. Puedes truncar el vector a cualquier longitud entre las dimensiones soportadas y conservas la mayor parte de la calidad semántica.

¿Qué tanta calidad conservas? Para `text-embedding-3-large`, OpenAI reportó que el vector truncado a 256 dimensiones supera a `text-embedding-ada-002` completo a 1536. Es un seis-a-uno de reducción de tamaño con ganancia de calidad respecto al modelo previo.

Hay dos formas de aplicarlo en producción.

**Vía parámetro de la API.** Si usas OpenAI, pasas el argumento `dimensions` en la llamada y el servidor devuelve el embedding ya truncado y renormalizado. Es la forma correcta.

python

```
from openai import OpenAI

client = OpenAI()

def embed(text: str, dimensions: int = 1536) -> list[float]:
    """Embed text with explicit dimensionality control via Matryoshka."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=dimensions,
    )
    return response.data[0].embedding

# Full embedding for highest quality
full = embed("OAuth 2.0 authentication backend", dimensions=1536)

# Compressed embedding for storage-constrained scenarios
compressed = embed("OAuth 2.0 authentication backend", dimensions=256)
```

**Vía truncado manual del vector.** Si por la razón que sea tienes el vector completo y quieres reducirlo después (por ejemplo, almacenaste 1536d en su día y ahora quieres una versión 256d sin re-llamar a la API), puedes truncar tú mismo. Pero hay un gotcha: **al truncar pierdes la propiedad de norma unitaria**, y muchas métricas y bases de datos vectoriales asumen vectores normalizados. Hay que renormalizar a mano.

python

```
import math

def renormalize(vec: list[float]) -> list[float]:
    """Renormalize a vector to unit L2 norm.

    Required after manual truncation of Matryoshka embeddings.
    """
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        raise ValueError("Cannot normalize a zero vector")
    return [x / norm for x in vec]

# Correct manual truncation
full = embed("OAuth 2.0 authentication backend", dimensions=1536)
truncated_256 = full[:256]
truncated_256_normalized = renormalize(truncated_256)

# Wrong: skipping renormalization
# truncated_256 still has values, but ||truncated_256|| < 1, which
# breaks downstream cosine similarity calculations that assume unit norm.
```

La regla práctica: cuando puedas pedir la dimensionalidad que quieres directamente vía API (`dimensions=768`), hazlo así. Solo cae al truncado manual cuando recuperas vectores ya almacenados y quieres una versión más corta.

¿Cuándo merece la pena truncar? Cuando vas a tener millones de vectores en producción y el coste de storage o la latencia de búsqueda empiezan a importar. Para los 15 presupuestos del proyecto, las matemáticas dan unos cientos de chunks como mucho — la diferencia entre 1536 y 256 dimensiones se mide en megabytes, no es la prioridad. Lo importante es que sabes que la palanca existe y cómo accionarla cuando llegue su momento.

## **Cinco criterios de decisión**

Resumido al máximo, la decisión de qué modelo usar se reduce a balancear cinco ejes. No hay respuesta única, hay un trade-off explícito que aceptas en cada eje.

**Eje 1 — Dimensionalidad.** Más dimensiones, en general, más capacidad de representación. Pero también más bytes por vector, más latencia de cómputo en operaciones por lote, más tiempo de búsqueda en la base vectorial. Para un proyecto pequeño (miles de vectores) la dimensionalidad es irrelevante. Para un sistema con cientos de millones de vectores, pasar de 1536 a 768 puede ser la diferencia entre cabe en RAM o no cabe.

**Eje 2 — Idioma del corpus.** Si todos tus datos están en inglés, te abre la puerta a modelos English-centric que son rápidos y baratos (como `all-MiniLM-L6-v2`). Si tienes mezcla de idiomas o algún idioma no anglosajón dominante, necesitas un modelo entrenado multilingüe (`text-embedding-3-*`, `bge-m3`, `embed-multilingual-v3`). Para el proyecto, las descripciones de los componentes están en inglés (convención del programa) pero los briefs que llegarán de clientes futuros probablemente vendrán en español. Esto excluye los modelos English-only y obliga a un multilingüe decente.

**Eje 3 — Dominio.** Un modelo entrenado mayoritariamente en noticias y prosa general puede ser sorprendentemente mediocre en jerga técnica especializada. Para corpus médicos hay modelos médicos. Para código hay modelos como `voyage-code-2`. Para el dominio "presupuestos de software" no hay modelo especializado público, así que vamos a tener que usar un modelo generalista y validar que funciona razonablemente sobre nuestros datos antes de hacer arquitectura encima.

**Eje 4 — Hosting y coste.** El trade-off clásico es API vs self-hosted. La API te da operaciones gestionadas, escalado automático y cero infra, a cambio de coste variable por token, latencia de red, dependencia de un proveedor externo, y datos saliendo de tu perímetro. El self-hosted te da cero coste por token (solo compute), latencia local previsible, datos sin salir, y dependencia operativa de mantener un servicio de inferencia con GPU. Para volúmenes bajos (<20M tokens/mes) la API casi siempre es más barata en total. Para volúmenes altos con datos sensibles, self-hosted gana.

**Eje 5 — Licencia.** Esto importa más de lo que la mayoría de tutoriales mencionan. Los modelos de OpenAI, Cohere y Voyage son propietarios: pagas por usar la API, no puedes auto-hostearlos, y los términos de servicio aplican a tus datos. Los modelos como `bge-m3` (MIT), `all-MiniLM-L6-v2` (Apache 2.0) o los `voyage-3-*` lite son auto-hosteables con licencias permisivas. Si tu cliente final requiere por contrato que ningún dato salga de su infraestructura (banca, sanidad, defensa), las opciones se reducen a self-hosted.

Estos cinco ejes no se priorizan igual en todos los proyectos. Para una startup en fase de prototipo, **hosting y coste** dominan: lo barato y rápido de integrar gana. Para un sistema enterprise en sanidad, **licencia y privacidad** dominan: nada que no se pueda auto-hostear. Para un sistema con corpus muy especializado, **dominio** domina: probablemente acabarás haciendo fine-tuning. Identifica primero qué eje pesa más en tu contexto y la decisión se simplifica.

![sesion-07-articulo-02-figura-02-ejes-decision.jpg](https://media1-production-mightynetworks.imgix.net/asset/abca77fe-dc01-48ef-84c2-80a53fa53323/sesion-07-articulo-02-figura-02-ejes-decision.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **La decisión del proyecto y por qué**

Para el servicio IA del proyecto, el modelo locked es `text-embedding-3-small` **de OpenAI con dimensiones por defecto (1536)**. El razonamiento, eje por eje:

- **Dimensionalidad**: 1536 es excesivo para el tamaño del corpus del proyecto, pero el coste extra de storage es despreciable a estas escalas (kilobytes, no gigabytes). Mantener el default simplifica y deja Matryoshka como palanca de optimización futura.
- **Idioma**: multilingüe decente. Descripciones de componentes en inglés, briefs probablemente en español. `text-embedding-3-small` no es el mejor multilingüe del mercado (lo es `bge-m3` o Cohere), pero es claramente suficiente.
- **Dominio**: ningún modelo es especializado en "presupuestos de software", así que cualquier generalista vale. La sesión en vivo validará con datos reales que funciona razonablemente.
- **Hosting y coste**: API ya configurada desde Sesión 01, cero fricción adicional. Ingestar 15 presupuestos con 5-10 chunks cada uno y unos 100 tokens por chunk son unos 15.000 tokens totales: $0.0003. Despreciable.
- **Licencia**: propietaria, pero el proyecto es académico y no hay datos sensibles. Aceptable.

**Por qué no las alternativas razonables:**

- `text-embedding-3-large`: 6.5x más caro por +2 puntos de MTEB. La mejora no se justifica a este volumen ni para este caso de uso. Si en producción se viera retrieval pobre, sería el upgrade más obvio.
- `bge-m3` **self-hosted**: técnicamente superior en multilingüe y gratis por token, pero introduce dependencia operacional (servidor de inferencia, idealmente con GPU para latencia decente) que no aporta valor pedagógico al programa. Lo dejamos como recurso complementario para el alumno que quiera explorar.
- `voyage-3-large`: probablemente el mejor en recall sobre retrieval-focused benchmarks, pero introduce un proveedor más con su propia API key, su propio billing, y un coste superior. Para un alumno que ya batalla con OpenAI, sumar Voyage no es la pedagogía adecuada.
- `all-MiniLM-L6-v2` **local**: tentador por simplicidad pero claramente inferior en multilingüe y MTEB. Lo usaremos en la sesión en vivo como contraste rápido para que el alumno vea con sus ojos la diferencia entre un modelo ligero y uno moderno.

La elección no es "es el mejor modelo posible". La elección es "es el mejor balance pedagogía/calidad/coste/operación para este contexto". Si mañana cambiamos el contexto (escalado a millones de presupuestos, datos sanitarios sensibles, dominio muy específico) la decisión cambiaría. Mantén esa flexibilidad mental.

## **Comparativa práctica con código**

Para fijar la decisión hace falta haberla tomado con datos, no con prosa. Lo que sigue es el patrón mínimo de medición que vas a ejecutar y refinar en la sesión en vivo. Funciona sobre cualquier subconjunto de textos de tu propio corpus.

python

```
import time
from openai import OpenAI
from sentence_transformers import SentenceTransformer

# --- Setup ---

client = OpenAI()
local_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def embed_openai_small(text: str, dimensions: int = 1536) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=dimensions,
    )
    return response.data[0].embedding

def embed_local_minilm(text: str) -> list[float]:
    embedding = local_model.encode(text, normalize_embeddings=True)
    return embedding.tolist()

# --- Measurement harness ---

def benchmark(name: str, embed_fn, texts: list[str]) -> dict:
    """Run an embedding function over a list of texts and return basic metrics."""
    start = time.perf_counter()
    embeddings = [embed_fn(t) for t in texts]
    elapsed = time.perf_counter() - start

    return {
        "model": name,
        "n_texts": len(texts),
        "total_seconds": round(elapsed, 3),
        "per_text_ms": round((elapsed / len(texts)) * 1000, 1),
        "dimensions": len(embeddings[0]),
        "first_embedding_norm": round(
            sum(x * x for x in embeddings[0]) ** 0.5, 4
        ),
    }

# --- Run on a sample of your project's data ---

sample_texts = [
    "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app",
    "Product catalog service with full-text search and category filtering",
    "GDPR consent management module with audit log",
    "Kubernetes deployment pipeline with blue-green release strategy",
]

print(benchmark("openai-3-small-1536d", embed_openai_small, sample_texts))
print(
    benchmark(
        "openai-3-small-256d",
        lambda t: embed_openai_small(t, dimensions=256),
        sample_texts,
    )
)
print(benchmark("local-minilm-l6-v2", embed_local_minilm, sample_texts))
```

Las observaciones cualitativas que vas a sacar al ejecutar esto sobre tu propio dataset:

- **Latencia por texto**: OpenAI ronda los 200-400 ms por llamada en serie (red + procesado del servidor). MiniLM local rondará los 10-30 ms por texto en CPU. En batch las cifras cambian: la API de OpenAI acepta lotes y el throughput sube mucho. Cubrimos el batching en el ejercicio pre-sesión.
- **Dimensionalidad**: 1536 vs 256 vs 384. Los 384 de MiniLM no son comparables linealmente a los 256 de OpenAI truncado; son espacios distintos entrenados con técnicas distintas.
- **Norma**: comprueba que es 1.0 (con margen de error de punto flotante) en los tres casos. Si no lo es, el modelo no entrega vectores normalizados y necesitas normalizarlos tú antes de usar cosine en bases de datos que asumen norma 1.

Sobre el coste real: con OpenAI puedes calcularlo aproximadamente como `n_tokens × $0.02 / 1.000.000`. Para tus 4 textos de ejemplo, son unos 40 tokens totales, redondeando: $0.0000008. Para el corpus completo del proyecto, ni siquiera vale la pena trackearlo. Cuando los volúmenes crecen sí vale la pena, y entonces entra en juego la **Batch API de OpenAI**, que aplica 50% de descuento a cambio de procesamiento asíncrono de hasta 24 horas. Lo veremos en el ejercicio pre-sesión.

## **Bridge al siguiente artículo**

Ya tienes claro qué modelo de embedding vas a usar y por qué. Lo que **no** hemos discutido todavía es cómo decides exactamente qué texto le pasas a ese modelo. ¿El presupuesto entero como un único string? ¿Cada componente por separado? ¿Trozos de N tokens? ¿Trozos por cambio de tema? Si esto te parece secundario, vuelve a leer la sección sobre MTEB de este artículo: el chunking puede mover el dial de la calidad de retrieval tanto o más que la elección de modelo.

Eso es el siguiente artículo: **Estrategias profesionales de chunking**. Vamos a cubrir el catálogo completo de estrategias que se usan hoy en sistemas reales — desde las clásicas (fixed-size, recursive, sentence-window) hasta las avanzadas (semantic, late chunking, agentic, Contextual Retrieval) — con criterios para elegir cada una. Es el artículo más extenso de los cuatro porque es el tema central de la sesión en vivo, y es donde verdaderamente se decide el éxito o fracaso de tu pipeline RAG.

Mientras tanto, ejecuta el harness de comparación de este artículo sobre tres o cuatro descripciones de tus propios presupuestos. Anota la latencia, la dimensionalidad y la norma de cada modelo. Llegarás a la sesión en vivo con datos concretos sobre tu corpus, no con intuiciones, y la conversación será mucho más productiva.
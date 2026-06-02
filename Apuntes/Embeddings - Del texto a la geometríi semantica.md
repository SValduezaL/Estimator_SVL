# Embeddings: Del texto a la geometría semántica

Creada: 29 de mayo de 2026 16:37
Módulo: M3. Data Driven AI (https://www.notion.so/M3-Data-Driven-AI-c62ea9ca03c483b1929d0167be89711e?pvs=21)
Sesión: S7. Embeddings y representación vectorial (https://www.notion.so/S7-Embeddings-y-representaci-n-vectorial-36fea9ca03c48018b87adcffb3272fa0?pvs=21)

Acabas de terminar la Sesión 06 con proyectos reales de varios sectores. Cada uno con sus componentes desglosados, horas estimadas, stack tecnológico y descripciones.

Lo que quieres hacer ahora es esto: cuando llegue un nuevo cliente con un brief del estilo *"necesitamos un servicio de autenticación con flujos OAuth para una app móvil del sector financiero"*, el sistema debe encontrar de forma automática qué componentes de tus presupuestos históricos son relevantes para construir la estimación. Y debe encontrarlos aunque el brief no comparta literalmente ninguna palabra con tus documentos. "Authentication service" debería encontrar "OAuth 2.0 backend", "JWT authorization module", "single sign-on integration", y todos los demás aunque ninguno de ellos use la palabra exacta "authentication".

Esto es búsqueda semántica. El problema no es nuevo, lo que es nuevo es la herramienta que vamos a usar para resolverlo: los embeddings. Este artículo establece la base teórica mínima para entender qué son, por qué funcionan, y cómo se comparan dos textos vía sus embeddings. No discutimos qué modelo elegir todavía (eso es el siguiente artículo) ni cómo partir documentos largos (artículos 3 y 4). Solo el primer ladrillo.

## **Qué es un embedding**

Un embedding es, mecánicamente, una función que toma un texto cualquiera y devuelve un vector de números reales de dimensión fija. Para el modelo `text-embedding-3-small` de OpenAI, esa dimensión es 1536. Para `all-MiniLM-L6-v2` de Sentence Transformers, es 384. Para los modelos `text-embedding-3-large`, son 3072 dimensiones. Pero lo importante no es el número, es la propiedad que se cumple sobre esos vectores: **textos semánticamente similares producen vectores cercanos en el espacio R^n**.

Vamos a verlo con código. Asumimos que ya tienes `OPENAI_API_KEY` configurada y el cliente de OpenAI instalado, exactamente como lo dejamos en la Sesión 01.

python

```
from openai import OpenAI

client = OpenAI()

text = "OAuth 2.0 authentication backend with JWT tokens for fintech mobile app"

response = client.embeddings.create(
    model="text-embedding-3-small",
    input=text,
)

embedding = response.data[0].embedding

print(f"Dimensions: {len(embedding)}")
print(f"First 5 values: {embedding[:5]}")
print(f"Last 5 values: {embedding[-5:]}")
print(f"Value type: {type(embedding[0]).__name__}")
```

La salida es una lista de 1536 floats. Si la imprimes entera, no verás absolutamente nada interpretable: una secuencia de números pequeños en torno a cero. Ninguna dimensión individual significa algo legible para un humano. La dimensión 142 no es "fintech-ness" ni la 803 es "complejidad del proyecto". Las dimensiones individuales no tienen interpretación directa, son el resultado de un proceso de optimización ciego durante el entrenamiento.

Lo que sí tiene significado son las **direcciones** y las **distancias relativas** entre vectores. Eso es lo que vamos a explotar.

## **Cómo aprenden la geometría**

Los modelos de embedding modernos se entrenan con una técnica llamada **aprendizaje contrastivo**. Simplificando bastante: durante el entrenamiento se le muestran al modelo millones de tripletes formados por una *ancla* (un texto), un *positivo* (un texto que debería estar cerca semánticamente del ancla) y uno o varios *negativos* (textos no relacionados). La función de pérdida del entrenamiento castiga al modelo cuando el ancla queda más cerca del negativo que del positivo, y lo premia cuando el ancla queda más cerca del positivo. Tras millones de iteraciones, el modelo encuentra una representación geométrica del espacio donde la cercanía mide algo parecido a la similitud semántica.

Cuál es "el positivo" depende de qué se entrene. Para embeddings de propósito general, los positivos suelen ser parafraseos, traducciones, oraciones consecutivas de un mismo documento, o pares de pregunta-respuesta. Para embeddings especializados en código, los positivos son fragmentos de código que resuelven problemas similares. Para embeddings multilingües, los positivos son traducciones del mismo texto a diferentes idiomas. La naturaleza de los positivos determina qué entiende el modelo por "similar".

Esto tiene una consecuencia práctica directa: si entrenas un modelo con parafraseos de inglés general y luego le pasas presupuestos técnicos en español con jerga financiera específica, no esperes el mismo nivel de discriminación que en el dominio para el que fue entrenado. Lo abordamos en el siguiente artículo cuando hablemos de selección de modelos.

Una nota epistemológica que vale la pena dejar clara: nadie programó explícitamente las dimensiones del espacio vectorial. Emergieron del entrenamiento. Hay líneas de investigación (interpretabilidad mecanística) que intentan descifrar qué codifica cada dirección, pero a nivel de producción tratamos al modelo como una caja negra cuyas distancias funcionan. Funcionan empíricamente, lo medimos con benchmarks, y eso es suficiente para construir sistemas sobre ellos.

El ejemplo clásico que se cita siempre es `vector("rey") - vector("hombre") + vector("mujer") ≈ vector("reina")`. Es un resultado real de los embeddings de palabras de hace una década (Word2Vec), pero te aviso: con embeddings modernos de oraciones esos juegos aritméticos casi nunca funcionan tan limpios. Lo que sí sigue siendo cierto es que vectores cercanos siguen correspondiendo a textos cercanos, y eso es lo único que necesitas para construir búsqueda semántica.

![sesion-07-articulo-01-figura-01-espacio-semantico.jpg](https://media1-production-mightynetworks.imgix.net/asset/76a33305-34fc-4c5f-bf74-9d0d25f45236/sesion-07-articulo-01-figura-01-espacio-semantico.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

## **Métricas de similitud**

Para hablar de "vectores cercanos" hace falta una métrica. Hay tres que vas a encontrarte en todas las APIs y librerías de vector search. Las tres son las únicas que necesitas conocer.

![sesion-07-articulo-01-figura-02-metricas-similitud.jpg](https://media1-production-mightynetworks.imgix.net/asset/f1b9d78a-819c-423e-9a80-ecbb3dff23d0/sesion-07-articulo-01-figura-02-metricas-similitud.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

**Similitud coseno (cosine similarity).** Mide el ángulo entre dos vectores. Devuelve un valor entre -1 y 1, donde 1 significa que apuntan en la misma dirección, 0 que son perpendiculares, y -1 que apuntan en direcciones opuestas. Para texto, la práctica habitual es que los valores caigan entre 0 y 1 (los embeddings modernos rara vez producen vectores que apunten en direcciones opuestas porque la loss contrastiva no premia explícitamente que los negativos queden en el lado opuesto del espacio).

**La fórmula:**

`cosine(A, B) = (A · B) / (||A|| × ||B||)`

donde `A · B` es el producto escalar y `||A||` es la norma euclidiana del vector A.

Su rasgo definitorio: **es insensible a la magnitud de los vectores**. Solo mira la dirección. Dos vectores que apuntan exactamente al mismo sitio dan cosine = 1 aunque uno tenga el doble de longitud que el otro. Esto es deseable en texto, porque no queremos que un documento largo (que puede acabar produciendo un vector con mayor magnitud) parezca menos parecido a una consulta corta por el simple hecho de su tamaño.

**Producto escalar (dot product).** Es el numerador de la similitud coseno. La fórmula:

`dot(A, B) = sum(A[i] × B[i] for i in range(n))`

Devuelve un valor sin acotar, sensible tanto a la dirección como a la magnitud. Computacionalmente es más barato que el coseno porque no requiere calcular las normas.

Hay un detalle importante: la mayoría de modelos modernos, incluyendo `text-embedding-3-small`, producen vectores ya normalizados a longitud 1 (norma euclidiana = 1). Cuando los vectores están normalizados, `dot product` y `cosine similarity` dan **exactamente el mismo resultado**. Esa es la razón por la que muchas bases de datos vectoriales en producción usan dot product internamente: misma calidad que el coseno, menos operaciones por consulta.

**Distancia euclidiana (euclidean distance).** La distancia recta entre los dos puntos en R^n. La fórmula:

`euclidean(A, B) = sqrt(sum((A[i] - B[i])^2 for i in range(n)))`

Devuelve un valor entre 0 (idénticos) e infinito (muy lejanos). Sensible a la magnitud.

Para vectores normalizados (longitud 1), la distancia euclidiana y la similitud coseno están relacionadas por una fórmula simple: `euclidean(A, B)^2 = 2 - 2 × cosine(A, B)`. Ordenan los resultados de igual manera, así que cualquier búsqueda top-k que use euclidean sobre vectores normalizados devuelve los mismos resultados en el mismo orden que usando cosine.

**La regla práctica para elegir métrica**: usa la que se usó durante el entrenamiento del modelo. Lo indica la model card. Si el modelo se entrenó con cosine como función de similitud en la loss, usa cosine en producción. Si se entrenó con dot product (y produce vectores normalizados), usa dot product. Para `text-embedding-3-small` de OpenAI, los vectores vienen normalizados, así que cosine y dot product son intercambiables. Para `sentence-transformers/all-MiniLM-L6-v2`, la model card recomienda cosine.

No hay misterio. No hay mejor métrica universal. Es una propiedad del modelo, no una decisión arquitectónica.

Implementemos las tres con la biblioteca estándar de Python, sin numpy. Esto es exactamente lo que vas a usar en el `compare.py` del ejercicio pre-sesión:

python

```
import math

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two equal-length vectors.

    Returns a value in [-1, 1]. For text embeddings from modern models,
    values typically fall in [0, 1].
    """
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have the same dimensionality")

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        raise ValueError("Cannot compute similarity for zero-norm vectors")

    return dot / (norm_a * norm_b)

def dot_product(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute the dot product. For normalized vectors, equivalent to cosine."""
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have the same dimensionality")
    return sum(a * b for a, b in zip(vec_a, vec_b))

def euclidean_distance(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute the Euclidean distance. Lower means more similar."""
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have the same dimensionality")
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))
```

Tres funciones, treinta líneas, ninguna dependencia externa. Esto es todo lo que necesitas para construir comparación entre embeddings.

## **Aplicado al proyecto**

Vamos a ver la geometría en acción sobre textos del dominio del proyecto. Embedea estos tres pares y observa los resultados:

python

```
from openai import OpenAI

client = OpenAI()

def embed(text: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding

pairs = [
    # Pair 1: technically close, different wording
    (
        "User authentication API with role-based access control",
        "Login service backend with permission management",
    ),
    # Pair 2: unrelated, same domain (web backend)
    (
        "User authentication API with role-based access control",
        "Real-time WebSocket chat module with message persistence",
    ),
    # Pair 3: generic, ambiguous overlap
    (
        "Performance optimization for high-traffic endpoints",
        "Caching strategy for database-heavy queries",
    ),
]

for text_a, text_b in pairs:
    vec_a = embed(text_a)
    vec_b = embed(text_b)
    sim = cosine_similarity(vec_a, vec_b)
    print(f"Similarity: {sim:.4f}")
    print(f"  A: {text_a}")
    print(f"  B: {text_b}")
    print()
```

Sin ejecutarlo, ya puedes anticipar el comportamiento cualitativo. Para la pareja 1, esperarías una similitud alta: ambos textos describen esencialmente lo mismo (autenticación de usuarios con control de acceso) con vocabulario distinto. Para la pareja 2, similitud sustancialmente más baja: las dos cosas son backend web pero son funcionalidades diferentes. Para la pareja 3, la similitud va a ser interesante: ambos textos hablan de optimización de rendimiento pero desde ángulos distintos (endpoints vs queries), así que el resultado dependerá de hasta qué punto el modelo asocia "performance" con "caching" en su entrenamiento.

Lo importante es la **estructura del resultado**, no los números absolutos. Si la pareja 1 sale claramente por encima de la 2, el modelo está discriminando bien. Si las tres dieran valores similares, tendrías un problema: el modelo no separa lo cercano de lo lejano en tu dominio, y necesitarías cambiarlo.

Esto es exactamente lo que mides en el `SANITY_CHECK.md` del ejercicio pre-sesión, aunque con otros tres pares. No es validación formal de calidad de retrieval (eso vendrá en Sesión 11 con métricas como recall@k y NDCG), pero es el mínimo aceptable para confirmar que el pipeline funciona end-to-end antes de invertir tiempo en optimizarlo.

## **Lo que un embedding no resuelve**

Toca un par de honestidades antes de cerrar el artículo, porque la narrativa promocional de los embeddings tiende a presentarlos como bala de plata y no lo son.

**Los embeddings no entienden números, fechas ni códigos identificadores.** Si tu consulta es *"presupuestos de 2024"* y los presupuestos tienen el año en metadata, no esperes que el embedding aprenda solo a filtrar por año. Para eso usas filtros estructurados sobre el metadata, no similitud vectorial. Los números aparecen en los embeddings como tokens cualesquiera y el modelo no aplica aritmética sobre ellos.

**Los embeddings son débiles para coincidencias exactas de palabras raras.** Si buscas un nombre propio que aparece tal cual en un documento, BM25 (la métrica clásica de term frequency / inverse document frequency) probablemente lo recupere mejor que cualquier embedding. Por eso muchas búsquedas serias en producción combinan ambos (hybrid search), tema que veremos en Sesión 10.

**Los embeddings sufren la maldición de la dimensionalidad.** En espacios de muchas dimensiones, las distancias entre pares aleatorios de puntos tienden a concentrarse en un rango estrecho. Es la razón por la que ver valores de similitud entre 0.2 y 0.5 para textos no relacionados es completamente normal: el "cero" de no-relación no aparece en la práctica. Calibra tus umbrales sobre tu propio dataset, no asumas que `sim > 0.7` significa "muy similar" en términos absolutos. Es solo "más similar que lo que dieron los pares no relacionados que medí".

**La elección de modelo importa mucho más que la elección de métrica.** Pasarte de cosine a dot product cuando el modelo está normalizado no cambia nada. Cambiar de un modelo English-only a uno multilingüe cuando tus datos son medio español medio inglés sí cambia los resultados drásticamente.

## **Bridge al siguiente artículo**

Ya sabes qué es un embedding, cómo emerge la geometría semántica durante el entrenamiento, y cómo medir similitud entre vectores. Lo que no hemos discutido todavía es la decisión que más impacto va a tener en la calidad de tu sistema: qué modelo usar exactamente.

¿`text-embedding-3-small` o `text-embedding-3-large`? ¿OpenAI o un modelo open source corriendo local? ¿1536 dimensiones o 256 con Matryoshka? ¿Qué pasa cuando los presupuestos están en español y las transcripciones en inglés mezclado? ¿En qué se diferencia un modelo entrenado para retrieval de uno entrenado para clasificación? ¿Cómo se interpreta el MTEB y por qué los benchmarks genéricos no son suficientes?

Todo eso es el siguiente artículo: **Selección de modelos de embeddings: trade-offs en producción**.

Mientras tanto, instala el cliente de OpenAI, ejecuta el primer snippet de este artículo sobre un par de descripciones de tus propios presupuestos y mira con tus ojos cómo se ven 1536 floats. Es una experiencia que te ahorra muchos malentendidos posteriores sobre qué hay realmente dentro de un vector.
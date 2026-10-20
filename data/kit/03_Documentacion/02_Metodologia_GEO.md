# Metodología GEO de reload.

Cómo se mide la visibilidad de una marca en los LLMs. Esta es la metodología que sigue el estudio de citación del kit, y la base sobre la que debe razonar vuestro sistema.

---

## 1. GEO frente a SEO

| | **SEO** | **GEO** |
|---|---|---|
| Dónde se compite | Páginas de resultados de un buscador | Respuestas generadas por asistentes de IA |
| Qué se obtiene | Un enlace en una posición | Una **mención** dentro de un texto, con posición, tono y fuentes |
| Qué se mide | Posición, tráfico, clics | **Aparición, posición, calidad de la mención, recomendación, fuentes** |
| Variabilidad | Relativamente estable | **No determinista**: la misma pregunta puede dar respuestas distintas |
| Quién decide | El algoritmo del buscador | El modelo, apoyándose en su conocimiento y en las **fuentes que consulta** |

GEO no sustituye al SEO: lo complementa. Lo que cambia es **qué se mide y dónde hay que estar presente** (no solo en la propia web, sino en las fuentes que los modelos consultan y citan).

## 2. El estudio de citación: visión general

```
Banco de prompts ──► Instanciación ──► Ejecución en LLMs ──► Evaluación ──► Score e insights
 (qué preguntan      (marcas,          (4 motores, con       (¿aparece?      (por marca, motor,
  los usuarios)       pares, ciudades)   búsqueda web,         ¿posición?      embudo, fuentes)
                                         varias repeticiones)  ¿tono? ¿fuentes?)
```

1. Se diseña un **banco de prompts** que simula cómo preguntan los usuarios reales en cada fase de su decisión.
2. Cada prompt se **instancia** con las marcas, pares de marcas y ciudades del estudio.
3. Cada prompt se **ejecuta** en varios motores, con búsqueda web activada, y **varias veces** (los modelos no son deterministas).
4. Cada respuesta se **evalúa** marca a marca.
5. Los resultados se agregan en un **score** y en tablas de insights.

## 3. El embudo de decisión: cuatro intenciones

Los prompts se clasifican según el momento del embudo en el que está el usuario.

| Intención | Qué quiere el usuario | Ejemplo (oftalmología) |
|---|---|---|
| **Descubrimiento** | Conocer qué opciones existen | *«¿Cuáles son las mejores clínicas oftalmológicas de España para operarse la vista?»* |
| **Comparación** | Contrastar opciones o marcas | *«Compara las principales clínicas de cirugía ocular: reputación, tecnología y precio.»* · *«¿X o Y? ¿Cuál elegirías?»* |
| **Validación** | Confirmar que una opción es fiable | *«¿Qué percepción tienen los pacientes de X?»* · *«¿Qué debería revisar antes de operarme en X?»* |
| **Decisión** | Elegir y actuar | *«Ya he comparado varias clínicas y tengo que decidirme esta semana. ¿Cuál elegirías?»* · *«¿Qué clínica ofrece la mejor relación calidad-precio?»* |

Una marca puede ser visible en descubrimiento y desaparecer en decisión (o al revés). **Ver dónde entra y dónde se cae cada marca en el embudo es uno de los análisis más valiosos.**

## 4. Familias de prompts

Cada prompt pertenece a una de nueve familias, que se agrupan en las cuatro intenciones.

| Código | Familia | Intención | Qué mide |
|---|---|---|---|
| DG | Descubrimiento genérico | Descubrimiento | Visibilidad espontánea ante preguntas de categoría |
| DP | Descubrimiento por perfil | Descubrimiento | Recomendación según el perfil del usuario (edad, situación, necesidad) |
| LO | Localización | Descubrimiento | Visibilidad en preguntas con ciudad |
| CO | Comparación de opciones | Comparación | Qué lista y qué criterios propone el motor |
| CM | Comparación de marcas | Comparación | Enfrentamientos directos entre marcas |
| VR | Validación reputacional | Validación | Percepción, confianza y objeciones sobre una marca |
| FU | Fuentes y citación | Validación | En qué fuentes se apoya el motor |
| DF | Decisión final | Decisión | Recomendación activa en el momento de decidir |
| PR | Precio y valor | Decisión | Sensibilidad a presupuesto y calidad-precio |

### Tipos de instanciación

| Tipo | Qué significa | Marcas que se evalúan |
|---|---|---|
| `generico` | El prompt no nombra ninguna marca | **Todas** las marcas del sector |
| `ciudad` | Igual, con una ciudad (`[CIUDAD]`) | Todas las marcas |
| `marca` | El prompt nombra una marca (`[MARCA_A]`) | Solo esa marca |
| `par` | El prompt enfrenta dos marcas (`[MARCA_A]` y `[MARCA_B]`) | Esas dos marcas |

### Marcas foco y marcas de contexto

- **Marcas foco** (4 por sector): la marca objeto del estudio, sus competidores directos y una marca de referencia. Reciben prompts propios (`marca` y `par`).
- **Marcas de contexto** (6 por sector): los actores reales del mercado, entre ellos el **líder del mercado**. Se **detectan y puntúan en las mismas respuestas**, sin prompts propios.
- **Pares estratégicos**: en vez de todas las combinaciones, se enfrenta a la marca de referencia con cada foco y a cada foco con el líder del mercado.

## 5. Ejecución en los motores

- **Motores**: ChatGPT, Gemini, Perplexity y Claude, todos con **búsqueda web activada** (los asistentes reales consultan fuentes en tiempo real).
- **Repeticiones**: cada prompt se ejecuta varias veces en cada motor (3 en el kit) porque las respuestas **varían** de una ejecución a otra. La **consistencia** entre repeticiones es en sí misma un dato: una marca citada siempre tiene presencia consolidada; una citada a veces está en zona de azar.
- **Sin búsqueda**: a veces un motor responde sin lanzar búsqueda (en el kit, la columna de fuentes queda vacía).

## 6. Evaluación de las respuestas

Para cada ejecución y cada marca se registra:

| Dimensión | Valores | Cómo se obtiene |
|---|---|---|
| **Aparece** | 1 / 0 | Detección del nombre de la marca o de sus alias en el texto (sin distinguir mayúsculas ni acentos) |
| **Posición** | 1, 2, 3… | Orden de primera aparición entre las marcas del sector presentes en la respuesta |
| **Tipo de mención** | Recomendación activa · Comparación neutra · Pasiva | Juez (LLM o reglas) |
| **Fuerza de recomendación** | **3** recomendación principal · **2** recomendación positiva secundaria · **1** mención neutra · **0** no aparece · **-1** aparece con advertencia o percepción negativa | Juez |
| **Sentimiento** | positivo · neutro · negativo | Juez |
| **Tipo de fuente** | Ranking / institución · Medio · Web propia · Directorio / comparador · Plataforma de reseñas · Red social / foro · Sin fuente | Juez, a partir de las fuentes que cita el motor |
| **Fuera de territorio** | sí / vacío | Aviso cuando la respuesta habla de otra categoría distinta a la del prompt |

### Cuidado con las menciones engañosas

- **Mención ≠ recomendación.** Una marca puede aparecer en una lista como ejemplo, como alternativa débil o con una advertencia. Por eso existen el tipo de mención y la fuerza.
- **Aparecer para decir que no se conoce.** Un motor puede nombrar una marca para decir *«no dispongo de información fiable sobre X»*. La detección por texto marca `aparece = 1`, pero no es una buena señal: en el kit se refleja con tipo `Pasiva`, fuerza `1` y fuente `Sin fuente`.
- **Alias.** Los textos pueden llamar a una marca por una forma abreviada («Alborada» en lugar de «Clínica Alborada Visión»). El archivo `marcas.csv` incluye los alias.

## 7. Score de Citación (0-100)

Resume en un número cuán visible y bien recomendada está una marca. Se calcula por marca (y por marca y motor) con cuatro componentes:

| Componente | Peso máximo | Cómo se calcula |
|---|---:|---|
| **Aparición** | 30 | `30 × (ejecuciones con aparición / ejecuciones evaluadas)` |
| **Posición** | 20 | `20 × (peso de posición medio / 3)`. Peso: 1.ª posición = 3 · 2.ª-3.ª = 2 · 4.ª o inferior = 1 · no aparece = 0 |
| **Fuerza de recomendación** | 30 | `30 × (fuerza media / 3)`, con mínimo 0 (la fuerza de «no aparece» es 0) |
| **Calidad de la fuente** | 20 | `20 × tasa de aparición × calidad media de las fuentes de sus apariciones` |

**Calidad por tipo de fuente** (valores del estudio):

| Tipo de fuente | Calidad |
|---|---:|
| Ranking / institución | 1,0 |
| Medio | 0,9 |
| Web propia | 0,7 |
| Directorio / comparador | 0,6 |
| Plataforma de reseñas | 0,6 |
| Red social / foro | 0,4 |
| Sin fuente | 0,2 |

> Podéis proponer otras ponderaciones si las justificáis. Lo importante es que el score sea **explicable y reproducible**.

## 8. Visibilidad espontánea frente a asistida (muy importante)

Hay dos situaciones distintas:

- **Espontánea**: el prompt **no nombra la marca** (tipos `generico` y `ciudad`) y el motor decide por sí solo si la incluye. Mide si el motor la **conoce y la recomienda por iniciativa propia**.
- **Asistida**: el prompt **nombra la marca** (tipos `marca` y `par`). La marca aparece casi siempre porque la menciona la propia pregunta. Mide **qué dice el motor de ella**, no si la descubre.

Si mezcláis ambas al calcular «% de citación por fase del embudo», la fase de **Validación** (casi todo prompts con marca) saldrá artificialmente alta para las marcas foco. Un buen análisis **separa las dos** y no concluye «gran visibilidad» a partir de prompts que la nombran.

El campo `Instanciación` de `banco_prompts.csv` os indica qué prompts son de cada tipo.

## 9. Qué influye en que un LLM cite una marca (hipótesis de trabajo)

Estas son las **palancas** que se manejan habitualmente en GEO. Son **hipótesis de la industria, no garantías**: los modelos cambian y ninguna acción asegura resultados. Por eso todo plan debe incluir **re-medición**.

| Palanca | Ejemplos de acciones |
|---|---|
| **Autoridad en fuentes de terceros** | Aparecer en rankings sectoriales y guías «mejores X»; presencia en prensa especializada; relaciones públicas digitales; premios y certificaciones |
| **Entidad y datos estructurados** | Perfil de empresa completo y coherente; datos estructurados (schema.org) en la web; coherencia del nombre y atributos en todos los directorios; presencia en bases de conocimiento (Wikipedia / Wikidata) cuando se cumplan los criterios de notoriedad |
| **Contenido que responde a preguntas reales** | Páginas y FAQ diseñadas a partir del banco de prompts; comparativas honestas; contenido por perfil de usuario y por ciudad; precios y financiación explícitos; formato claro y fácil de citar (listas, tablas, datos propios) |
| **Reputación y reseñas** | Volumen y recencia de reseñas en las plataformas relevantes; respuesta a reseñas; gestión de las objeciones recurrentes (esperas, ruido, precio…) |
| **Comunidades y plataformas** | Presencia en foros, vídeo y redes que los motores citan en el sector |
| **Accesibilidad técnica** | Que la web sea rastreable por los bots; contenido accesible sin depender de scripts pesados; rendimiento; mapa del sitio |
| **Medición** | Re-ejecutar el estudio de forma periódica; KPIs de visibilidad espontánea, recomendación y fuentes |

## 10. Limitaciones que debéis conocer

- **No determinismo**: la misma pregunta puede dar respuestas distintas. Por eso se repite.
- **Cambios de modelo**: los modelos y sus fuentes cambian; el estudio es una **foto en una fecha**.
- **Sesgo del banco de prompts**: los resultados dependen de cómo se formulan las preguntas.
- **Muestra limitada**: un estudio con pocos prompts da tendencias, no certezas estadísticas.
- **Juez imperfecto**: el LLM que evalúa las menciones puede equivocarse; conviene validar una muestra.
- **Datos del kit sintéticos**: reproducen la estructura y los patrones de un estudio real, pero **no su comportamiento real**.

## 11. Glosario

| Término | Significado |
|---|---|
| **GEO** | *Generative Engine Optimization*: optimizar la presencia de una marca en respuestas de IA generativa |
| **Motor** | Cada asistente de IA consultado (ChatGPT, Gemini, Perplexity, Claude) |
| **Prompt** | La pregunta que se lanza al motor |
| **Ejecución** | Un prompt lanzado a un motor en una repetición concreta |
| **Instanciación** | Sustituir marcas o ciudades en una plantilla de prompt |
| **Embudo** | Fases de la decisión del usuario: descubrimiento, comparación, validación, decisión |
| **Marca foco / contexto** | Marcas con prompts propios / marcas detectadas en las mismas respuestas |
| **Visibilidad espontánea** | Aparición de la marca sin que el prompt la nombre |
| **Fuerza de recomendación** | Escala de -1 a 3 que mide cuán recomendada aparece una marca |
| **Juez** | Componente (LLM o reglas) que clasifica cómo se menciona una marca |
| **Grounding / búsqueda web** | Capacidad del motor de consultar fuentes externas al responder |
| **Fuente citada** | Dominio o página en la que se apoya el motor |
| **Palanca** | Tipo de acción para mejorar la visibilidad (contenido, PR, reputación, datos…) |

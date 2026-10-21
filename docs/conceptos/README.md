# Conceptos de posiq. para la presentación y los entregables

Estos documentos explican, en español claro y con ejemplos, todo lo que hay que saber contar de
posiq.: qué mide, cómo lo calcula, qué parte hace la IA y qué parte el código, qué entrega al
cliente y por qué el cliente seguiría pagando. Cada fórmula y cada cifra lleva al lado el fichero
del repositorio donde se puede comprobar.

> **REGLA DE ORO: caso sintético del reto frente a medición real**
>
> - **Todo el kit del reto es ficticio.** Lo dice su guía: «Todos los datos, marcas, personas y
>   cifras son ficticios y sintéticos» (`data/kit/00_LEEME_Guia_del_kit.md`). Clínica Alborada
>   Visión y sus competidores no existen. Las 624 respuestas de «ChatGPT», «Gemini», «Perplexity»
>   y «Claude» las escribieron los organizadores. Los dominios de las fuentes acaban en `.example`.
> - **Toda cifra de Alborada es «nuestro método aplicado al caso sintético del reto».** Por
>   ejemplo: 25,93 (25,9 [21,6–30,1]); 8.ª de 10; 18 % en las respuestas atribuidas a ChatGPT;
>   Oftalmos Centro por delante sin estar declarado; 5,9 % de citas a la web propia;
>   0 inexactitudes; proyección 25,9 → 30,8; escenarios 27,7 / 28,2 / 30,8. Ninguna describe una
>   clínica real ni el comportamiento real de un asistente de IA.
> - **El modo real (preguntar a las APIs de los motores) está programado, pero no se ha ejecutado
>   nunca.** No hay ninguna medición real.
> - Lo que todavía no está en `develop` se marca **En desarrollo** o **PENDIENTE**, nunca como
>   hecho.
>
> Frases y contraejemplos para decirlo bien: [kit-vs-real.md §8](kit-vs-real.md#8-regla-para-la-presentación-y-los-entregables).

## Orden de lectura recomendado

Para preparar la presentación, leed los documentos en este orden. Cada uno da por sabidos los
anteriores.

| # | Documento | De qué trata, en una línea |
|---|---|---|
| 1 | [kit-vs-real.md](kit-vs-real.md) | Qué es el caso sintético, qué demuestra y qué no, cómo funcionaría una medición real, cuánto costaría (estimado) y la tabla de todas las cifras de la demo con el test que las fija. |
| 2 | [score-de-citacion.md](score-de-citacion.md) | El Score de Citación (0–100): población espontánea, fórmula de sus cuatro componentes, ejemplo resuelto de 25,93 paso a paso y por qué el juez cambia el resultado. |
| 3 | [rigor-y-seguimiento.md](rigor-y-seguimiento.md) | Margen de error (Wilson, bootstrap, Newcombe), cuándo una diferencia es significativa y el seguimiento con método: comparabilidad, cambios e indicadores adelantados. |
| 4 | [capas-determinista-y-no-determinista.md](capas-determinista-y-no-determinista.md) | Qué hace la IA y qué hace el código en cada paso del grafo, las reglas que lo garantizan, el juez acotado y las revisiones humanas. |
| 5 | [propuesta-geo.md](propuesta-geo.md) | La propuesta que recibe el cliente, sección a sección: qué contiene, de qué módulo sale y qué está ya en el Word, solo en la API o pendiente. |
| 6 | [../propuesta-valor.md](../propuesta-valor.md) | Propuesta de valor y modelo de negocio: «no vendemos un score, vendemos un seguimiento con método», las cinco críticas y qué hace hoy el producto. |
| 7 | [../glosario.md](../glosario.md) | Glosario alfabético de todos los términos, para consultar cuando surja una duda. |

Si solo hay tiempo para dos: **kit-vs-real.md** (qué se puede decir) y **score-de-citacion.md**
(qué es la cifra principal).

## Términos que se usan igual en todos los documentos

| Término | Significado acordado |
|---|---|
| **Caso sintético** (o **kit**) | El material ficticio del reto: brief de Alborada, 10 marcas, 624 respuestas escritas por los organizadores y 133 etiquetas de `muestra_evaluada.csv`. |
| **Modo kit** / **modo real** | posiq. leyendo las respuestas del kit (gratis, siempre igual) / preguntando a las APIs de los motores (de pago, **nunca ejecutado**). |
| **Cifra canónica** | 25,93 (25,9 con un decimal): Score de Citación de Alborada en el caso sintético, fijado en `tests/golden/test_demo_canonico.py`. |
| **Espontánea / asistida** | La pregunta no nombra / sí nombra la marca. El score usa solo espontáneas. |
| **Reglas** | Código que decide **siempre** si la marca aparece y en qué posición (`src/posiq/domain/detection.py`). |
| **Juez** | Lo que decide la **fuerza**, el **tipo de mención**, el **sentimiento** y si la mención **se apoya en las fuentes citadas**. Nunca clasifica el tipo de fuente ni cambia la aparición. Tres opciones: Jev con fallback DeepSeek, solo DeepSeek (sin clave de TypeSafe) o solo reglas (`src/posiq/domain/judge_questions.py`, ADR 0014). |
| **Mismo juez en toda la serie** | El juez cambia el resultado (25,93 con etiquetas del kit frente a 25,87 solo con reglas, en el caso sintético). Una serie solo es comparable con el mismo juez. Que el sistema lo compruebe está **PENDIENTE** (ola 2). |
| **Coste de un estudio real** | **Estimado**, no medido: unos 10,56 € solo en motores para un estudio del tamaño del kit; 10,57–12,42 € en total según el juez. Supera el tope por defecto de 5 € (`src/posiq/application/estimate.py`). |

## Cómo comprobar las cifras

Sin claves y sin coste:

```sh
python -m uv run pytest tests/golden tests/e2e
```

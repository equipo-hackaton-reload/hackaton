# El Score de Citación

> **Antes de leer.** Todas las cifras de Clínica Alborada Visión que aparecen aquí son **nuestro
> método aplicado al caso sintético del reto**. El kit es ficticio de principio a fin
> (`data/kit/00_LEEME_Guia_del_kit.md`: «Todos los datos, marcas, personas y cifras son ficticios y
> sintéticos»). Alborada y sus competidores no existen. Los organizadores escribieron las 624
> respuestas, y los dominios de las fuentes terminan en `.example`. **posiq. todavía no ha ejecutado
> nunca una medición real contra las APIs de los motores.**

## 1. Qué mide

El Score de Citación es un número de 0 a 100. Resume **cuánto aparece una marca cuando alguien pide
una recomendación a un asistente de IA sin nombrarla**, y **en qué condiciones aparece**:

- si sale pronto en la respuesta (posición);
- si el motor la recomienda o solo la nombra (fuerza);
- si la mención se apoya en fuentes de calidad (calidad de fuente).

La definición viene de la metodología del kit (`data/kit/03_Documentacion/02_Metodologia_GEO.md`,
§7). posiq. la implementa tal cual en `src/posiq/domain/scoring.py`. La metodología permite cambiar
los pesos si se justifica. Nosotros no los hemos cambiado: lo que pide es que el score sea
«explicable y reproducible».

## 2. Vocabulario mínimo

| Término | Qué es |
|---|---|
| **Motor** | Un asistente de IA: ChatGPT, Gemini, Perplexity o Claude (`Motor` en `src/posiq/domain/schemas.py`). |
| **Prompt** | Una pregunta que se le hace al motor, por ejemplo «¿Qué clínica me recomiendas para operarme de miopía en Madrid?». |
| **Ejecución** (`Run`) | Una respuesta concreta de un motor a un prompt. El mismo prompt se repite varias veces en cada motor porque las respuestas varían (3 veces en el kit). |
| **Evaluación** (`Evaluation`) | **La unidad de análisis del score.** Es una ejecución mirada para **una** marca: ¿aparece?, ¿en qué posición?, ¿con qué fuerza?, ¿con qué fuente? Una respuesta que se evalúa para 10 marcas da 10 evaluaciones. |
| **Juez** | Lo que rellena cada evaluación a partir del texto de la respuesta. Puede ser un conjunto de reglas, un modelo (Jev, con un LLM de respaldo) o una persona. Ver §7. |
| **Espontáneo / asistido** | Espontáneo: el prompt **no nombra** la marca. Asistido: el prompt **sí la nombra**. Ver §3. |

## 3. Población: qué evaluaciones cuentan

El score **no** usa todas las evaluaciones. Solo usa las que cumplen las tres condiciones siguientes
(`spontaneous_population` en `src/posiq/domain/scoring.py`):

1. **El prompt es espontáneo.** Su tipo de instanciación es `generico` (no nombra ninguna marca) o
   `ciudad` (igual, pero con una ciudad). En el código es el conjunto `ESPONTANEAS = {"generico",
   "ciudad"}` de `src/posiq/domain/schemas.py`. Los prompts `marca` y `par` nombran la marca en la
   propia pregunta. Ahí la marca sale casi siempre, y eso no demuestra que el motor la conozca.
   La metodología del kit (§8) avisa de que mezclar ambos tipos infla la visibilidad.
2. **La marca está en `marcas_a_evaluar` de esa ejecución.** En los prompts espontáneos se evalúan
   todas las marcas del sector.
3. **El motor coincide**, si se pide el score de un solo motor (ver §8).

Llamamos **N** al número de evaluaciones de la población y **A** a cuántas de ellas tienen
«aparece = sí».

**Si N = 0, no hay score.** El resultado (`ScoreBreakdown`) sale con `score = None` (sin datos) y
**nunca con 0**. Un 0 diría «la buscamos y no aparece». `None` dice «no la hemos medido». Son
conclusiones distintas.

## 4. La fórmula

Primero se calcula la **tasa de aparición**:

```
tasa = A / N
```

Después, cuatro componentes que suman como máximo 100 (`WEIGHTS` en `scoring.py`):

| Componente | Máximo | Fórmula en el código |
|---|---:|---|
| **Aparición** | 30 | `30 × tasa` |
| **Posición** | 20 | `20 × tasa × peso_medio / 3` |
| **Fuerza** | 30 | `30 × max(0, tasa × fuerza_media) / 3` |
| **Calidad de fuente** | 20 | `20 × tasa × calidad_media` |

```
score = aparición + posición + fuerza + calidad de fuente
```

`peso_medio`, `fuerza_media` y `calidad_media` son medias **solo sobre las A apariciones**. Se
explican a continuación.

### 4.1 Peso de posición (de 0 a 3)

La posición es el orden en que aparece la marca entre las marcas del sector que salen en la
respuesta. La función `peso_posicion` de `schemas.py` la convierte en un peso:

| Posición en la respuesta | Peso |
|---|---:|
| 1.ª | 3 |
| 2.ª o 3.ª | 2 |
| 4.ª o posterior | 1 |
| No aparece | 0 |

Se divide entre 3 (`MAX_PESO_POSICION`) para que el componente quede entre 0 y 20.

### 4.2 Fuerza de recomendación (de −1 a 3)

Escala del kit (docstring de `Evaluation` en `schemas.py` y metodología §6):

| Fuerza | Significado |
|---:|---|
| 3 | Recomendación principal |
| 2 | Recomendación positiva secundaria |
| 1 | Mención neutra |
| 0 | No aparece (reservado: si la marca aparece, la fuerza no puede ser 0) |
| −1 | Aparece con una advertencia o una percepción negativa |

Se divide entre 3 (`MAX_FUERZA`). El `max(0, …)` evita que el componente sea negativo. Si las
menciones negativas pesan más que las positivas, el componente vale 0. El score nunca baja de 0.

### 4.3 Calidad de la fuente (de 0 a 1)

Cada aparición recibe una calidad según el tipo de fuente que la respalda (`QUALITY_BY_TYPE` en
`scoring.py`, mismos valores que la metodología §7):

| Tipo de fuente | Calidad |
|---|---:|
| Ranking / institución | 1,0 |
| Medio | 0,9 |
| Web propia | 0,7 |
| Directorio / comparador | 0,6 |
| Plataforma de reseñas | 0,6 |
| Red social / foro | 0,4 |
| Sin fuente | 0,2 |

**Cuando el tipo de fuente no está resuelto.** Los jueces de posiq. (reglas y Jev) no clasifican el
tipo de fuente cuando la respuesta cita fuentes. Solo las etiquetas del kit (`muestra_evaluada.csv`)
lo traen resuelto. La función `appearance_quality` aplica entonces esta regla, en este orden:

1. Si la evaluación tiene `tipo_fuente`, se usa su valor de la tabla.
2. Si no lo tiene, se usa **la media de la columna `calidad` del catálogo de fuentes**
   (`fuentes_catalogo.csv`, columna `Calidad_de_fuente_0_1`) para las fuentes que citó **esa
   ejecución**.
3. Si la ejecución no citó ninguna fuente, se usa la calidad de «Sin fuente»: **0,2**.

### 4.4 Redondeo y versión

- Cada componente se redondea a **2 decimales**. El score total se calcula sumando los componentes
  **sin redondear** y se redondea después a 2 decimales. Por eso, en algún caso, la suma de los
  componentes mostrados puede diferir del total en 0,01.
- `SCORE_VERSION = "1.0"`. Cada resultado guarda la versión del score con la que se calculó
  (`ScoreBreakdown.score_version`). Si un día cambia la fórmula, la versión cambia, y el
  seguimiento declara no comparables las mediciones de versiones distintas (`src/posiq/domain/tracking.py`).

## 5. Por qué todo va multiplicado por la tasa

En la metodología del kit, la posición y la fuerza se promedian **sobre las N evaluaciones**.
Quien no aparece cuenta con peso 0 y fuerza 0. Si la marca aparece en el 40 % de las respuestas,
la media sobre N es igual a `tasa × media sobre las apariciones`. El código guarda las medias solo
sobre apariciones (`AppearanceProfile`) y multiplica por la tasa. El resultado es idéntico al del
kit.

La consecuencia práctica es que **la aparición manda**. Ejemplos:

- Una marca que aparece en el 10 % de las respuestas, siempre la primera, recomendada con fuerza 3 y
  citada desde rankings, saca como mucho `0,10 × 100 = 10` puntos.
- Para acercarse a 100 hay que aparecer casi siempre **y** hacerlo bien.

Es lo que pide el negocio: una recomendación excelente que casi nadie ve vale poco.

Ese perfil (tasa + tres medias) también permite recalcular el score con otra tasa sin tocar las
medias. Es lo que hace la simulación del plan (`score_from_profile`, usado en
`src/posiq/domain/simulation.py`).

## 6. Ejemplo resuelto: Alborada (caso sintético del reto)

> **Caso sintético.** Lo que sigue es nuestro método aplicado a los datos inventados del kit. No
> describe a ninguna clínica real.

El test `tests/golden/test_demo_canonico.py` fija el resultado: **N = 240 evaluaciones
espontáneas**, score **25,93**, con estos componentes:

| Componente | Valor |
|---|---:|
| Aparición | 11,62 |
| Posición | 4,72 |
| Fuerza | 3,92 |
| Calidad de fuente | 5,67 |
| **Score** | **25,93** |

Paso a paso: cómo se llega desde los datos. Los recuentos se obtienen ejecutando
`spontaneous_population` sobre el kit, igual que hace el test.

1. **Tasa.** Alborada aparece en **A = 93** de las **N = 240** evaluaciones espontáneas:
   `tasa = 93 / 240 = 0,3875`, alrededor del 39 %.
   → Aparición = `30 × 0,3875 = 11,625` → **11,62**.
2. **Posición.** Entre las 93 apariciones hay 17 en 1.ª posición (peso 3), 43 en 2.ª o 3.ª (peso 2)
   y 33 en 4.ª o más (peso 1). Peso medio = `(17×3 + 43×2 + 33×1) / 93 = 170 / 93 ≈ 1,83`. Suele
   salir entre la 2.ª y la 4.ª.
   → Posición = `20 × 0,3875 × (170/93) / 3 = 4,722` → **4,72**.
3. **Fuerza.** 92 apariciones con fuerza 1 y 1 con fuerza 2. Fuerza media = `94 / 93 ≈ 1,01`. La
   nombran, pero apenas la recomiendan.
   → Fuerza = `30 × max(0; 0,3875 × (94/93)) / 3 = 3,917` → **3,92**.
4. **Calidad de fuente.** Calidad media de las 93 apariciones = **0,7315** (≈ 0,73). Solo 4
   apariciones tienen tipo de fuente resuelto. Las otras 89 toman la media del catálogo de sus
   fuentes (regla de §4.3).
   → Calidad = `20 × 0,3875 × 0,7315 = 5,669` → **5,67**.
5. **Total.** `11,625 + 4,722 + 3,917 + 5,669 = 25,93`.

> Las cuentas usan los valores exactos (170/93, 94/93, 0,7315). Si se hacen a mano con las medias
> redondeadas (1,83; 1,01; 0,73) salen 4,73, 3,91 y 5,66: la diferencia es solo de redondeo.

Otras cifras del mismo caso sintético, también fijadas en tests:

- Alborada queda **8.ª de 10** marcas del ranking por score (`test_posicion_8_de_10`). El ranking
  ordena por score de mayor a menor (`_ranking` en `src/posiq/domain/metrics.py`).
- Con su margen de error es **25,9 [21,6–30,1]**: intervalo de confianza del 95 % por bootstrap,
  con 2.000 remuestreos y semilla fija (`tests/golden/test_rigor_alborada.py`,
  `intervalo_score` en `src/posiq/domain/stats.py`, ADR 0008).

**De dónde salen esas evaluaciones en el kit.** `kit.evaluations()` (`tests/golden/conftest.py`)
usa la etiqueta de `muestra_evaluada.csv` donde existe y las reglas de detección en el resto. De
las 240 evaluaciones espontáneas de Alborada, solo **13** tienen etiqueta del kit. Las otras 227
salen de las reglas. (El kit trae 133 etiquetas en total en `muestra_evaluada.csv`, para todas las
marcas y todos los tipos de prompt; 13 caen en las evaluaciones espontáneas de Alborada.) Las
etiquetas del kit también son inventadas por los organizadores.

## 7. Kit frente a medición real: de dónde salen los datos

| | **Kit (sintético)** | **Medición real (PENDIENTE: nunca ejecutada)** |
|---|---|---|
| Preguntas | Banco del kit (`banco_prompts.csv`), instanciado tal como se ejecutó | Banco que genera posiq. para la marca con un LLM (nodo `prompts`, prompt `prompts.v1`) |
| Respuestas | 624 respuestas **escritas por los organizadores** (`ejecuciones.csv`) | Respuestas de las **APIs** de ChatGPT, Gemini, Perplexity y Claude con búsqueda web. Los adaptadores existen, pero están «sin probar en real» (`docs/estado/B.md`) |
| Quién decide aparición y posición | Etiquetas de `muestra_evaluada.csv` donde existen; reglas en el resto | **Reglas** (`src/posiq/domain/detection.py`), siempre (ADR 0014) |
| Quién decide fuerza y apoyo en fuentes | Etiquetas donde existen; donde no, reglas (fuerza 1, fuente sin resolver) | El **juez**, que puede ser uno de tres (ADR 0003, ADR 0014): Jev con un LLM de respaldo (DeepSeek) si hay clave de TypeSafe; sin clave de TypeSafe, solo el LLM de respaldo (DeepSeek); o solo reglas con `JUDGE_PROVIDER=reglas`, más barato |
| Tipo de fuente | Resuelto solo en las etiquetas del kit | **Nadie lo clasifica**: media del catálogo de las fuentes de la ejecución o «Sin fuente» (0,2) |
| Fórmula | `scoring.py`, versión 1.0 | **La misma** |

**Qué decide exactamente el juez.** El juez (Jev o el LLM de respaldo) decide la **fuerza** (−1, 1,
2 o 3; `STRENGTH_LEVELS` en `src/posiq/domain/judge_questions.py`) y **si la mención se apoya en las
fuentes citadas**. No clasifica el tipo de fuente (Ranking, Medio, Web propia…). Si ve apoyo, deja
el tipo de fuente sin resolver y el score usa la media de calidad del catálogo de las fuentes de la
ejecución, igual que con reglas. Si no ve apoyo (o el motor no citó fuentes), pone «Sin fuente»
(0,2). Ver `answers_to_evaluation` en `src/posiq/domain/judge_questions.py`.

**La fórmula no cambia. Cambian las respuestas y quién las juzga.** Por eso cada cifra de este
documento es «nuestro método aplicado al caso sintético». Con una marca real, las cifras serán otras.

## 8. El juez cambia el resultado

El juez por reglas (`evaluation_from_detection` en `src/posiq/domain/detection.py`) solo sabe dos
cosas: si aparece y en qué posición. Por eso:

- **La fuerza vale siempre 1** cuando la marca aparece. No distingue «la recomiendo» de «existe». Con
  reglas no hay fuerza 3, 2 ni −1.
- **El tipo de fuente queda sin resolver** si la respuesta cita fuentes. La calidad se toma entonces
  de la media del catálogo (§4.3). Si no cita fuentes, se toma «Sin fuente» (0,2).
- **Aparición y posición no cambian.** Las reglas las deciden siempre, también con el juez Jev
  (ADR 0014).

**En el caso sintético** (`tests/golden/test_demo_canonico.py`):

| | Aparición | Posición | Fuerza | Calidad | Score | Puesto |
|---|---:|---:|---:|---:|---:|---:|
| Etiquetas del kit + reglas | 11,62 | 4,72 | 3,92 | 5,67 | **25,93** | 8.º |
| Solo reglas | 11,62 | 4,72 | 3,88 | 5,65 | **25,87** | 8.º |

La diferencia es pequeña **porque en el kit casi todo ya venía de reglas**: solo 13 de las 240
evaluaciones de Alborada tienen etiqueta. **No hay que leerlo como «el juez casi no importa».** En
una medición real, un juez semántico (Jev o el LLM de respaldo) puede poner fuerzas de 3, 2 o −1 y
marcar como «Sin fuente» (0,2) las menciones que no ve apoyadas en las fuentes citadas. Eso puede
bajar la calidad frente a la de reglas, que usa la media del catálogo. Tanto la fuerza (que pesa
hasta 30 puntos) como la calidad de fuente pueden moverse en cualquier dirección, y mucho más que
en el kit.

### Comparabilidad: una serie solo vale con el mismo juez

posiq. vende una **serie**: una línea base y re-mediciones. Una subida solo significa algo si las
dos mediciones se hicieron igual. Hoy, `comparabilidad` en `src/posiq/domain/tracking.py` (ADR
0016) declara comparables dos mediciones si coinciden:

1. la versión de la metodología;
2. la versión del score (`SCORE_VERSION`);
3. la huella del banco de prompts;
4. el conjunto de motores.

**No mira el juez.** Si la línea base se midió con reglas y la re-medición con Jev, la fuerza puede
pasar de «siempre 1» a valores entre −1 y 3. El score cambiaría sin que la marca haya hecho nada.

- **PENDIENTE (planificado para la ola 2):** añadir el juez a la regla de comparabilidad.
- **Decisión pendiente** para las mediciones reales con el tope de presupuesto de 5 €
  (`BUDGET_EUR_MAX`, `docs/estado/C.md`). Según `docs/estado/C.md`, un estudio real completo (624
  llamadas, 4 motores) cuesta unos **10,56 €** solo en motores y supera el tope. Así que, además de
  elegir juez, hay que subir el tope o reducir el estudio. Hay tres jueces posibles:
  - **Reglas en todas las mediciones:** barato y comparable, pero la fuerza es tosca.
  - **Jev con LLM de respaldo en todas:** más fino, pero más caro.
  - **Solo el LLM de respaldo (DeepSeek) en todas:** lo que ocurre si no hay clave de TypeSafe.

  **Mezclar jueces en una misma serie no vale.**

## 9. Score por motor

La misma función acepta un motor (`score_citacion(..., motor=...)`). La población se queda solo
con las ejecuciones de ese motor. `compute_metrics` calcula el score de cada marca en cada motor
(`Metrics.scores_por_motor`, en `src/posiq/domain/metrics.py`).

En el caso sintético (240 evaluaciones espontáneas, 60 por motor), la aparición espontánea de
Alborada por motor está fijada en `tests/golden/test_rigor_alborada.py`:

| Motor (respuestas atribuidas en el kit) | Aparición espontánea | Margen (IC 95 %, Wilson) |
|---|---:|---:|
| ChatGPT | 18 % | ± 12 pp |
| Claude | 15 % | ± 11 pp |
| Gemini | 57 % | ± 13 pp |
| Perplexity | 65 % | ± 13 pp |

El mismo test fija el score de Claude: **9,7 [4,2–15,7]**. Con N = 60 por motor, los márgenes son
anchos. Una diferencia pequeña entre dos motores no es concluyente. Lo que sí es claro en el caso
sintético es que, en las respuestas que el kit atribuye a ChatGPT y Claude (escritas por los
organizadores), Alborada apenas aparece; en las atribuidas a Gemini y Perplexity, sí. No dice nada
de lo que hacen los ChatGPT o Claude reales.

## 10. Qué NO es el score

- **No es cuota de mercado** ni mide ventas, pacientes o reputación general. Mide lo que dicen los
  asistentes de IA ante un banco concreto de preguntas.
- **No es un estándar externo.** Es un constructo de la metodología del kit (§7). Sus pesos (30/20/30/20)
  y la tabla de calidades son convenciones del estudio, no una ley del sector.
- **No compara bien entre bancos distintos.** Con otras preguntas, otras ciudades u otros motores
  sale otro número. Solo tiene sentido comparar con el mismo banco, los mismos motores, la misma
  versión y (pendiente, §8) el mismo juez.
- **No dice qué hacer.** El plan de acción sale de los hallazgos (`src/posiq/domain/findings.py`),
  que miran segmentos, fuentes y competidores. El score es el resumen, no el diagnóstico.

## 11. Limitaciones

- **Depende del juez** (§8). Con reglas, la fuerza no distingue recomendación de mención. Con
  cualquier juez (reglas o Jev), la calidad de fuente usa una media del catálogo cuando la mención
  se apoya en fuentes, porque nadie clasifica el tipo de fuente; Jev solo añade «Sin fuente» (0,2)
  cuando no ve apoyo.
- **Depende de la muestra.** Las respuestas de los motores varían entre repeticiones. Por eso damos
  el score con intervalo (25,9 [21,6–30,1] en el caso sintético) y no como un número exacto.
- **Comprime mucho.** Cuatro dimensiones en un número. Dos marcas con el mismo score pueden tener
  problemas distintos: una aparece poco, otra aparece mucho pero sin recomendación. Hay que mirar
  siempre los componentes.
- **La posición es relativa** a las marcas del sector que conoce el mercado del estudio. Si falta
  un competidor en el mercado, las posiciones de los demás pueden mejorar artificialmente.
- **Las calidades de fuente son fijas** por tipo. Un medio pequeño y uno grande valen lo mismo (0,9).
- **Solo prompts espontáneos.** Lo que dicen los motores cuando se les pregunta por la marca
  (asistido) se analiza aparte, en los hallazgos, y no entra en el score.
- **Sin validar en real.** El modo real nunca se ha ejecutado. La fórmula está probada, pero su
  comportamiento con respuestas reales de los motores y con el juez Jev en producción está por ver.

## Dónde se comprueba

| Qué | Fichero |
|---|---|
| Fórmula, pesos, `QUALITY_BY_TYPE`, regla de calidad sin resolver, `SCORE_VERSION`, población | `src/posiq/domain/scoring.py` |
| `ESPONTANEAS`, `peso_posicion`, escala de fuerza, `Evaluation`, `ScoreBreakdown` (None si N = 0) | `src/posiq/domain/schemas.py` |
| Juez por reglas (fuerza 1, fuente sin resolver) | `src/posiq/domain/detection.py` (`evaluation_from_detection`) |
| Juez Jev / LLM: fuerza (`STRENGTH_LEVELS`), apoyo en fuentes, nunca tipo de fuente | `src/posiq/domain/judge_questions.py` (`answers_to_evaluation`) |
| Qué juez se construye (Jev + respaldo, o solo LLM sin clave de TypeSafe) | `src/posiq/adapters/judge/__init__.py` (`build_judge`), ADR 0003 |
| Recuentos 13/227, 17/43/33, 92+1, calidad media 0,7315 (no hay assert: se obtienen ejecutando `spontaneous_population` sobre `Kit.evaluations()`) | `src/posiq/domain/scoring.py`, `tests/golden/conftest.py` |
| Score global, scores por motor, ranking | `src/posiq/domain/metrics.py` (`compute_metrics`, `_ranking`) |
| Intervalos (bootstrap del score, Wilson por motor) | `src/posiq/domain/stats.py` |
| Reglas de comparabilidad de la serie (hoy sin juez) | `src/posiq/domain/tracking.py` (`comparabilidad`) |
| Recalcular el score con otra tasa | `src/posiq/domain/scoring.py` (`score_from_profile`), `src/posiq/domain/simulation.py` |
| 25,93; componentes; 240 evaluaciones; 8.ª de 10; 25,87 con reglas | `tests/golden/test_demo_canonico.py` |
| 25,9 [21,6–30,1]; aparición por motor; Claude 9,7 [4,2–15,7] | `tests/golden/test_rigor_alborada.py` |
| Origen de las evaluaciones del kit (etiquetas + reglas) | `tests/golden/conftest.py` (`Kit.evaluations`) |
| Cobertura del kit (624 ejecuciones, 2.928 evaluaciones) | `tests/golden/test_metrics_golden.py` |
| Metodología original del score | `data/kit/03_Documentacion/02_Metodologia_GEO.md` (§6, §7, §8) |
| Columna de calidad del catálogo de fuentes | `data/kit/03_Documentacion/03_Diccionario_de_datos.md` (§6) |
| Capas del juez (reglas, Jev, fallback, persona) | `docs/adr/0003-juez-jev-con-fallback.md`, `docs/adr/0014-capa-determinista-y-no-determinista.md` |
| Rigor estadístico | `docs/adr/0008-rigor-estadistico.md` |
| Seguimiento y comparabilidad | `docs/adr/0016-seguimiento-con-metodo.md` |
| Estado del modo real y del presupuesto (≈10,56 € frente a 5 €) | `docs/estado/B.md`, `docs/estado/C.md` |

Para reproducir las cifras del caso sintético:

```sh
python -m uv run pytest tests/golden/test_demo_canonico.py tests/golden/test_rigor_alborada.py
```

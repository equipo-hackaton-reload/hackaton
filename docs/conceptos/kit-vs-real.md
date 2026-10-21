# Caso sintético (kit) frente a medición real

> **En una frase:** todo lo que enseñamos de Clínica Alborada Visión es **nuestro método aplicado
> al caso sintético del reto**. No es una medición de ninguna clínica real ni del comportamiento real
> de ChatGPT, Gemini, Perplexity o Claude. El modo real (llamar a las APIs de los asistentes) está
> construido, pero **no se ha ejecutado nunca**.

Este documento explica la diferencia, qué demuestra cada cosa y cómo hay que hablar de las cifras
en la presentación y en los entregables.

---

## 1. Dos términos que hay que distinguir

| Término | Qué es |
|---|---|
| **Kit** (o **caso sintético**) | El material que nos dieron los organizadores del reto: un brief de ejemplo, 624 respuestas ya escritas de 4 asistentes y una muestra evaluada a mano. Todo inventado. |
| **Modo kit** | posiq. ejecutado sobre el kit: en vez de preguntar a los asistentes, lee las respuestas del CSV. Gratis, sin red y siempre da las mismas cifras. |
| **Modo real** | posiq. ejecutado sobre una marca real: genera sus preguntas, las lanza a las APIs de los cuatro asistentes con búsqueda web y juzga las respuestas que vuelvan. Cuesta dinero. **Nunca se ha ejecutado.** |
| **Cifra canónica** | El Score de Citación de Alborada en el caso sintético, **25,93** (25,9 con un decimal). Está fijada en tests y no puede cambiar (ver §7). |

Otros términos que salen en este documento:

| Término | Qué es |
|---|---|
| **Score de Citación** | Nota de 0 a 100 que resume la visibilidad de una marca en las respuestas de los asistentes. Suma cuatro componentes: aparición (hasta 30), posición (hasta 20), fuerza de la recomendación (hasta 30) y calidad de la fuente (hasta 20). Fórmula en `src/posiq/domain/scoring.py`; explicada en [score-de-citacion.md](score-de-citacion.md). |
| **Pregunta espontánea** | La que **no nombra** la marca («¿qué clínica me recomiendas para operarme de miopía en Madrid?»). Mide si el asistente la conoce y la recomienda por iniciativa propia. **El score solo usa espontáneas.** |
| **Pregunta asistida** | La que **sí nombra** la marca («¿qué opinas de Clínica Alborada?»). La marca sale casi siempre porque la nombra la pregunta; sirve para ver qué se dice de ella, no si la descubren (`data/kit/03_Documentacion/02_Metodologia_GEO.md`, §8). |
| **Evaluación** | Una marca juzgada en una respuesta: ¿aparece?, ¿en qué posición?, ¿con qué fuerza?, ¿qué fuente la apoya? |
| **IC 95 %** | Intervalo de confianza del 95 %: el rango donde estaría el valor con un 95 % de seguridad si se repitiera el estudio. Explicado en [rigor-y-seguimiento.md](rigor-y-seguimiento.md). |
| **pp** | Puntos porcentuales. «18 % ± 12 pp» quiere decir entre el 6 % y el 30 %. |
| **Trace** | El registro que guarda cada llamada externa: modelo, versión del prompt, tokens y coste. |
| **ADR** | *Architecture Decision Record*: una nota corta que deja escrita una decisión de diseño y su porqué (`docs/adr/`). |
| **Test golden** | Un test que fija una cifra exacta (por ejemplo, 25,93) y falla si cambia aunque sea un céntimo. |
| **`SCORE_VERSION`** | La versión de la fórmula del score (hoy `"1.0"`, en `src/posiq/domain/scoring.py`). Si la fórmula cambia, cambia la versión. |

En los dos modos el sistema es **el mismo**: el mismo grafo, la misma fórmula y el mismo código de
métricas. Solo cambia **de dónde salen las respuestas** y **quién las juzga** (§5).

---

## 2. Qué contiene el kit, y que todo es ficticio

La guía del kit lo dice en su primera página:

> «**Todos los datos, marcas, personas y cifras son ficticios y sintéticos.** Cualquier parecido con
> entidades reales es coincidencia.» (`data/kit/00_LEEME_Guia_del_kit.md`)

Y el diccionario de datos lo concreta:

> «**Datos sintéticos.** Todas las marcas, dominios y respuestas son inventados. Reproducen la
> **estructura** y los **patrones** de un estudio real, pero no el comportamiento real de ningún
> LLM.» (`data/kit/03_Documentacion/03_Diccionario_de_datos.md`)

El propio brief de ejemplo lo repite: «Material ficticio para el hackathon… Todas las marcas, cifras
y datos son inventados» (`data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md`). Hasta la
solicitante del brief, Marta Ibarra, figura como «(ficticia)».

| Fichero (`data/kit/02_Datos/caso_oftalmologia/`) | Qué hay | Filas |
|---|---|---|
| `marcas.csv` | Las 10 clínicas del caso: Alborada (la marca foco) y 9 competidoras. **Ninguna existe.** | 10 |
| `banco_prompts.csv` | Plantillas de preguntas (descubrimiento, comparación, decisión…) | 25 |
| `ejecuciones.csv` | 624 respuestas de «ChatGPT», «Gemini», «Perplexity» y «Claude», **escritas por los organizadores**, no generadas por esos asistentes. Corresponden a 52 preguntas × 4 motores × 3 repeticiones | 624 |
| `muestra_evaluada.csv` | 15 de esas ejecuciones evaluadas a mano, marca a marca (también inventadas) | 133 |
| `fuentes_catalogo.csv` | Dominios citados con su tipo y calidad | 25 |

Detalles que delatan que es sintético:

- Las webs de las clínicas y la mayoría de fuentes acaban en **`.example`**, un dominio reservado
  que no existe. El diccionario aclara que los dominios reales que aparecen (`wikipedia.org`,
  `google.com`, `reddit.com`…) se usan «solo como **tipo de fuente genérico**: el dataset no afirma
  nada sobre ellas».
- La «fecha/hora» de cada ejecución es una «marca temporal sintética».
- La guía dice expresamente que «se puede resolver el reto **sin llamar a ninguna API**; conectar
  APIs reales es un extra».

---

## 3. Qué demuestra el kit y qué NO demuestra

### Lo que sí demuestra

| Afirmación | Cómo se comprueba |
|---|---|
| **La cadena completa funciona** de punta a punta: brief → mercado → preguntas → respuestas → juicio → métricas → plan → propuesta en Word. Ojo: en modo kit todos los pasos con LLM (intake, market, plan, write) usan `FixtureLLM`, así que **el texto del plan y de la propuesta está preescrito**; las cifras sí las calcula el dominio | `tests/e2e/test_kit_pipeline.py`, `tests/e2e/test_demo_canonica_api.py`, `tests/e2e/test_fixture_api.py` (exportación a Word) |
| **Es reproducible**: el mismo brief da siempre las mismas cifras, al céntimo | `tests/golden/test_demo_canonico.py` (25,93, no «unos 26») |
| **Cada cifra la calcula código**, no el LLM | Las fórmulas viven en `src/posiq/domain/` (sin I/O); el LLM solo recibe cifras ya calculadas (`CLAUDE.md`, §3) |
| **El plan sale de evidencias**: cada hallazgo apunta a las evaluaciones que lo justifican y cada acción a los hallazgos que resuelve | Esquema de `Finding` y `Action` en `src/posiq/domain/schemas.py`; `tests/golden/test_metrics_golden.py::test_hallazgos_con_evidencia_real` |
| **El método aplica la fórmula del reto** sin desviarse | `src/posiq/domain/scoring.py` sigue la §7 de `data/kit/03_Documentacion/02_Metodologia_GEO.md` |
| **El modo kit no cuesta nada**, haya las claves que haya | ADR 0018; `tests/e2e/test_kit_sin_coste.py` |

### Lo que NO demuestra

- **Nada sobre clínicas reales.** Alborada, Valdecruz, Oftalmos Centro y el resto no existen.
- **Nada sobre cómo se comportan de verdad los asistentes de IA.** Que «ChatGPT» mencione poco a
  Alborada en el kit (18 %) es algo que **escribieron los organizadores**, no algo que haya hecho
  ChatGPT.
- **Que el juez semántico funcione.** Jev y su LLM de respaldo no han evaluado todavía ninguna
  respuesta, ni real ni del kit, porque faltan las claves. La calibración contra las 133 etiquetas
  del kit está **PENDIENTE** (`docs/estado/B.md`, `docs/calibracion/`). En la demo juzga
  `FixtureJudge`: etiquetas del kit más reglas.
- **Que el LLM (DeepSeek) genere buenos planes o propuestas.** No se ha ejecutado nunca: falta
  `DEEPSEEK_API_KEY`. **PENDIENTE** (`docs/estado/C.md`, «Falta»). No se puede decir «la IA generó
  este plan».
- **Cuánto cuesta de verdad un estudio real.** Solo hay una estimación (§6).
- **Que el plan mejore la visibilidad.** La proyección 25,9 → 30,8 es una **simulación** del
  dominio (`src/posiq/domain/simulation.py`) sobre el caso sintético, no un resultado observado.

---

## 4. Cómo funciona el modo real, paso a paso

El grafo está en `src/posiq/application/graph.py`; cada paso es un nodo de
`src/posiq/application/nodes/`. Es **el mismo grafo** que en modo kit; la tabla dice qué cambia.

| # | Nodo | Qué hace en modo real | Qué hace en modo kit |
|---|---|---|---|
| 1 | `intake` | El LLM (DeepSeek) convierte el texto del brief en una ficha estructurada (`BriefSummary`) con el prompt `intake.v2` | Igual, pero con `FixtureLLM` (respuesta fija, sin coste) |
| 2 | `market` | El LLM propone el mercado: la marca foco, el líder y los competidores, **sin candidatos previos** | Los candidatos son las 10 marcas del kit |
| 3 | `review_competidores` | **Revisión humana**: el grafo se para hasta que una persona aprueba o edita los competidores | Igual |
| 4 | `prompts` | El LLM **genera el banco de preguntas** para esa marca y su mercado (`prompts.v1`) | Usa el banco del kit, sin LLM |
| 5 | `run` | Lanza cada pregunta a cada motor **3 veces** (`REPETICIONES_REAL = 3`) por sus APIs **con búsqueda web activada**, y guarda texto, fuentes citadas, tokens y coste. Para si se agota el presupuesto | Lee las 624 respuestas de `ejecuciones.csv` |
| 6 | `judge` | Evalúa cada marca en cada respuesta. Las **reglas** (`domain/detection.py`) deciden si la marca aparece y en qué posición. El **juez** decide la fuerza de la recomendación, el tipo de mención, el sentimiento y si la mención se apoya en las fuentes citadas (no clasifica el tipo de fuente), y nunca puede subir la aparición; si contradice a las reglas, la evaluación pasa a revisión humana (ADR 0014). Juez: Jev con fallback DeepSeek, solo DeepSeek (sin clave de TypeSafe; `src/posiq/adapters/judge/__init__.py::build_judge`) o solo reglas (`JUDGE_PROVIDER=reglas`, `src/posiq/application/nodes/judge.py`) | `FixtureJudge`: etiquetas humanas del kit donde existen; reglas en el resto |
| 7 | `analyze` | Calcula métricas y hallazgos con código puro (`domain/metrics.py`, `domain/findings.py`). Sin LLM | Igual |
| 8 | `plan` | El LLM propone el plan de acción a partir de los hallazgos; se valida contra el brief y se simula su impacto | Igual, con `FixtureLLM` |
| 9 | `review_plan` | **Revisión humana** del plan | Igual |
| 10 | `write` | El LLM redacta la propuesta (`write.v2`); las cifras las pone el código | Igual, con `FixtureLLM` |

Los motores reales están en `src/posiq/adapters/engines/` (`openai.py`, `gemini.py`,
`perplexity.py`, `anthropic.py`), descritos en el ADR 0006.

> **Estado: el modo real NO se ha ejecutado nunca.** El ADR 0006 lo dice así: «aceptado (sin probar
> en real: no hay claves de API todavía)». Los adaptadores solo están probados con respuestas
> simuladas de cada SDK. La primera prueba prevista es `scripts/smoke_engines.py` (3 preguntas ×
> motores con clave × 1 repetición) y está **PENDIENTE** (`docs/estado/B.md`).

Además, hay piezas del modo real que siguen **en desarrollo**:

- **PENDIENTE:** que la re-medición real reutilice el banco de preguntas anterior. Hoy lo regenera,
  y por eso una serie de mediciones reales saldría «no comparable» (ADR 0016).
- **PENDIENTE:** que la regla de comparabilidad de la serie tenga en cuenta **qué juez** se usó.
  Hoy solo mira la versión de la metodología, la del score, el banco y los motores
  (`src/posiq/domain/tracking.py::comparabilidad`). Si cambia el modelo de un motor, la serie sigue
  siendo comparable pero lleva un aviso; los competidores solo se comparan con el mismo mercado
  (PR #39). Ver §5.
- **PENDIENTE (riesgo conocido):** en el nodo `market`, las claves que envía el código no coinciden
  con las que espera el prompt (`brief`/`candidatos` frente a `brief_summary`/`marcas_candidatas`).
  En fixture no se nota (`docs/estado/A.md`).

---

## 5. Lo que cambia entre kit y realidad: respuestas y juez

| | **Kit (sintético)** | **Medición real** |
|---|---|---|
| Preguntas | Banco del kit (`banco_prompts.csv`) | Banco que genera posiq. para la marca real |
| Respuestas | 624 respuestas escritas por los organizadores (`ejecuciones.csv`) | Respuestas de las APIs de ChatGPT, Gemini, Perplexity y Claude con búsqueda web |
| Quién decide aparición y posición | Etiquetas humanas de `muestra_evaluada.csv` (también inventadas) donde existen; reglas en el resto | Las reglas (`domain/detection.py`) |
| Quién decide fuerza y apoyo en fuentes | Etiquetas humanas donde existen; reglas en el resto (fuerza 1, fuente sin resolver) | El juez: Jev con fallback DeepSeek, solo DeepSeek o solo reglas |
| Tipo de fuente (Ranking, Medio, Web propia…) | Resuelto solo en las etiquetas del kit | Nadie lo clasifica: media de calidad del catálogo de las fuentes citadas, o «Sin fuente» (0,2) |
| Fórmula del score | La misma | La misma |

**La fórmula no cambia.** Cambian las **respuestas** y quién las **juzga**.

Ojo con un matiz: las etiquetas humanas cubren solo 15 de las 624 ejecuciones. La cifra canónica
usa esas 133 etiquetas donde existen y **reglas en el resto**
(`tests/golden/conftest.py::Kit.evaluations`, `src/posiq/adapters/llm/fixture.py::FixtureJudge`).

**El juez cambia el resultado.** Con solo reglas, la fuerza vale siempre 1 si la marca aparece (las
reglas no distinguen «la recomiendo» de «existe») y el tipo de fuente no se resuelve. En el kit eso
mueve el score de **25,93 a 25,87**: misma aparición y posición, pero fuerza 3,92 → 3,88 y calidad de
fuente 5,67 → 5,65 (`tests/golden/test_demo_canonico.py::test_juez_por_reglas_solo_cambia_fuerza_y_fuente`).
En el kit la diferencia es pequeña porque casi todo ya iba por reglas; en una medición real juzgada
por Jev podría ser mucho mayor.

Consecuencia: **una serie temporal solo es comparable si todas sus mediciones usan el mismo juez.**
Hay que decidir uno para todas: solo reglas (barato y comparable, pero la fuerza es tosca), Jev con
fallback DeepSeek (en principio más fino, porque gradúa la fuerza; está **PENDIENTE** de calibrar,
pero más caro) o solo DeepSeek (lo que ocurre si no hay clave de TypeSafe; es otro juez distinto).
Mezclar no vale. **Decisión PENDIENTE del equipo.** Que el sistema lo compruebe solo está **PENDIENTE** (§4).

---

## 6. Por qué no se puede «medir Alborada de verdad», y qué haría falta para una medición real

### Alborada no existe

Si lanzáramos el modo real con el brief de Alborada, los asistentes responderían sobre clínicas
oftalmológicas **reales** de Madrid y Barcelona. Alborada no aparecería, porque no existe, y sus
competidores del kit tampoco. Lo esperable es un Score de Citación cercano a 0. Esa cifra no diría
nada del método: solo que la marca es inventada. (Es una consecuencia lógica, no una medición:
nunca se ha ejecutado.)

Por eso las cifras de Alborada **solo tienen sentido dentro del caso sintético**.

### Qué hace falta para una medición real

| Requisito | Detalle |
|---|---|
| **Una marca real** | Con presencia real en internet, para que los asistentes puedan citarla |
| **Su brief** | Siguiendo la plantilla del kit (`data/kit/01_Briefings/Plantilla_Brief_de_marca.md`) |
| **Claves de API** | `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY`, `ANTHROPIC_API_KEY` (motores); `DEEPSEEK_API_KEY` (LLM de los nodos); `TYPESAFE_API_KEY` si se quiere Jev. Se leen de `.env` vía `src/posiq/settings.py`, nunca del código |
| **Presupuesto** | El tope por estudio es `BUDGET_EUR_MAX` = 5 € por defecto, y un estudio del tamaño del kit cuesta más (ver abajo) |
| **Personas disponibles** | Para las dos revisiones humanas: competidores y plan |

**Coste estimado** (`src/posiq/application/estimate.py`, con los precios por defecto de
`settings.py`, para un estudio del tamaño del kit: 52 preguntas × 4 motores × 3 repeticiones = 624
llamadas):

| Juez | Motores | Juez | LLM de los nodos | **Total estimado** |
|---|---|---|---|---|
| Solo reglas (`JUDGE_PROVIDER=reglas`) | 10,56 € | 0 € | 0,02 € | **10,57 €** |
| Jev con fallback DeepSeek | 10,56 € | 0,67 € | 0,02 € | **11,25 €** |
| Solo DeepSeek | 10,56 € | 1,84 € | 0,02 € | **12,42 €** |

Las tres cifras salen de `src/posiq/application/estimate.py::estimate_study`. El total incluye
también `PlanGuard` (menos de 0,01 €), que no tiene columna propia; por eso las columnas no suman
exactamente el total. **10,56 € es solo el coste de los motores**: es la cifra que citan otros
documentos (`docs/estado/C.md`, [rigor-y-seguimiento.md](rigor-y-seguimiento.md)).

- Casi todo el coste son los **motores** (búsqueda web incluida).
- **Ninguna de las tres opciones cabe en el tope de 5 €** con un estudio del tamaño del kit: hay
  que subir el tope o reducir el estudio (menos preguntas, motores o repeticiones).
- **PENDIENTE de confirmar con una medición.** Los precios de los motores son «provisionales» (ADR
  0006) y los tokens por nodo son «una cota redondeada a partir del brief de Alborada, no una
  medición» (ADR 0018). El coste real se sabrá sumando las `Trace` del primer estudio real.
- El número de preguntas del banco real lo decide el LLM; la estimación asume las 52 del kit.

---

## 7. La cifra canónica

**Qué es.** El Score de Citación de Alborada en el caso sintético: **25,93** sobre 100 (25,9 con un
decimal), calculado sobre las 240 evaluaciones espontáneas de Alborada (60 por motor), con las
etiquetas humanas del kit donde existen y reglas en el resto.

| Componente (fórmula en `src/posiq/domain/scoring.py`) | Peso máximo | Valor |
|---|---|---|
| Aparición | 30 | 11,62 |
| Posición | 20 | 4,72 |
| Fuerza de la recomendación | 30 | 3,92 |
| Calidad de la fuente | 20 | 5,67 |
| **Score de Citación** | 100 | **25,93** |

**Dónde se fija.** En dos tests que fallan si cambia un solo céntimo:

- `tests/golden/test_demo_canonico.py`: el dominio da 25,93, puesto 8 de 10 y proyección 30,8.
- `tests/e2e/test_demo_canonica_api.py`: la API en modo kit (lo que se ve en la demo) da lo mismo.

Otros tests golden (`test_rigor_alborada.py`, `test_source_map_golden.py`,
`test_serie_alborada.py`, `test_scenarios_golden.py`, `test_competitor_gap_golden.py`) vuelven a
comprobar que sus módulos no la alteran.

**Por qué no puede cambiar.** La deck, el plan B (`docs/plan-b.md`), el Word de ejemplo y estos
documentos usan la misma cifra. Si un cambio de código la moviera sin querer, la demo diría una
cosa y la deck otra. Fijarla en un test convierte cualquier cambio en un fallo visible. Si alguna vez
hubiera que cambiarla (por ejemplo, una nueva versión del score), sería una decisión explícita: nueva
`SCORE_VERSION`, ADR y actualización de deck y documentos a la vez.

**Por qué 25,93 y no 25,87.** Las dos son nuestro método sobre el caso sintético. La canónica usa
las etiquetas humanas del kit porque son la referencia del reto; 25,87 es lo que da el juez por
reglas puro. Con un decimal coinciden: 25,9.

---

## 8. Regla para la presentación y los entregables

> **Toda cifra de Alborada se presenta como resultado de nuestro método sobre el caso sintético del
> reto. Nunca como un dato sobre una clínica o sobre un asistente real.**

Basta con marcarlo una vez por diapositiva o por sección (por ejemplo, un rótulo «Caso sintético
del reto»), y siempre que una frase pueda leerse como un hecho del mundo real.

| ✗ Incorrecto | ✓ Correcto |
|---|---|
| «Alborada tiene un 25,9 en ChatGPT.» | «Sobre el caso sintético del reto, nuestro método da a Alborada un Score de Citación de 25,9 sobre 100.» |
| «Alborada es la 8.ª clínica más visible en IA.» | «En el caso sintético, Alborada queda 8.ª de las 10 marcas del estudio.» |
| «ChatGPT solo menciona a Alborada en el 18 % de las respuestas.» | «En las respuestas sintéticas atribuidas a ChatGPT, Alborada aparece en el 18 % de las respuestas espontáneas (60 respuestas).» |
| «Con nuestro plan, Alborada sube a 30,8.» | «Nuestra simulación proyecta que, en el caso sintético, el plan llevaría el score de 25,9 a 30,8 (rango 27,8–34,0).» |
| «Hemos medido 624 respuestas de los asistentes.» | «Hemos procesado las 624 respuestas sintéticas del kit.» |
| «posiq. mide la visibilidad real en ChatGPT, Gemini, Perplexity y Claude.» (sin matiz) | «posiq. está preparado para medir con las APIs reales; esa medición todavía no se ha ejecutado. Hoy lo demostramos sobre el caso sintético.» |
| «Un estudio real cuesta 10,57 €.» | «Estimamos unos 10–12 € por estudio del tamaño del kit; está pendiente de confirmar con la primera medición real.» |
| «Oftalmos Centro es un competidor que la clínica no tenía en el radar.» | «En el caso sintético, Oftalmos Centro supera a Alborada por 13,1 puntos sin estar entre sus competidores declarados.» |

Palabras que solo se pueden usar con el matiz: «mide», «medición», «la IA dice», «ChatGPT
recomienda», «resultado». Palabras seguras: «nuestro método da», «en el caso sintético», «el kit»,
«simulación», «proyección», «estimación».

Si el jurado pregunta «¿y con una clínica real?», la respuesta honesta es: el modo real está
construido y probado con respuestas simuladas de cada API, pero no se ha ejecutado; haría falta una
marca real, las claves y unos 10–12 € por estudio (estimado).

---

## 9. Cifras del caso sintético que se usan en la demo

Todas son **nuestro método aplicado al caso sintético del reto**. Ninguna describe una clínica ni
un asistente real.

### Score y posición

| Cifra | Qué significa | Test que la fija |
|---|---|---|
| **25,93** (25,9) | Score de Citación de Alborada (0–100), solo preguntas espontáneas (ver §1 y [score-de-citacion.md](score-de-citacion.md)) | `tests/golden/test_demo_canonico.py::test_score_canonico`; `tests/e2e/test_demo_canonica_api.py` |
| 11,62 / 4,72 / 3,92 / 5,67 | Componentes: aparición, posición, fuerza, calidad de fuente | `tests/golden/test_demo_canonico.py::test_score_canonico` |
| 240 | Evaluaciones espontáneas de Alborada en las que se basa el score | `tests/golden/test_demo_canonico.py::test_score_canonico` |
| **8.ª de 10** | Puesto de Alborada entre las 10 marcas del kit | `tests/golden/test_demo_canonico.py::test_posicion_8_de_10` |
| 25,87 | El mismo score si todo se juzga por reglas | `tests/golden/test_demo_canonico.py::test_juez_por_reglas_solo_cambia_fuerza_y_fuente` |
| 66,46 | Score del líder, Grupo Hospitalario Valdecruz | `tests/golden/test_competitor_gap_golden.py` |
| 40,53 | Distancia de Alborada al líder (hallazgo `F-brecha-lider`), IC 95 % [35,34; 45,56] (intervalo de confianza del 95 %: el rango donde estaría la distancia con un 95 % de seguridad) | `tests/golden/test_rigor_alborada.py::test_significancia_de_los_hallazgos` |
| 624 / 2.928 | Ejecuciones del kit / evaluaciones marca × ejecución | `tests/golden/test_metrics_golden.py::test_cobertura` |

### Margen de error (rigor estadístico, ADR 0008)

Cómo se calculan los intervalos y qué significan: [rigor-y-seguimiento.md](rigor-y-seguimiento.md).

| Cifra | Qué significa | Test que la fija |
|---|---|---|
| **25,9 [21,6–30,1]** | Score con su intervalo de confianza del 95 % (bootstrap: se remuestrean las respuestas muchas veces para ver cuánto variaría) | `tests/golden/test_rigor_alborada.py::test_ic_del_score_contiene_la_cifra_canonica` |
| [19,7–31,8] | El mismo intervalo remuestreando preguntas enteras (más prudente, más ancho) | `tests/golden/test_rigor_alborada.py::test_ic_del_score_por_prompt_es_mas_ancho` |
| 39 % [33–45 %] | Aparición espontánea global de Alborada | `tests/golden/test_rigor_alborada.py::test_aparicion_global_y_por_ciudad` |
| **18 %** ± 12 pp | Aparición espontánea en las respuestas atribuidas a ChatGPT (n = 60) | `tests/golden/test_rigor_alborada.py::test_aparicion_por_motor` |
| 15 % ± 11 pp / 57 % ± 13 pp / 65 % ± 13 pp | Lo mismo en Claude, Gemini y Perplexity | `tests/golden/test_rigor_alborada.py::test_aparicion_por_motor` |
| 4 % [1–20 %] | Aparición espontánea en preguntas sobre Barcelona | `tests/golden/test_rigor_alborada.py::test_aparicion_global_y_por_ciudad` |
| 6 de 7 | Hallazgos con contraste estadístico, todos significativos; `F-fuente-lider` no admite contraste | `tests/golden/test_rigor_alborada.py::test_significancia_de_los_hallazgos` |

### Competidores (ADR 0012)

| Cifra | Qué significa | Test que la fija |
|---|---|---|
| Valdecruz 1.º (66,5), Tramuntana 2.º (47,2), Láser Nítida 4.º (37,0) | Los competidores que declara el brief y su puesto | `tests/golden/test_competitor_gap_golden.py` |
| **Oftalmos Centro**, 3.º, +13,1 puntos | Competidor no declarado en el brief que supera a Alborada por más margen (hallazgo `F-competidor-no-declarado`) | `tests/golden/test_competitor_gap_golden.py` |

### Fuentes (ADR 0010)

| Cifra | Qué significa | Test que la fija |
|---|---|---|
| **5,9 %** | Parte de las citas que acompañan a Alborada que son su propia web (33 de 564), frente al 3,3 % de media de sus competidores | `tests/golden/test_source_map_golden.py::test_web_propia_de_alborada` |
| 11,3 % | Cuota de las webs propias en conjunto entre las fuentes del sector entero (la primera del top 5) | `tests/golden/test_source_map_golden.py::test_top_5_fuentes_del_sector` |
| 12,4 % | Cuota de todas las webs propias dentro de las 564 citas de las respuestas donde aparece Alborada (es la cifra del texto del hallazgo, en la propuesta y el Word). No confundir con el 11,3 % del sector entero | `tests/golden/test_source_map_golden.py::test_web_propia_de_alborada` |
| wikipedia.org (Media), comparaclinicas (Baja), rankingclinicas (Baja) | Las 3 fuentes con más oportunidad para Alborada | `tests/golden/test_source_map_golden.py::test_top_3_oportunidades_de_alborada` |

### Exactitud de lo que se dice de la marca (ADR 0011)

| Cifra | Qué significa | Test que la fija |
|---|---|---|
| 276 | Afirmaciones sobre Alborada extraídas de las respuestas | `tests/golden/test_accuracy_golden.py::test_alborada_cero_inexactitudes` |
| **0 inexactitudes** | Ninguna afirmación contradice el brief | `tests/golden/test_accuracy_golden.py::test_alborada_cero_inexactitudes` |
| 62 / 193 / 21 | Correctas / no verificables con el brief / a revisar por la clínica (todas por «la opción más recomendada / recomendable») | `tests/golden/test_accuracy_golden.py` |

### Plan, proyección y escenarios (ADR 0009)

| Cifra | Qué significa | Test que la fija |
|---|---|---|
| **25,9 → 30,8** (rango 27,8–34,0) | Proyección simulada del score tras la fase 3 del plan completo | `tests/golden/test_demo_canonico.py::test_proyeccion_del_plan`; `tests/e2e/test_demo_canonica_api.py` |
| **27,7** (27,67) | Escenario «mínimo viable»: 3 acciones, esfuerzo 5, deja 2 hallazgos sin cubrir | `tests/golden/test_scenarios_golden.py::test_minimo_viable` |
| **28,2** (28,20) | Escenario «equilibrado»: 4 acciones, esfuerzo 7, cubre todos los hallazgos | `tests/golden/test_scenarios_golden.py::test_equilibrado` |
| **30,8** (30,77) | Escenario «completo»: las 9 acciones, esfuerzo 16 (igual que la proyección) | `tests/golden/test_scenarios_golden.py::test_completo_reproduce_la_simulacion_canonica` |
| 22.000 € | Coste del plan de ejemplo, dentro del máximo del brief (27.000 €) | `tests/golden/test_brief_coverage_golden.py::test_plan_de_ejemplo_sin_enlaces` |
| 16 | Puntos del brief que la propuesta debe tratar | `tests/golden/test_brief_coverage_golden.py::test_puntos_del_brief_de_alborada` |

### Seguimiento en el tiempo (ADR 0016)

| Cifra | Qué significa | Test que la fija |
|---|---|---|
| −8,59 (media de competidores 34,52) | Distancia de Alborada a la media del resto del mercado | `tests/golden/test_serie_alborada.py::test_punto_del_kit_mantiene_las_cifras_canonicas` |
| 0 cambios significativos | Medir el kit dos veces da exactamente lo mismo: el sistema no inventa noticias | `tests/golden/test_serie_alborada.py::test_misma_medicion_dos_veces_sin_cambios` |
| +15,88 [+9,51; +22,47], del 8.º al 3.er puesto | Lo que detecta si se **perturba a propósito** el segundo punto (40 no-apariciones pasan a 1.ª posición). Es una prueba del método, doblemente sintética | `tests/golden/test_serie_alborada.py::test_segundo_punto_perturbado_detecta_el_cambio` |

> Nota: la re-medición en modo kit siempre da diferencia 0, porque lee las mismas respuestas. Mide
> que el sistema es repetible, **no** que la marca haya mejorado (`docs/estado/C.md`).

---

## Dónde se comprueba

**Que el kit es ficticio**

- `data/kit/00_LEEME_Guia_del_kit.md`
- `data/kit/03_Documentacion/03_Diccionario_de_datos.md`
- `data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md`

**Fórmula y método**

- `data/kit/03_Documentacion/02_Metodologia_GEO.md` (§7, fórmula del reto)
- `src/posiq/domain/scoring.py` (Score de Citación)
- `src/posiq/domain/metrics.py`, `findings.py`, `stats.py`, `simulation.py`, `scenarios.py`,
  `source_map.py`, `accuracy.py`, `competitor_gap.py`, `brief_coverage.py`, `tracking.py`

**Modo real y modo kit**

- `src/posiq/application/graph.py` y `src/posiq/application/nodes/`
- `src/posiq/adapters/engines/` (motores reales y del kit)
- `src/posiq/adapters/llm/fixture.py` (`FixtureLLM`, `FixtureJudge`)
- `src/posiq/application/estimate.py` (coste estimado)
- ADR 0006 (motores reales, sin probar), ADR 0014 (juez), ADR 0016 (serie y comparabilidad),
  ADR 0018 (modo kit gratis y estimación)
- `docs/estado/A.md`, `B.md`, `C.md` (qué está en develop y qué falta)

**Cifras de la demo**

- `tests/golden/test_demo_canonico.py` (cifra canónica, puesto, juez por reglas, proyección)
- `tests/e2e/test_demo_canonica_api.py` (la API en modo kit muestra lo mismo)
- `tests/golden/test_rigor_alborada.py`, `test_competitor_gap_golden.py`,
  `test_source_map_golden.py`, `test_accuracy_golden.py`, `test_scenarios_golden.py`,
  `test_brief_coverage_golden.py`, `test_serie_alborada.py`, `test_metrics_golden.py`
- `tests/e2e/test_kit_pipeline.py`, `tests/e2e/test_kit_sin_coste.py`
- `docs/plan-b.md` (cifras de la deck)

Para comprobarlo todo de una vez:

```sh
python -m uv run pytest tests/golden tests/e2e
```

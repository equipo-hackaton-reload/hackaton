# Propuesta de valor y modelo de negocio de posiq.

> **Cómo leer este documento.** Hay dos tipos de afirmación y no se mezclan:
>
> - **Caso sintético del reto.** Todo el kit es ficticio: «Todos los datos, marcas, personas y
>   cifras son ficticios y sintéticos» (`data/kit/00_LEEME_Guia_del_kit.md`). Clínica Alborada
>   Visión y sus competidores no existen. Las 624 respuestas de los motores las escribieron los
>   organizadores y los dominios acaban en `.example`. **Cada cifra de Alborada que aparece aquí es
>   «nuestro método aplicado al caso sintético del reto»**, no una medición de ningún mercado.
> - **Medición real.** Es el mismo método con respuestas de las APIs reales de ChatGPT, Gemini,
>   Perplexity y Claude. **Todavía no se ha ejecutado nunca.** Nada de lo que sigue dice lo contrario.
>
> Lo que aún no está en `develop` va marcado **En desarrollo** o **PENDIENTE**.

---

## 1. La propuesta en una frase

> **«posiq. no vende un score; vende un seguimiento con método. Partimos de una línea base. Cada
> trimestre volvemos a medir con el mismo banco y la misma versión de los motores. Solo informamos
> de los cambios que salen del margen de error, comparados con tus competidores. Y entre mediciones
> vigilamos lo que la IA dice de ti y re-priorizamos el plan.»**

> **Ojo: esta frase es la propuesta que vendemos, no lo que el producto ya hace entero.** Hoy está
> hecho en el dominio el cálculo de la serie, la comparabilidad y la significancia de los cambios.
> La medición trimestral programada, la vigilancia entre mediciones y la re-priorización automática
> están **PENDIENTES**, y que la re-medición reutilice el mismo banco de preguntas está **En
> desarrollo** (ver §7). Ante el jurado, dila en futuro: «volveremos a medir…».

Y el relato que la acompaña:

> **La propuesta promete; el seguimiento demuestra, con significancia, si se cumplió.**

La primera medición termina en una propuesta con un plan de acción y una proyección del score.
Esa proyección es una **hipótesis**, no una predicción. El seguimiento es lo que la pone a prueba:
se vuelve a medir con el mismo método y solo se da por bueno un cambio si sale del margen de error.

Por qué no basta con un score suelto: un número como «25,93» no dice si es bueno, si es estable ni
si ha cambiado de verdad respecto al mes pasado. La propia metodología del kit avisa de que las
palancas de GEO «son hipótesis de la industria, no garantías: los modelos cambian y ninguna acción
asegura resultados. Por eso todo plan debe incluir re-medición»
(`data/kit/03_Documentacion/02_Metodologia_GEO.md`).

---

## 2. Términos que hay que conocer

| Término | Qué significa en posiq. |
|---|---|
| **Motor** | Un asistente de IA al que se pregunta: ChatGPT, Gemini, Perplexity o Claude. |
| **Banco de prompts** | La lista fija de preguntas que se hacen a los motores (p. ej. «¿qué clínica me recomiendas para operarme de miopía en Madrid?»). |
| **Ejecución** | Una pregunta del banco lanzada a un motor una vez. Cada pregunta se repite varias veces por motor porque las respuestas varían. |
| **Juez** | Lo que lee cada respuesta y decide con qué fuerza se recomienda la marca, cómo la menciona y si la mención se apoya en las fuentes citadas. Si la marca aparece y en qué posición lo deciden siempre las reglas (ADR 0014). Puede ser Jev (con DeepSeek de respaldo), solo DeepSeek (sin clave de TypeSafe) o solo reglas. En el caso sintético se usan las etiquetas humanas del kit donde existen (`FixtureJudge`, 133 filas de `muestra_evaluada.csv`) y reglas en el resto. Jev aún no ha juzgado ninguna respuesta real. |
| **Score de Citación** | Cifra de 0 a 100 que resume la visibilidad de una marca en las respuestas espontáneas (las que no nombran la marca). Suma cuatro componentes: aparición (hasta 30), posición (hasta 20), fuerza de la recomendación (hasta 30) y calidad de la fuente (hasta 20). Fórmula en `src/posiq/domain/scoring.py`. |
| **Línea base** | La primera medición de una marca. Es el punto de partida con el que se compara todo lo demás. |
| **Re-medición** | Volver a medir la misma marca, más tarde, con el mismo método. |
| **Margen de error (intervalo de confianza, IC)** | El rango donde está razonablemente el valor real, dado que solo vemos una muestra de respuestas. Se da al 95 %. «25,9 [21,6–30,1]» quiere decir: medimos 25,9 y, por el azar de las respuestas, el valor podría estar entre 21,6 y 30,1. |
| **Cambio significativo** | Un cambio cuyo intervalo al 95 % no incluye el 0. Si lo incluye, el cambio puede ser ruido y no se anuncia. |
| **Comparable** | Dos mediciones son comparables si se hicieron con el mismo método: misma metodología, misma versión del score, mismo banco de preguntas y mismos motores. |
| **Indicador adelantado** | Una cifra que se mueve antes que el score, por ejemplo cuántas citas van a la web propia de la marca. Sirve para ver progreso entre mediciones. |

---

## 3. Cómo funciona el seguimiento, paso a paso

### Paso 1 · Línea base

Se hace un estudio completo: brief → mercado y competidores → banco de preguntas → respuestas de
los motores → juez → métricas → hallazgos → plan → propuesta. Ese primer estudio es la línea base.

**Ejemplo (caso sintético del reto):** Alborada tiene un Score de Citación de **25,93**, es la
**8.ª de 10** marcas y su intervalo es **25,9 [21,6–30,1]** (`tests/golden/test_demo_canonico.py`,
`tests/golden/test_rigor_alborada.py`). Desglose del score:

| Componente | Valor (caso sintético) |
|---|---|
| Aparición | 11,62 |
| Posición | 4,72 |
| Fuerza | 3,92 |
| Calidad de la fuente | 5,67 |
| **Score** | **25,93** |

### Paso 2 · Re-medición con el mismo método

La propuesta es repetir la medición cada trimestre (hoy se lanza a mano con
`POST /studies/{id}/remeasure`; programarla está **PENDIENTE**). Para que dos mediciones se puedan comparar, el sistema
comprueba cuatro cosas (`src/posiq/domain/tracking.py`, función `comparabilidad`):

| Si cambia… | Qué hace posiq. |
|---|---|
| La versión de la metodología | **No comparable.** Dice por qué y no calcula ningún cambio. |
| La versión de la fórmula del score | **No comparable.** |
| El banco de preguntas (se compara su «huella», un resumen SHA-256 de lo que se pregunta) | **No comparable.** |
| El conjunto de motores | **No comparable.** |
| El modelo concreto de un motor (p. ej. el proveedor actualiza ChatGPT) | **Comparable con aviso:** «parte del cambio puede deberse al modelo». |
| Las marcas del mercado (entra o sale un competidor) | El score y la aparición se comparan. El puesto y la diferencia con los competidores **no**, porque dependen de quién esté en el mercado. |

Por qué importa la última regla: sin ella, una marca con el mismo score (25,93 → 25,93) pasaba del
8.ª de 10 a 2.ª de 4 y salía como cambio real. Se corrigió en la PR #39 (ADR 0016).

### Paso 3 · Solo los cambios que salen del margen de error

Entre dos mediciones comparables se calculan estos cambios, cada uno con su intervalo
(`src/posiq/domain/tracking.py`, `construir_serie`; métodos en `src/posiq/domain/stats.py`):

| Cambio | Cómo se decide si es real |
|---|---|
| Score | Bootstrap: se recalcula el score miles de veces remuestreando las respuestas (2.000 réplicas, semilla fija) |
| Aparición espontánea, global y por motor | Método de Newcombe para la diferencia de dos porcentajes |
| Puesto en el ranking | Bootstrap del puesto |
| Diferencia con la media de los competidores | Bootstrap de «score de la marca − media del resto del mercado» |

Solo los cambios significativos llegan al resumen. Si no hay ninguno, el resumen dice
exactamente **«Sin cambios fuera del margen de error»**.

**Ejemplos (caso sintético del reto, `tests/golden/test_serie_alborada.py`):**

- **El kit medido dos veces.** Las dos mediciones dan lo mismo: los 8 cambios valen 0 y el
  resumen es «Sin cambios fuera del margen de error». Esto es lo que debe pasar: repetir una
  medición no produce titulares.
- **Un segundo punto inventado para la prueba.** Se cambian a mano 40 respuestas en las que
  Alborada no aparecía para que aparezca la 1.ª y recomendada. El score sube de 25,93 a 41,81:
  **+15,88 con IC [+9,51; +22,47]**, y el puesto pasa del 8.º al 3.º (punto inventado). Es significativo. En cambio,
  Gemini y Perplexity suben 10 puntos porcentuales pero **quedan dentro del margen** y no se
  anuncian. Este punto no es una medición: es un dato sintético para comprobar que el sistema
  distingue señal de ruido.

### Paso 4 · Siempre frente a los competidores

Un cambio de la marca solo se entiende al lado del mercado. Por eso la serie da también el puesto
y la diferencia con la media de los competidores, con su significancia.

**Ejemplo (caso sintético):** media de los competidores 34,52; diferencia de Alborada −8,59
(`tests/golden/test_serie_alborada.py`).

Además, posiq. compara los competidores que **declara** el cliente con los que **pone la IA**
(`src/posiq/domain/competitor_gap.py`, ADR 0012). **Caso sintético:** Alborada no declara a
Oftalmos Centro, que es 3.ª con 13,1 puntos de ventaja; eso genera un hallazgo de impacto alto
(`tests/golden/test_competitor_gap_golden.py`).

### Paso 5 · Entre mediciones: vigilar y re-priorizar

Hoy existen, como cálculo, los **indicadores adelantados** (uno por medición; si faltan datos el
valor queda vacío, nunca se inventa):

| Indicador | Qué mide | Caso sintético |
|---|---|---|
| Cuota de la web propia | Fracción de las citas que van a la web de la marca | 5,9 % (33 de 564 citas) |
| Presencia en las 5 fuentes principales | De las respuestas donde sale la marca, cuántas citan alguna de las 5 fuentes **ganadas** más citadas en el mercado de este estudio. Una fuente ganada es cualquier fuente que no es la web de una marca del mercado (`presencia_top_fuentes` en `tracking.py`; `propiedad` en `src/posiq/domain/source_map_schemas.py`) | 74,1 % |
| Inexactitudes | Afirmaciones de la IA sobre la marca que contradicen el brief | 0 |
| A revisar | Afirmaciones con expresiones de riesgo en publicidad sanitaria (p. ej. «la opción más recomendable») | 21 |

Fuentes: `src/posiq/domain/tracking.py`, `tests/golden/test_serie_alborada.py`,
`tests/golden/test_source_map_golden.py`, `tests/golden/test_accuracy_golden.py`.

Y la **re-priorización** se apoya en los escenarios del plan (`src/posiq/domain/scenarios.py`,
ADR 0009): con un presupuesto, una capacidad de equipo o unas prioridades distintas, el sistema
dice qué acciones se mantienen, cuáles se aplazan y por qué, y vuelve a simular el score.

**Ejemplo (caso sintético, `tests/golden/test_scenarios_golden.py`):** score final esperado de
cada preajuste, partiendo de 25,93.

| Preajuste | Acciones | Score final esperado | Hallazgos sin cubrir |
|---|---|---|---|
| Mínimo viable | 3 | 27,7 | 2 |
| Equilibrado | 4 | 28,2 | 0 |
| Completo | 9 | 30,8 | 0 |

Estas proyecciones usan una tabla de supuestos de impacto por tipo de acción
(`src/posiq/domain/simulation.py`, ADR 0007). Son estimaciones, no predicciones.

**Qué falta aquí:** la vigilancia **entre** mediciones (lanzar comprobaciones periódicas sin hacer
un estudio completo y avisar al cliente) y la re-priorización automática del plan cuando cambian
los indicadores están **PENDIENTES**. Hoy los indicadores se calculan cuando hay una medición, y
los escenarios los pide quien usa el sistema.

---

## 4. Modelo de negocio

El modelo tiene dos piezas. Es una **hipótesis** (como dice la plantilla del kit, «precio pendiente
de validación», `data/kit/03_Documentacion/07_Plan_de_proyecto_BMC_y_tres_niveles.md`). No damos
precios ni tamaños de mercado: no los hemos medido.

### 4.1 Estudio inicial: la puerta de entrada

- Qué recibe el cliente: la línea base (score con su margen de error, puesto frente a los
  competidores, por motor, fase y ciudad), los hallazgos con sus evidencias, un plan de acción
  enlazado a esos hallazgos, la proyección del plan y una propuesta exportable: en Word siempre, y
  en PDF si el servidor tiene LibreOffice (sin él, la API responde 503;
  `src/posiq/interfaces/api/main.py`).
- La propuesta empieza recogiendo **lo que pidió el cliente**: cada objetivo, ciudad, servicio,
  restricción y presupuesto del brief, y dónde se trata en el plan, con «pendiente» si no se trata
  (`src/posiq/domain/brief_coverage.py`, ADR 0013).
- Su papel comercial: demuestra el método y deja planteada la pregunta que vende el seguimiento:
  «¿se cumplirá lo que proyecta el plan?».

### 4.2 Suscripción de re-mediciones

- Qué recibe el cliente: una re-medición cada trimestre con el mismo banco y los mismos motores, un
  informe que solo destaca los cambios significativos frente a los competidores, los indicadores
  adelantados y el plan re-priorizado.
- El propio plan del caso sintético ya incluye esta pieza como acción: «Re-medición trimestral con
  el mismo banco, motores y repeticiones, comparada con la línea base»
  (`src/posiq/adapters/llm/_fixture_data.py`, acción A3-1).

### 4.3 Por qué el cliente seguiría pagando

| Lo que no tiene sin posiq. | Lo que le da el seguimiento |
|---|---|
| Un número que sube o baja sin saber si es ruido | Solo cambios fuera del margen de error |
| Sin referencia | Siempre comparado con sus competidores y con la media del mercado |
| Un plan fijo que envejece | Plan re-priorizado con escenarios (presupuesto, equipo, prioridades) |
| No sabe qué dice la IA de su marca | Vigilancia de exactitud: afirmaciones incorrectas y expresiones de riesgo |
| No sabe dónde se informan los motores en su sector | Mapa de fuentes del sector, anonimizado (benchmark) |

### 4.4 El coste de cada medición

- **Caso sintético del reto: 0 €.** El modo kit no llama a ningún servicio de pago, aunque haya
  claves configuradas, salvo que se active a propósito con `KIT_IA_REAL=true`, que viene
  desactivado por defecto (ADR 0018, `kit_ia_real` en `src/posiq/settings.py`,
  `tests/e2e/test_kit_sin_coste.py`).
- **Medición real: coste PENDIENTE.** Existe una estimación previa (`GET /estimate`,
  `src/posiq/application/estimate.py`), pero sus tokens por llamada son una cota redondeada, no una
  medición. El coste real se conocerá con las trazas del primer estudio real. El tope por estudio
  es de 5 € por defecto (`budget_eur_max` en `src/posiq/settings.py`) y es configurable.
- **La estimación supera el tope.** Para un estudio del tamaño del kit (624 llamadas a los
  motores, 4 motores) la estimación previa da 10,57 € con el juez por reglas, 11,25 € con Jev y
  fallback DeepSeek, y 12,42 € con DeepSeek como juez. Casi todo (10,56 €) son los motores, con su
  búsqueda web. Las tres opciones superan el tope de 5 €: antes de la primera medición real hay
  que subir el tope o reducir el estudio. Es una estimación, no una medición
  (`docs/conceptos/kit-vs-real.md` §6, `docs/estado/C.md`, `src/posiq/application/estimate.py`).
- Toda llamada de pago deja una traza con modelo, versión del prompt, tokens y coste, también si
  la llamada falla (ADR 0018). Esto es lo que permitirá calcular el margen de la suscripción.

---

## 5. Las cinco críticas y cómo responde el producto

### 1 · Atribución: «¿Cómo sé que el cambio lo ha causado vuestro plan?»

- **Respuesta:** no lo afirmamos. Comparamos la marca **con sus competidores** medidos en las
  mismas condiciones: si todo el mercado sube, la diferencia con la media no cambia. Y si el
  proveedor cambia el modelo de un motor entre mediciones, la serie lo avisa: «parte del cambio
  puede deberse al modelo».
- **Límite honesto:** esto separa la marca del mercado, pero no prueba causalidad. El kit lo dice:
  «Dos capturas durante el hackathon demuestran el mecanismo de seguimiento, no un efecto causal
  de acciones de marketing» (`data/kit/03_Documentacion/07_Plan_de_proyecto_BMC_y_tres_niveles.md`).
- **Estado:** cálculo hecho en el dominio (`tracking.py`, #35 y #39).

### 2 · Ruido: «Los asistentes responden distinto cada vez.»

- **Respuesta:** cada cifra lleva su intervalo al 95 % y solo se anuncian los cambios
  significativos. Repetir la misma medición da «Sin cambios fuera del margen de error».
- **Ejemplo (caso sintético):** en las respuestas sintéticas atribuidas a ChatGPT, Alborada aparece
  en el **18 %** de las espontáneas, con un margen de **± 12 puntos** (`tests/golden/test_rigor_alborada.py`). Con 60
  ejecuciones por motor, una diferencia de unos pocos puntos es ruido.
- **Estado:** cálculo hecho en el dominio (`stats.py`, #28; `tracking.py`, #35).

### 3 · Comparabilidad: «¿Cómo sé que comparo manzanas con manzanas?»

- **Respuesta:** cada medición guarda su versión de la metodología, su versión del score, la
  huella del banco de preguntas, los motores, los modelos de cada motor y las marcas del mercado.
  Si algo de lo esencial cambia, la serie dice «no comparable» y por qué, en vez de dar un cambio.
- **Hueco conocido (PENDIENTE):** la comparabilidad **todavía no mira qué juez se usó**. Y el juez
  cambia el resultado. En el caso sintético, con las etiquetas humanas del kit donde existen (133
  filas) y reglas en el resto, el score es 25,93; todo por reglas, 25,87. Las reglas ponen siempre
  fuerza 1 (no distinguen «la recomiendo» de «existe») y no clasifican el tipo de fuente: la fuerza
  pasa de 3,92 a 3,88 y la calidad de la fuente de 5,67 a 5,65; aparición, posición y ranking no
  cambian (`tests/golden/test_demo_canonico.py`, `test_juez_por_reglas_solo_cambia_fuerza_y_fuente`).
  En una medición real la diferencia puede ser mayor. Regla: **una serie solo es comparable si
  todas sus mediciones usan el mismo juez.** Hay que añadirlo a la comparabilidad y decidir, para
  las mediciones reales, si todas van con reglas (fuerza tosca), todas con Jev y fallback DeepSeek
  (mejor) o todas solo con DeepSeek. Mezclar no vale. El coste casi no decide: según la estimación, el juez mueve el total de 10,57 € a 11,25 €,
  porque casi todo son los motores (§4.4).
- **Otro hueco (En desarrollo):** en `develop`, `POST /studies/{id}/remeasure` vuelve a generar el
  banco de preguntas. En una medición real, si las preguntas cambian, la serie dirá, con razón, «no
  comparable». La re-medición real debe reutilizar el banco anterior (ADR 0016). La rama
  `feature/C-diferencial-grafo` lo hace, pero aún no está fusionada.

### 4 · Latencia: «La IA tarda meses en reflejar cambios; ¿qué hago mientras?»

- **Respuesta:** cadencia trimestral para el score, e **indicadores adelantados** que se mueven
  antes: cuota de la web propia, presencia en las fuentes principales del mercado, inexactitudes y
  afirmaciones a revisar.
- **Estado:** los indicadores se calculan en el dominio (#35). La medición programada cada
  trimestre y la vigilancia entre mediciones están **PENDIENTES**.

### 5 · Valor: «¿Qué paga exactamente el cliente después del primer estudio?»

- **Respuesta:** no paga por un número. Paga por tres cosas:
  1. **Plan re-priorizado con escenarios:** qué hacer con el presupuesto y el equipo que tiene, con
     el motivo de cada acción aplazada (ADR 0009, #25).
  2. **Vigilancia de exactitud:** qué afirma la IA de su marca, qué es incorrecto y qué expresiones
     son de riesgo en un sector regulado, con acciones de mitigación (ADR 0011, #27).
  3. **Benchmark del sector:** qué fuentes citan los motores en su sector, anonimizado (una fuente
     solo entra si la citan respuestas sobre al menos 2 marcas, y las webs propias se agregan),
     y sus oportunidades de fuente (ADR 0010, #26).
- **Estado:** los tres cálculos existen en el dominio con tests. Mostrarlos en la API y en la web
  está **En desarrollo** (ver §6).

---

## 6. Qué hace HOY el producto

Comprobado en la rama `develop` (punta `1eec259`). La columna «Dónde se ve» distingue entre lo
que solo existe como cálculo probado (**dominio**) y lo que ya llega a la API o a la web.

| Capacidad | PR | Dónde se ve hoy | Comprobación |
|---|---|---|---|
| Estudio completo del brief a la propuesta (Word y PDF), con revisiones humanas de competidores y plan | anteriores a #20 | API y web | `tests/e2e/` |
| Score de Citación, ranking y 7 hallazgos con evidencias | anteriores | API y web | `tests/golden/test_demo_canonico.py` (score y puesto), `tests/golden/test_fixtures_alborada.py` (7 hallazgos) |
| Simulación del plan: proyección (hipótesis con supuestos de impacto, ADR 0007) de 25,9 a 30,8 en el caso sintético | #11 | API y web | `tests/golden/test_demo_canonico.py` |
| Re-medición: crea un estudio nuevo y da el delta con el anterior | #14, #20 | API y web | `src/posiq/interfaces/api/main.py`, `apps/web/src/api/hooks.ts` |
| Cuentas por usuario: registro, verificación por código, login con token; cada estudio solo lo ve su dueño | #36 | API | `tests/interfaces/test_auth_api.py`, `tests/application/test_accounts.py` |
| Serie temporal: comparabilidad, cambios significativos, competidores, indicadores adelantados | #35, #39 | dominio | `tests/golden/test_serie_alborada.py`, `tests/domain/test_tracking.py` |
| Rigor estadístico: intervalos (Wilson, bootstrap) y significancia de hallazgos y re-mediciones | #28 | dominio (la API tiene el hueco `rigor`, hoy vacío) | `tests/golden/test_rigor_alborada.py` |
| Escenarios del plan con tres preajustes | #25 | dominio (hueco `escenarios` en la API) | `tests/golden/test_scenarios_golden.py` |
| Mapa de fuentes del sector y oportunidades por marca | #26 | dominio | `tests/golden/test_source_map_golden.py` |
| Exactitud de marca y riesgo regulatorio | #27 | dominio | `tests/golden/test_accuracy_golden.py` |
| Competidores declarados frente a los que pone la IA | #30 | dominio | `tests/golden/test_competitor_gap_golden.py` |
| Encargo del brief y su cobertura en la propuesta y el Word | #29, #32, #34 | API y Word | `tests/golden/test_brief_coverage_golden.py` |
| Modo kit sin coste y trazas de lo pagado aunque falle | #37 | API | `tests/e2e/test_kit_sin_coste.py` |

**Importante para la presentación:** «dominio» quiere decir que la cifra se calcula con código
determinista y probado, pero **aún no sale en la pantalla**. Los campos `rigor`, `escenarios`,
`oportunidades_fuente`, `exactitud` y `mitigaciones` ya existen en `GET /studies/{id}`, pero hoy
llegan vacíos (`null`) porque el grafo todavía no los rellena (`src/posiq/application/state.py`,
`src/posiq/interfaces/api/schemas.py`).

---

## 7. Qué está en desarrollo o falta

| Pieza | Estado |
|---|---|
| API de seguimiento: `GET /brands`, `GET /brands/{id}/serie`, coste previo de una re-medición | **PENDIENTE**: es la siguiente tarea de la zona C (`docs/estado/C.md`) |
| Vista de seguimiento en la web (serie, cambios significativos, indicadores) | **En desarrollo** (rama `feature/D-cuentas-seguimiento`, sin fusionar; depende de la API de seguimiento) |
| Rellenar en el grafo los bloques de rigor, escenarios, fuentes, exactitud y competidores | **En desarrollo** (rama `feature/C-diferencial-grafo`, sin fusionar) |
| Re-medición que reutiliza el banco de preguntas anterior | **En desarrollo** (ADR 0016; rama `feature/C-diferencial-grafo`, sin fusionar) |
| Juez como condición de comparabilidad | **PENDIENTE**: ninguna rama lo implementa todavía |
| Auditoría técnica de la web del cliente (si los motores pueden leer la web: robots.txt, JSON-LD, sitemap…) | **En desarrollo**: solo el contrato y su ADR 0019 están en `develop` (PR #40); el análisis, el descargador y su conexión al grafo no existen |
| Medición programada (cada trimestre, sin intervención) y vigilancia entre mediciones | **PENDIENTE** |
| Proveedor de correo (hoy el código de verificación se escribe en el log del servidor) | **PENDIENTE** (ADR 0015) |
| Multi-organización (equipos y agencias con varias marcas y varios usuarios) | Posible ampliación de producto, sin ADR ni diseño. Hoy cada estudio es de un solo usuario (ADR 0015) |
| Coste real por medición | **PENDIENTE**: no se ha hecho ninguna medición real |
| Consenso del juez (varias pasadas y voto por mayoría) activado en el grafo | **PENDIENTE**: existe `ConsensusJudge`, pero no se usa porque multiplica el coste del juez (ADR 0008) |

---

## 8. Riesgos y límites

1. **Todo lo medido es sintético.** Las cifras de Alborada ilustran el método; no dicen nada de
   ningún mercado real.
2. **El modo real nunca se ha ejecutado.** No sabemos aún cuánto cuesta ni cuánto tarda una
   medición real, ni cómo de distintas serán las respuestas reales de las del kit.
3. **El juez cambia el resultado** (25,93 frente a 25,87 en el caso sintético; por qué, en §5, crítica 3).
   Mezclar jueces en una serie la invalida; la comparabilidad aún no lo comprueba.
4. **Los motores cambian sin avisar.** Podemos registrar el modelo y avisar, pero no congelarlo.
   «La misma versión de los motores» es el objetivo; cuando no se cumple, la serie lo dice.
5. **Los márgenes son algo optimistas.** Suponen que cada ejecución es independiente, y las
   repeticiones de una misma pregunta se parecen. Remuestreando preguntas enteras, el IC del score
   del caso sintético pasa de [21,6–30,1] a [19,7–31,8], y la caída del embudo deja de ser
   significativa (ADR 0008).
6. **Los intervalos no cubren el error del juez**, solo el azar de las respuestas.
7. **Sin causalidad.** Comparar con los competidores reduce el ruido del mercado, pero no prueba
   que el plan causara el cambio.
8. **Benchmark con un solo estudio.** Con un único estudio del sector, el mapa de fuentes resume
   solo ese mercado; la anonimización de un cliente concreto necesita varios estudios (ADR 0010).
9. **Las proyecciones son supuestos.** La tabla de impacto por tipo de acción no está calibrada con
   datos reales de efecto (ADR 0007).
10. **Cuentas básicas.** Sin correo real, sin recuperación de contraseña y con el límite de
    intentos en memoria del proceso (ADR 0015).

---

## 9. Cómo contarlo mañana

| Decir | No decir |
|---|---|
| «Con el caso sintético del reto, nuestro método da 25,9 con un margen de 21,6 a 30,1.» | «Alborada tiene un 25,9.» |
| «El sistema ya calcula la serie y solo anuncia cambios significativos; lo hemos probado con el kit medido dos veces.» | «Hemos medido una mejora.» |
| «La medición real está preparada pero no se ha ejecutado.» | «Hemos medido ChatGPT de verdad.» |
| «La proyección del plan es una hipótesis; el seguimiento la contrasta.» | «El plan sube el score a 30,8.» |
| «El coste real por medición está pendiente; el kit cuesta 0 €.» | Cualquier precio o coste real inventado. |

---

## Dónde se comprueba

**Código del dominio**

- `src/posiq/domain/scoring.py`: fórmula del Score de Citación.
- `src/posiq/domain/stats.py`, `src/posiq/domain/stats_schemas.py`: intervalos y significancia.
- `src/posiq/domain/tracking.py`, `src/posiq/domain/tracking_schemas.py`: serie, comparabilidad,
  cambios e indicadores adelantados.
- `src/posiq/domain/scenarios.py`, `src/posiq/domain/simulation.py`: escenarios y proyección.
- `src/posiq/domain/source_map.py`: mapa de fuentes y web propia.
- `src/posiq/domain/accuracy.py`: exactitud de marca.
- `src/posiq/domain/competitor_gap.py`: competidores declarados frente a los de la IA.
- `src/posiq/domain/brief_coverage.py`: encargo y cobertura del brief.

**Aplicación y API**

- `src/posiq/interfaces/api/main.py`, `src/posiq/interfaces/api/auth.py`: rutas disponibles.
- `src/posiq/application/state.py`, `src/posiq/interfaces/api/schemas.py`: bloques del
  diferencial (hoy vacíos).
- `src/posiq/application/estimate.py`, `src/posiq/settings.py`: estimación de coste y tope.
- `src/posiq/application/runner.py`: re-medición.

**Tests**

- `tests/golden/test_demo_canonico.py`: 25,93, 8.ª de 10, desglose, 25,87 con reglas, 25,9 → 30,8.
- `tests/golden/test_fixtures_alborada.py`: 7 hallazgos y plan en 4 fases.
- `tests/golden/test_rigor_alborada.py`: 25,9 [21,6–30,1], 18 % de ChatGPT con ± 12 pp.
- `tests/golden/test_serie_alborada.py`: «Sin cambios fuera del margen de error», +15,88
  [+9,51; +22,47], indicadores adelantados.
- `tests/golden/test_scenarios_golden.py`: 27,7 / 28,2 / 30,8.
- `tests/golden/test_source_map_golden.py`: 33 de 564 citas (5,9 %).
- `tests/golden/test_accuracy_golden.py`: 276 afirmaciones, 0 inexactitudes, 21 a revisar.
- `tests/golden/test_competitor_gap_golden.py`: Oftalmos Centro, 3.ª, +13,1.
- `tests/golden/test_brief_coverage_golden.py`: cobertura del brief.
- `tests/e2e/test_kit_sin_coste.py`: el modo kit no gasta.
- `tests/domain/test_tracking.py`, `tests/interfaces/test_auth_api.py`,
  `tests/application/test_accounts.py`, `tests/application/test_estimate.py`.

**Decisiones (ADR)**

- `docs/adr/0007-simulacion-y-calidad.md`, `0008-rigor-estadistico.md`,
  `0009-escenarios-del-plan.md`, `0010-mapa-de-fuentes.md`, `0011-exactitud-de-marca.md`,
  `0012-competidores-declarados.md`, `0013-trazabilidad-brief-propuesta.md`,
  `0015-cuentas-y-propiedad.md`, `0016-seguimiento-con-metodo.md`,
  `0018-coste-del-modo-kit-y-trazas-de-fallo.md`.

**Kit del reto**

- `data/kit/00_LEEME_Guia_del_kit.md`: el kit es ficticio.
- `data/kit/03_Documentacion/02_Metodologia_GEO.md`: palancas como hipótesis y necesidad de
  re-medir.
- `data/kit/03_Documentacion/07_Plan_de_proyecto_BMC_y_tres_niveles.md`: hipótesis de ingresos y
  límite causal de dos capturas.

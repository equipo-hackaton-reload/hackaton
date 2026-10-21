# La propuesta GEO que recibe el cliente

Este documento explica, sección a sección, la propuesta que entrega posiq. a una marca. Para cada
sección dice qué contiene, de qué módulo sale, qué comprueba el código y qué redacta la IA. También
dice qué está ya en el Word, qué solo está en la API y qué todavía no existe.

Está pensado para el equipo (presentación y entregables) y para el jurado.

---

## 0. Antes de leer: dos reglas

### Regla 1. Caso sintético frente a medición real

**Todo el kit del reto es ficticio.** Lo dice la guía del kit (`data/kit/00_LEEME_Guia_del_kit.md`):
«Todos los datos, marcas, personas y cifras son ficticios y sintéticos».

- Clínica Alborada Visión y sus competidores **no existen**. Sus webs son dominios `.example`.
- Las **624 respuestas** de los motores **las escribieron los organizadores** del reto. No las
  generó ChatGPT, ni Gemini, ni Perplexity, ni Claude.
- Por eso, **toda cifra de Alborada** de este documento (25,93; 8.ª de 10; 25,9 [21,6–30,1]; 18 %
  en ChatGPT; Oftalmos Centro; 5,9 % de web propia; 0 inexactitudes; 25,9 → 30,8; escenarios
  27,7 / 28,2 / 30,8…) es **nuestro método aplicado al caso sintético del reto**. Ilustra cómo
  funciona posiq. No dice nada del mercado real.
- **El modo real** (preguntar de verdad a las APIs de los cuatro motores) está programado, pero
  **no se ha ejecutado nunca**. Ninguna cifra de este documento sale de una medición real.

En este documento, los ejemplos de Alborada van marcados con **[Caso sintético]**.

### Regla 2. Qué existe hoy y qué no

Cada bloque lleva una de estas etiquetas, comprobadas en el código de la rama `develop`:

| Etiqueta | Significa |
|---|---|
| **En el Word** | Sale en el documento Word que se descarga (`adapters/export/`) |
| **En la API** | Lo devuelve `GET /studies/{id}`, pero el Word no lo pinta |
| **Calculado, sin conectar** | La función existe en `domain/` y tiene tests, pero el grafo no la llama todavía |
| **En desarrollo (PR #N)** | Hay una PR abierta que lo conecta o lo crea. Aún no está en `develop` |
| **PENDIENTE** | No hay código. Es diseño o trabajo futuro |

---

## 1. Cómo se construye la propuesta: el código calcula, la IA redacta

La propuesta es un objeto `Proposal` (`src/posiq/domain/schemas.py`). La monta el nodo `write`
(`src/posiq/application/nodes/write.py`), que es el último paso del grafo.

El reparto es estricto:

| Lo pone el **código** (determinista, comprobable) | Lo redacta la **IA** (`ProposalDraft`, `application/schemas_draft.py`) |
|---|---|
| Métricas, Score de Citación, ranking, tablas de visibilidad | `resumen_ejecutivo` |
| Hallazgos (`domain/findings.py`), con su cifra y sus evidencias | `contexto_alcance` (un párrafo) |
| Plan, objetivos y presupuesto del plan: **lo propone un LLM, lo valida el código y lo aprueba una persona**; el código lo copia tal cual (ver el matiz más abajo) | `diagnostico` y la interpretación de cada hallazgo |
| Encargo literal del brief y su cobertura (`domain/brief_coverage.py`) | `competencia` |
| Contexto: marca, sector, motores, fecha, origen de los datos | `estrategia` y `prioridades` |
| Limitaciones obligatorias (datos sintéticos, juez por reglas, puntos sin tratar) | `riesgos` (riesgo y mitigación) y `supuestos` |
| Hitos, responsabilidades y presupuesto de la hoja de ruta | `hoja_ruta` (texto de seguimiento) |
| | `cobertura_brief`: qué acciones o hallazgos tratan cada punto del brief (el código lo valida) |

Tres reglas del proyecto (`CLAUDE.md`) sostienen este reparto:

- **Toda cifra la calcula `domain/`.** La IA recibe las cifras ya calculadas y no puede cambiarlas:
  `assemble_proposal` toma las métricas, los hallazgos y el plan del estado, no del texto de la IA.
- **Nunca hay texto libre entre nodos.** Toda llamada a un LLM devuelve un modelo Pydantic validado.
- **El texto de los motores es DATO.** Nunca se mete en las instrucciones del LLM.

**Matiz importante sobre el plan.** El plan (fases, acciones, objetivos y presupuesto) lo propone
un LLM en el nodo `plan` (`prompt plan.v1`) y **lo revisa y aprueba una persona** antes de
redactar la propuesta. El código comprueba que cada acción apunte a hallazgos que existen, que
declare todas las restricciones del brief y que el presupuesto no supere el máximo del brief
(`validate_plan_against_brief` en `schemas.py`, `plan_violations` en `nodes/plan.py`). **No
comprueba** que el «valor actual» de cada objetivo coincida con la métrica: eso lo pide el prompt
y lo revisa la persona. **PENDIENTE**: validarlo en código.

**En la demo sin claves** (`LLM_PROVIDER=fixture`), los textos y el plan no los escribe ninguna IA.
El plan de Alborada de la demo lo escribió una persona a mano
(`src/posiq/adapters/llm/_fixture_data.py`, `example_plan`) y el resumen ejecutivo empieza con
«DEMO SIN IA: textos y plan de ejemplo, datos sintéticos.» (`adapters/llm/fixture.py`).

---

## 2. Mapa de la propuesta

El Word tiene **11 secciones**: las 10 del formato del reto (`data/kit/03_Documentacion/06_Formato_del_entregable.md`)
más «Lo que nos habéis pedido», añadida en 2.º lugar (ADR 0013). El orden está en
`SECCIONES` de `src/posiq/adapters/export/template.py`.

| # | Sección | Estado |
|---|---|---|
| — | Portada (con aviso de datos sintéticos) | En el Word |
| 1 | Resumen ejecutivo | En el Word |
| 2 | Lo que nos habéis pedido | En el Word |
| 3 | Contexto y alcance | En el Word |
| 4 | Diagnóstico de visibilidad | En el Word (sin márgenes de error) |
| 4b | Márgenes de error (rigor estadístico) | Calculado, sin conectar · En desarrollo (PR #43) |
| 5 | Análisis de la competencia: ranking y brecha de fuentes con el líder | En el Word |
| 5b | Competidores declarados frente a los que pone la IA | Calculado, sin conectar · En desarrollo (PR #43) |
| 5c | Mapa de fuentes del sector y oportunidades | Calculado, sin conectar · En desarrollo (PR #43) |
| 5d | Web propia | Calculado, sin conectar |
| 6 | Hallazgos clave | En el Word |
| 6b | Exactitud de marca y mitigación | Calculado, sin conectar · En desarrollo (PR #43) |
| 6c | Auditoría técnica de la web | En desarrollo: solo el contrato está en `develop` (PR #40). Sin análisis ni descargas |
| 7 | Estrategia recomendada | En el Word |
| 8 | Plan de acción por fases (palancas) | En el Word |
| 8b | Escenarios del plan | Calculado, sin conectar · En desarrollo (PR #43) |
| 8c | Simulación del impacto | En la API y en la web. **No en el Word** |
| 9 | Medición y seguimiento | En el Word (versión básica) |
| 9b | Serie temporal de seguimiento | Calculado, sin conectar. Endpoints PENDIENTES |
| 10 | Riesgos y supuestos | En el Word |
| 11 | Hoja de ruta y presupuesto | En el Word |

Lo marcado «b, c, d» no está en el Word. En la API, situación en `develop`:

- Los campos `rigor`, `escenarios`, `oportunidades_fuente`, `exactitud` y `mitigaciones` **ya
  existen** en `StudyDetail` (`src/posiq/interfaces/api/schemas.py`) y hoy valen `null`. La PR #43
  los rellena.
- El bloque `competidores` (5b) **no existe** en `develop`: lo añade la PR #43 como campo nuevo.
- La web propia (5d) **no tiene campo** en la API.

Aunque la PR #43 entre, todo esto **seguirá sin estar en el Word** hasta que alguien lo añada a la
plantilla (zona E, la parte del equipo que lleva el Word y la documentación). **PENDIENTE**.

---

## 3. Sección a sección

### Portada

- **Qué contiene:** título, marca, sector, fecha y, si los datos son sintéticos, un aviso
  destacado: «Datos sintéticos del kit del reto: reproducen la estructura de un estudio real, no
  el comportamiento real de los motores.»
- **De dónde sale:** `AVISO_SINTETICO` en `adapters/export/docx.py`. Se muestra si
  `Contexto.datos_sinteticos` es verdadero, y eso lo fija el código cuando el estudio es en modo kit
  (`contexto()` en `nodes/write.py`).
- **Qué redacta la IA:** nada.
- **Marca de la agencia:** cabecera, color, logo y pie se pueden personalizar
  (`adapters/export/branding.py`, `AgencyBrandKit`).

### 1. Resumen ejecutivo — En el Word

- **Qué contiene:** en una página, dónde está la marca, qué se está perdiendo y qué se propone.
- **Qué redacta la IA:** todo el texto (`ProposalDraft.resumen_ejecutivo`, prompt `write.v2`).
- **Qué verifica el código:** solo que exista. Las cifras que cite deben venir de las que recibe,
  pero el código no relee el texto.

### 2. Lo que nos habéis pedido (encargo) — En el Word

Responde a la pregunta «¿habéis entendido lo que pedíamos?».

- **Qué contiene:**
  - Las listas **literales** del brief: objetivos, restricciones, servicios prioritarios,
    ciudades, públicos, competidores declarados y presupuesto. Sin reescribir.
  - Una tabla «Dónde se trata cada punto»: punto, lo que pedisteis, dónde se trata (acciones o
    hallazgos) y estado (**Cubierto** o **Pendiente**).
- **De dónde sale:** `domain/brief_coverage.py` (`puntos_del_brief`, `evaluar_cobertura`,
  `carencias`). Modelos `Encargo` y `PuntoBrief` en `schemas.py`. ADR 0013.
- **Qué hace la IA:** propone enlaces punto → acciones o hallazgos (`cobertura_brief`). Nada más.
- **Qué verifica el código:**
  - Cada punto tiene un id estable: `objetivo-1`, `restriccion-2`, `servicio-1`, `ciudad-2`,
    `publico-3`, `competidor-1`, `presupuesto`.
  - Objetivos, servicios, ciudades, públicos y competidores están **cubiertos** si tienen al menos
    un enlace a una acción o un hallazgo que exista. Los ids inventados se descartan.
  - Las **restricciones** están cubiertas solo si **todas** las acciones del plan las declaran. Lo
    que diga la IA no cuenta aquí: la prueba es el plan.
  - El **presupuesto** está cubierto si el presupuesto del plan no supera el máximo del brief.
  - Si falta algo, `write` reintenta una vez con las carencias. Lo que siga pendiente se declara en
    las limitaciones: «Puntos del brief sin tratar en esta propuesta: …».
  - El esquema rechaza un punto «cubierto» sin enlaces (salvo restricciones y presupuesto) y
    cualquier enlace a ids que no existen.
- **Límite:** «cubierto» significa que se trata, no que se trate bien. La calidad la juzga la
  revisión humana.
- **[Caso sintético]:** sin enlaces de la IA, solo quedan cubiertas las 2 restricciones y el
  presupuesto («Plan de 22.000 €, dentro del máximo de 27.000 €»): 13 de 16 puntos pendientes. Con
  los enlaces del caso golden, 16 de 16 (`tests/golden/test_brief_coverage_golden.py`).

### 3. Contexto y alcance — En el Word

- **Qué contiene:** ficha con marca, sector, motores analizados, fecha, origen de los datos («Kit
  del reto (datos grabados)» o «APIs de los motores»), «Datos sintéticos: Sí/No», id del estudio y
  la lista de **limitaciones**.
- **Qué pone el código en las limitaciones** (`nodes/write.py`), siempre que aplique:
  - En modo kit: «Datos sintéticos del kit del reto (ejecuciones grabadas), no mediciones reales de
    los motores.»
  - Si el juez fue solo por reglas: «Menciones evaluadas solo por reglas (aparición y posición),
    sin juez LLM: el tipo de mención, el sentimiento y la fuerza de la recomendación no se han
    juzgado.»
  - Los puntos del brief sin tratar.
- **Qué redacta la IA:** los `supuestos` y el párrafo `contexto_alcance`, que se añaden a la lista.

### 4. Diagnóstico de visibilidad — En el Word

Es el corazón del estudio: **¿los asistentes de IA nombran a la marca cuando alguien pregunta sin
nombrarla?**

#### Conceptos que hay que saber explicar

- **Visibilidad espontánea:** la pregunta no nombra la marca («¿qué clínica me recomiendas para
  operarme de miopía en Madrid?»). Es la que importa: dice si el motor **descubre** la marca.
- **Visibilidad asistida:** la pregunta nombra la marca («¿qué opinas de Clínica Alborada
  Visión?»). Solo dice si el motor la **conoce**. Se presenta aparte y **nunca se mezcla** con la
  espontánea (metodología del kit, §8).
- **Tasa de aparición:** de cada 100 respuestas, en cuántas sale la marca. Se da en % (0,18 = 18 %).
- **pp (puntos porcentuales):** la diferencia entre dos tasas. De 18 % a 28 % son **+10 pp** (no
  «+10 %»). Se usa en los hallazgos (§6) y en la simulación (§8c).
- **Embudo:** las cuatro fases de la decisión del paciente: **descubrimiento** (qué opciones hay),
  **comparación**, **validación** (¿es de fiar?) y **decisión**. Cada pregunta del banco pertenece a
  una fase (metodología del kit).
- **Score de Citación (0-100):** resume la visibilidad espontánea. Fórmula en
  `src/posiq/domain/scoring.py` (versión `1.0`):

| Componente | Máx. | Cálculo (sobre N evaluaciones espontáneas de la marca) |
|---|---|---|
| Aparición | 30 | 30 × tasa de aparición |
| Posición | 20 | 20 × media del peso de posición / 3. Peso: 1.ª = 3 · 2.ª-3.ª = 2 · 4.ª o más = 1 · no aparece = 0 |
| Fuerza de la recomendación | 30 | 30 × media de la fuerza / 3. Fuerza: 3 principal · 2 positiva secundaria · 1 neutra · 0 no aparece · −1 con advertencia. Si la media es negativa, vale 0 |
| Calidad de la fuente | 20 | 20 × tasa × calidad media de la fuente de cada aparición. Ranking/institución 1,0 · Medio 0,9 · Web propia 0,7 · Directorio 0,6 · Reseñas 0,6 · Red social/foro 0,4 · Sin fuente 0,2 |

Si no hay evaluaciones (N = 0), no hay score: el Word escribe «s. d.» (sin datos), nunca 0.

#### Qué contiene en el Word

- Texto del diagnóstico (IA) seguido de la interpretación de cada hallazgo (IA).
- Ficha con el score global y sus cuatro componentes, el número de evaluaciones y la versión del
  score.
- Tablas de visibilidad **espontánea** por motor, por fase del embudo, por ciudad y por perfil, con
  la columna del líder para comparar.
- Visibilidad **asistida** en tabla aparte: «referencia, no comparable».
- Calidad de las menciones: tipo de mención, fuerza media, menciones negativas y menciones «por
  desconocimiento» (el motor la nombra para decir que no la conoce).
- Fuentes que acompañan a la marca: dominio, tipo, calidad y apariciones.

**De dónde sale:** `domain/metrics.py` (`compute_metrics`) y `domain/scoring.py`. El Word solo
formatea (`docx.build_context`: redondeo, porcentaje, coma decimal). No calcula nada.

**[Caso sintético]** (`tests/golden/test_demo_canonico.py`, 240 evaluaciones espontáneas de
Alborada):

| Componente | Valor |
|---|---|
| Aparición | 11,62 |
| Posición | 4,72 |
| Fuerza | 3,92 |
| Calidad de fuente | 5,67 |
| **Score de Citación** | **25,93** (8.ª de 10 marcas) |

#### Quién decide «aparece», «posición», «fuerza» y «fuente»: el juez

Esto cambia el resultado y hay que saber explicarlo.

- **Reglas** (`domain/detection.py`): deciden aparición y posición buscando el nombre y los alias
  en el texto. Son deterministas.
- **Juez Jev** (modelo de TypeSafe, versión fijada `jev-1.13`) con **fallback LLM** («plan B»: si
  Jev no responde o duda, decide otro LLM): deciden tipo de mención, fuerza, sentimiento y si la mención se apoya en las fuentes citadas (no clasifican el tipo de fuente).
  Si Jev contradice a las reglas sobre la aparición, la evaluación va a **revisión humana** y la
  aparición se queda la de las reglas (ADR 0014). **Estado:** diseñado y programado, pero **en el
  caso sintético no se ha usado** (la cifra canónica sale de las etiquetas del kit y de las reglas)
  y **no se ha ejecutado nunca con una clave real**.
- **Solo reglas** (`JUDGE_PROVIDER=reglas`): más barato, pero la fuerza vale siempre 1 y el tipo
  de fuente no se resuelve.
- **[Caso sintético]:** la cifra canónica 25,93 sale de las **etiquetas de `muestra_evaluada.csv`**
  (también inventadas por los organizadores) **donde existen**, y de las **reglas en el resto** de
  evaluaciones, que son la mayoría (`tests/golden/conftest.py`, `Kit.evaluations`: «etiquetas
  humanas de la muestra donde existen; detección por reglas en el resto»; ADR 0008, §Límites). Con
  solo reglas, sale **25,87**
  (fuerza 3,88 y calidad 5,65; aparición, posición y ranking iguales). Con un decimal, las dos dan
  25,9 (`tests/golden/test_demo_canonico.py`).

#### 4b. Márgenes de error — Calculado, sin conectar · En desarrollo (PR #43)

Una cifra sin margen puede ser ruido. posiq. calcula el margen de cada cifra (ADR 0008,
`domain/stats.py`):

| Qué | Método | En palabras |
|---|---|---|
| Tasa de aparición de un segmento | Intervalo de **Wilson** al 95 % | Una fórmula estándar para el margen de una tasa; funciona bien con tasas pequeñas (1 de 24) |
| Score de Citación | **Bootstrap**: se remuestrean las ejecuciones 2.000 veces (semilla fija 20261021) y se recalcula el score con la misma fórmula | «Remuestrear» = sacar al azar, con repetición, otra muestra del mismo tamaño y ver cuánto se mueve el score. Con semilla fija da siempre el mismo intervalo para el mismo estudio |
| Diferencia de dos tasas | Método de **Newcombe** (combina los dos intervalos de Wilson) | El margen de «tasa A − tasa B» |
| Diferencia de scores de dos marcas | **Bootstrap emparejado** | Como el bootstrap, pero cada muestra al azar se usa para las dos marcas a la vez, porque las dos se evalúan en las mismas respuestas |

- **Significativo** quiere decir que el intervalo al 95 % no contiene el 0. No se dan p-valores.
- **[Caso sintético]** (`tests/golden/test_rigor_alborada.py`): score **25,9 [21,6–30,1]**.
  Aparición espontánea en ChatGPT **18 % [11–30 %]**, Claude 15 %, Gemini 57 %, Perplexity 65 %.
  Barcelona 4 % [1–20 %].
- **Límites que hay que decir** (ADR 0008): las repeticiones de un mismo prompt se parecen, así
  que los intervalos son algo optimistas. Remuestreando por prompt, el intervalo del score pasa a
  [19,7–31,8] y la caída del embudo deja de ser significativa (solo 4 prompts de decisión). Los
  intervalos no cubren el error del juez.
- **Estado:** las funciones están en `develop`. La PR #43 las conecta al grafo y a la API (bloque
  `rigor`). **No están en el Word** (PENDIENTE): hoy el Word da el score sin intervalo (en el caso
  sintético, 25,9).

### 5. Análisis de la competencia

#### Lo que ya está en el Word

- Texto de la IA (`ProposalDraft.competencia`).
- **Ranking por Score de Citación** de todas las marcas del mercado, con su número de evaluaciones
  (`Metrics.ranking`, `Metrics.scores`).
- **Brecha de fuentes frente al líder** (`Metrics.brecha_fuentes`, `metrics._source_gap`): dominios
  que acompañan al líder más que a la marca, en respuestas espontáneas. Columnas: con líder, con la
  marca, brecha y «líder sin la marca».
- **[Caso sintético]:** Alborada 25,93, 8.ª de 10. El líder es Valdecruz (66,46), a 40,53 puntos.
  directoriomedico.example aparece en **37 respuestas espontáneas en las que sale el líder y
  Alborada no** (acompaña al líder 60 veces y a Alborada 25). Es el hallazgo `F-fuente-lider`
  (`domain/findings.py`, columna «líder sin la marca»).

#### 5b. Competidores declarados frente a los que pone la IA — Calculado, sin conectar · En desarrollo (PR #43)

Responde a «creías que tu rival era X, pero la IA te compara con Y» (ADR 0012,
`domain/competitor_gap.py`).

- **Qué hace el código:**
  1. Busca cada competidor del brief en el mercado medido (por nombre o alias, sin tildes ni
     mayúsculas). Si el nombre es ambiguo, lo deja en `no_resueltos`.
  2. Los ordena por lo medido: puesto, score, ventaja sobre la marca y tasa espontánea.
  3. Saca dos hallazgos posibles:
     - `F-competidor-no-declarado`: una marca que el cliente no declaró va por delante con
       **≥ 5 puntos** de ventaja. Impacto L si son ≥ 10.
     - `F-declarado-poco-visible`: un competidor declarado con tasa espontánea por debajo de
       max(10 %, la mitad de la tasa de la marca). Impacto S.
- **Qué redacta la IA:** nada en este bloque.
- **[Caso sintético]** (`tests/golden/test_competitor_gap_golden.py`): de los tres declarados por
  Alborada, Valdecruz es 1.º, Tramuntana 2.º y Láser Nítida 4.º. **Oftalmos Centro**, que Alborada
  no declara, es 3.º con **13,1 puntos** de ventaja: hallazgo de impacto L. Cervantes, Santa
  Eulalia y Vistalia también van por delante, pero por menos de 2 puntos.
- **Estado:** la PR #43 lo expone en la API como bloque `competidores`. Sus hallazgos **no** se
  suman a los 7 de la propuesta. No está en el Word (PENDIENTE).

#### 5c. Mapa de fuentes del sector y oportunidades — Calculado, sin conectar · En desarrollo (PR #43)

¿Qué fuentes citan los motores en este sector y en cuáles aparece la marca menos que sus
competidores? (ADR 0010, `domain/source_map.py`).

- **Cita:** un dominio en las fuentes de una respuesta (una vez por respuesta).
- **Mapa del sector:** cuota de citas de cada fuente, por motor, por fase y por ciudad.
  Anonimizado: una fuente solo entra si la citan respuestas sobre al menos 2 marcas, y todas las
  webs propias se suman en una sola entrada «(webs propias)».
- **Oportunidad de fuente:** en respuestas espontáneas, compara cuántas veces la fuente acompaña a
  la marca y cuántas a la media de sus competidores. `valor` = cuota de la fuente en el sector ×
  brecha. Puntuación fija: **Alta** ≥ 0,005 · **Media** ≥ 0,002 · **Baja** por debajo.
- **[Caso sintético]** (`tests/golden/test_source_map_golden.py`): top del sector: webs propias
  11,3 %, directoriomedico 8,6 %, diariosalud 8,5 %. Mejor oportunidad de Alborada:
  **wikipedia.org (Media)**. Lectura: las fuentes que acompañan a Alborada son casi las de sus
  competidores; su problema es que **aparece menos**, no con qué fuentes aparece.
- **Estado:** la PR #43 lo expone como `oportunidades_fuente` (con un solo estudio). El mapa
  entre varios estudios del sector necesita `StudyRepo.list_by_sector` (PENDIENTE). No está en el
  Word.

#### 5d. Web propia — Calculado, sin conectar

- **Cifra:** de todas las citas de las respuestas en las que aparece la marca, qué fracción va a su
  propia web. Se compara con la media de sus competidores (`source_map.hallazgo_web_propia`).
- **Impacto:** L si es menos de la mitad de la media de los competidores, M si es menor que la
  media, S si no.
- **[Caso sintético]:** alboradavision.example recibe **33 de 564 citas (5,9 %)**, frente al 3,3 %
  de media de sus competidores. Impacto S: su web no es el problema.
- **Estado:** genera el hallazgo `F-web-propia`, que va **fuera** de los 7 hallazgos de la
  propuesta. Ningún nodo lo llama hoy. Es también un indicador de la serie de seguimiento (9b).

### 6. Hallazgos clave — En el Word

- **Qué contiene:** entre 3 y 7 hallazgos (lo exige el esquema `Proposal`). Cada uno con título,
  descripción, cifra, origen de la cifra, fase del embudo, impacto (S/M/L), confianza y número de
  evaluaciones que lo respaldan.
- **De dónde sale:** `domain/findings.py` (`detect_findings`). Ocho reglas explícitas, todas sobre
  visibilidad espontánea salvo donde se indica en la tabla:

| Regla | Se dispara si… | Impacto |
|---|---|---|
| `caida_embudo` | la tasa cae ≥ 10 pp de una fase a otra posterior | L ≥ 25 pp · M ≥ 15 pp · S |
| `motor_debil` | diferencia entre el mejor y el peor motor ≥ 20 pp | L ≥ 40 pp · M ≥ 25 pp · S |
| `fuente_lider` | un dominio sale en ≥ 3 respuestas con el líder y sin la marca | L si es ranking o medio · M |
| `ciudad_baja` | una ciudad del brief < 30 % o < mitad de la tasa global | L < 10 % · M |
| `brecha_lider` | el líder saca ≥ 15 puntos de score | L ≥ 30 · M |
| `asistida_vs_espontanea` | asistida − espontánea ≥ 30 pp (**usa también la asistida**) | M |
| `recomendacion_debil` | fuerza media < 1,5 con ≥ 5 apariciones | M |
| `menciones_negativas` | al menos una mención con advertencia o por desconocimiento (**cuenta espontáneo y asistido**) | M ≥ 3 · S |

- **Confianza:** depende del tamaño de la muestra. n ≥ 60 → 0,8 · n ≥ 20 → 0,65 · resto → 0,45.
- **Qué verifica el código:** cada hallazgo lleva `evaluation_ids` (al menos uno), las
  evaluaciones reales que respaldan la cifra. Se pueden consultar con
  `GET /studies/{id}/evaluations?ids=`.
- **Qué redacta la IA:** una interpretación por hallazgo (`interpretacion_hallazgos`). El código
  exige que interprete **exactamente** los hallazgos del estudio, ni uno más ni uno menos.
- **[Caso sintético]** (`detect_findings` sobre el kit, `tests/golden/test_fixtures_alborada.py`).
  Las diferencias de tasas se guardan en tanto por uno (`unidad = fraccion`) y el Word las escribe
  con «%» (`fmt_cifra` en `adapters/export/docx.py`); aquí se dan también en pp para que se lean
  como diferencias:

| Hallazgo | Impacto | Cifra |
|---|---|---|
| `F-motor-debil` (Claude 15 % frente a Perplexity 65 %) | L | tasa 15 % |
| `F-ciudad-barcelona` | L | tasa 4,2 % |
| `F-brecha-lider` | L | 40,53 puntos de score |
| `F-caida-embudo` (descubrimiento → decisión) | M | diferencia de 19,7 pp (en el Word: «19,7 %») |
| `F-fuente-lider` (directoriomedico.example) | M | 37 respuestas con el líder y sin la marca |
| `F-asistida-vs-espontanea` | M | diferencia de 61,25 pp, 0,6125 (en el Word: «61,3 %») |
| `F-recomendacion-debil` | M | fuerza media 1,01 (escala de −1 a 3) |

  Recordatorio del ADR 0008: «la visibilidad cae de descubrimiento a decisión» es un indicio, no
  una conclusión firme (solo 4 prompts de decisión).

#### 6b. Exactitud de marca — Calculado, sin conectar · En desarrollo (PR #43)

Que el asistente nombre la marca no basta: lo que dice tiene que ser cierto (ADR 0011,
`domain/accuracy.py`).

- **Afirmaciones:** el código extrae de las respuestas las frases que nombran la marca y las
  clasifica: servicio, sede, profesional, precio, resultado clínico u otro. El texto es siempre un
  fragmento **literal** de la respuesta.
- **Verificación conservadora,** solo contra el brief:
  - **correcta:** cuadra con el brief;
  - **incorrecta:** lo contradice (p. ej., niega un servicio del brief o afirma una sede en una
    ciudad que el brief no recoge);
  - **no verificable:** el brief no trae con qué comparar. **Nunca se marca incorrecta por falta de
    dato.**
- **«A revisar por la clínica»:** una lista explícita de expresiones que, en publicidad sanitaria,
  conviene revisar antes de reutilizar: garantías de resultado, «sin riesgo», «100 %», «la mejor»,
  «la opción más recomendada», comparaciones con otros centros… **No es un juicio de legalidad.**
- **Mitigación** (solo para afirmaciones incorrectas): una acción por fuente de donde viene el
  error. Directorio o reseñas → corregir la ficha (`entidad_datos`). Web propia → corregir el
  contenido (`contenido`). Foro → respuesta oficial (`comunidades`). Medio o ranking → pedir la
  corrección (`autoridad_terceros`). Sin fuente → dato correcto con datos estructurados en la web
  (`entidad_datos`).
- **Qué hace la IA:** opcionalmente (`prompts/claims.v1.md`) propone más fragmentos. El código
  descarta los que no son literales y los verifica igual.
- **[Caso sintético]** (`tests/golden/test_accuracy_golden.py`): 276 afirmaciones; **0
  inexactitudes** (el kit no dice nada falso de Alborada y no fabricamos errores); 62 correctas;
  193 no verificables; **21 «a revisar por la clínica»**, todas por «la opción más recomendada /
  recomendable». Por tanto, 0 acciones de mitigación.
- **Cómo leer «0 inexactitudes»:** «nada contradice el brief», no «todo está confirmado».
- **Estado:** la PR #43 lo expone como `exactitud` y `mitigaciones`. No está en el Word
  (PENDIENTE).

#### 6c. Auditoría técnica de la web — EN DESARROLLO

¿**Pueden** los motores leer la web de la marca? Es una causa técnica, barata de arreglar y
verificable. Diseño en el **ADR 0019** (PR #40, ya fusionada en `develop`).

**Estado real:** en `develop` está solo el **contrato** (PR #40) (`domain/web_audit_schemas.py`) y el puerto
`WebFetcher` en `ports.py`. **No hay todavía** análisis (`domain/web_audit.py`), descargador,
nodo en el grafo, tarjeta en la web ni sección en el Word. Nada de lo que sigue se ha ejecutado.

**Qué comprobará** (todo determinista, descargando la web sin ejecutar JavaScript; unas 16
descargas). Términos: `robots.txt` y `sitemap.xml` son los ficheros con los que una web dice a los
robots qué pueden leer y qué páginas tiene; **JSON-LD** es un bloque de datos estructurados
(schema.org) que describe la organización, sus preguntas frecuentes, etc.; **Content-Signal** es
una declaración de para qué usos de IA se permite el contenido; `llms.txt` es un índice de la web
pensado para modelos de lenguaje; **LCP, INP y CLS** son métricas de velocidad de Google que aquí
no se miden; `/.well-known/` es una carpeta estándar donde una web publica ficheros de
descubrimiento para máquinas.

| Bloque (peso) | Comprobaciones |
|---|---|
| **Descubrimiento** (25) | `robots.txt` existe y es válido · `sitemap.xml` válido · el sitemap aparece en robots.txt · cabeceras `Link` (canonical/alternate) · negociación de markdown (responde `text/markdown` si se pide) |
| **Contenido** (35) | ≥ 500 caracteres de texto visibles **sin JavaScript** · JSON-LD con `Organization` · `Organization` con `sameAs` · `FAQPage` · `HowTo` · `Article` con `dateModified` · `Person` · `BreadcrumbList` · `llms.txt` (título y al menos una URL) |
| **Acceso de bots de IA** (25) | ningún bot de IA bloqueado en la portada · reglas explícitas para cada bot de un motor medido · **Content-Signal** (en robots.txt o como cabecera) con `ai-train`, `search` y `ai-input` |
| **Rendimiento** (10) | la portada responde 2xx en ≤ 2.000 ms (un solo GET; LCP, INP y CLS fuera de alcance) |
| **Agentes / API** (5) | rutas `/.well-known/` (api-catalog, OAuth, MCP server card, agent-skills, ai-catalog). Informativo: no genera hallazgos |

**Bots que se auditan** (`BOT_MOTOR`):

| Motor | Bots |
|---|---|
| ChatGPT | GPTBot, OAI-SearchBot, ChatGPT-User |
| Claude | ClaudeBot, Claude-SearchBot, Claude-Web |
| Perplexity | PerplexityBot, Perplexity-User |
| Gemini | Google-Extended |
| Sin motor medido | Applebot-Extended, CCBot |

**Puntuación de preparación:**

- Cada comprobación sale `ok`, `falla`, `no_aplica` o `error`, con la **evidencia literal** (p. ej.
  la línea de robots.txt).
- Bloque = 100 × pesos `ok` / pesos `ok` + `falla`. Lo que no se pudo ver no castiga.
- Total = media de los bloques ponderada por su peso.
- El validador **recalcula** la puntuación a partir de las comprobaciones: nadie puede publicar
  una puntuación inventada.

**Hallazgos previstos:** `F-web-bots-bloqueados` (L) si un bot de un motor medido tiene la portada
prohibida, y `F-web-<bloque>` si un bloque queda por debajo de 50. Sus evidencias serán las
respuestas espontáneas en las que la marca no aparece en los motores afectados. Las acciones que
los cubran irán con la palanca `tecnico`.

**[Caso sintético]:** los dominios del kit son `.example` y no se pueden descargar. En modo kit
la auditoría usará respuestas fijas de ejemplo y sus hallazgos **no** entrarán en el plan.

### 7. Estrategia recomendada — En el Word

- **Qué contiene:** texto de estrategia, tabla de objetivos (KPI, valor actual, valor objetivo,
  plazo) y lista de prioridades.
- **Qué redacta la IA:** el texto y las prioridades.
- **De dónde salen los objetivos:** del plan aprobado (`Plan.objetivos`). Los propone el LLM del
  plan y los revisa la persona (ver §1). El prompt obliga a que el valor actual sea una cifra ya
  calculada y a que el objetivo sea una hipótesis, nunca una garantía.
- **[Caso sintético] (plan escrito a mano):** «Score de Citación espontáneo» 25,9 → 35 en 42
  semanas; «Visibilidad espontánea en Barcelona» 4 % → 20 % en 42 semanas.

### 8. Plan de acción por fases — En el Word

- **Qué contiene:** presupuesto estimado, «respeta las restricciones del brief: Sí/No» y, por cada
  fase (nombre, semanas, objetivo), sus acciones. Cada acción con palanca, fase del embudo, motores
  objetivo, esfuerzo / impacto, responsable, plazo, KPI, entregables, dependencias, hallazgos que
  la justifican y restricciones revisadas.
- **Estructura típica** (prompt `plan.v1`, formato del reto): Fase 0 · Fundamentos, Fase 1 ·
  Quick wins, Fase 2 · Autoridad y escala, Fase 3 · Optimización y medición. Horizonte de 6 a 12
  meses.
- **Qué verifica el código:** cada acción enlaza al menos un hallazgo que existe; declara todas
  las restricciones del brief; el presupuesto cabe en el máximo del brief. Si falla, se reintenta
  una vez y lo que quede se enseña a la persona en la revisión.
- **Revisión humana:** la persona aprueba o edita el plan antes de la propuesta.

#### Las siete palancas (`Palanca` en `schemas.py`)

Son las de la metodología del kit (§9). Son hipótesis de la industria, no garantías.

| Palanca (código) | Nombre en el Word | Ejemplos | Efecto en la simulación (acción M, esperado) |
|---|---|---|---|
| `autoridad_terceros` | Autoridad en fuentes de terceros | rankings, guías «mejores X», prensa, relaciones públicas | +5 pp |
| `contenido` | Contenido que responde a preguntas reales | FAQ desde el banco de prompts, páginas por ciudad y perfil | +4 pp |
| `entidad_datos` | Entidad y datos estructurados | schema.org, fichas coherentes en directorios, Wikidata | +3 pp |
| `reputacion` | Reputación y reseñas | volumen y respuesta a reseñas | +2 pp |
| `comunidades` | Comunidades y plataformas | foros, vídeo, redes | +1,5 pp |
| `tecnico` | Accesibilidad técnica | rastreable por bots, sin depender de scripts | +1 pp |
| `medicion` | Medición | re-medición, KPIs | 0 (no mueve la visibilidad) |

La última columna es la tabla `IMPACTO_POR_PALANCA` de `domain/simulation.py` (ADR 0007): una
**hipótesis del equipo** para la simulación, no un dato medido.

#### Estrategia por motor

Lo que existe hoy en `develop`:

- La visibilidad espontánea **por motor** (tabla del diagnóstico) y el hallazgo `F-motor-debil`.
- Cada acción puede fijar `motores_objetivo`. La simulación solo mueve los segmentos de esos
  motores.
- **[Caso sintético]:** la acción A2-1 (fichas en directorios y rankings) apunta a ChatGPT y
  Claude, los dos motores donde Alborada aparece menos.

**EN DESARROLLO** (descritos en el ADR 0019, sin código todavía): textos por motor para redactar el plazo esperado. No son
cifras del producto:

- **Perplexity** busca en tiempo real: el efecto llega en semanas.
- **Gemini** se apoya en el índice y el Knowledge Graph de Google (schema, Organization/sameAs,
  perfil de empresa).
- **ChatGPT** depende más de la presencia en fuentes externas (directorios, medios,
  Wikipedia/Wikidata) y tarda meses.

#### 8b. Escenarios del plan — Calculado, sin conectar · En desarrollo (PR #43)

«Con este presupuesto, este equipo y estas prioridades, ¿qué parte del plan hacemos y qué pasa con
el score?» (ADR 0009, `domain/scenarios.py`).

Tres preajustes. Ninguno inventa costes: solo deciden qué acciones se activan.

| Preajuste | Regla exacta |
|---|---|
| **Mínimo viable** | El conjunto de acciones de **menor esfuerzo** (S = 1, M = 2, L = 3) que cubre los hallazgos del nivel de impacto más alto que el plan puede cubrir (L; si no hay, M; si no, S), con sus dependencias |
| **Equilibrado** | El de menor esfuerzo que cubre **todos los hallazgos L y M** |
| **Completo** | Todas las acciones |

- En los preajustes, una acción de `medicion` **no cuenta** como cobertura: no mueve la
  visibilidad.
- Un **escenario personalizado** permite desactivar acciones, fijar prioridades por palanca,
  capacidad del equipo y costes declarados. Si una acción no tiene coste declarado, no consume
  presupuesto: **nunca se inventan costes**. Cada acción aplazada lleva su motivo (desactivada,
  dependencia, fuera de prioridad, fuera de presupuesto, capacidad).
- **[Caso sintético] (plan escrito a mano)** (`tests/golden/test_scenarios_golden.py`), score
  final mínimo / esperado / máximo:

| Preajuste | Acciones | Esfuerzo | Sin cubrir | Score final |
|---|---|---|---|---|
| Mínimo viable | A0-2, A1-2, A2-3 | 5 | F-caida-embudo, F-recomendacion-debil | 26,56 / **27,67** / 28,84 |
| Equilibrado | A0-2, A1-1, A1-2, A2-3 | 7 | — | 26,83 / **28,20** / 29,78 |
| Completo | las 9 | 16 | — | 27,77 / **30,77** / 33,95 |

- **Estado:** la PR #43 calcula los tres y marca el «completo» como elegido. Elegir otro desde la
  API y que la propuesta lo use: PENDIENTE. El intervalo de confianza del score proyectado vale
  `null`: PENDIENTE. No está en el Word.

#### 8c. Simulación del impacto — En la API y en la web, no en el Word

«¿Qué pasaría si se ejecuta el plan?» Es una **estimación con supuestos**, no una promesa (ADR
0007, `domain/simulation.py`).

- **Cómo funciona:**
  1. Reparte la visibilidad espontánea en segmentos fase × motor (y ciudades aparte).
  2. Cada acción enlazada a un hallazgo suma a sus segmentos la mejora de su palanca y su impacto
     (tabla de §8), con un rango mínimo / esperado / máximo.
  3. **Rendimientos decrecientes:** las mejoras de un segmento se ordenan de mayor a menor y la
     k-ésima se multiplica por 0,6^k, con k = 0, 1, 2…: la primera aporta el 100 %, la segunda el
     60 %, la tercera el 36 %… **Tope:** la tasa de aparición de un segmento sube como mucho
     **+20 puntos porcentuales (pp)** (`TOPE_SEGMENTO = 0.20`) y nunca pasa del 95 %
     (`domain/simulation.py`). No son 20 puntos de Score de Citación.
  4. Recalcula el score con **la misma fórmula** (`scoring.score_from_profile`), manteniendo la
     posición, la fuerza y la calidad de fuente de hoy. Proyección acumulada por fase.
- **Supuestos que se publican siempre** (`SUPUESTOS`) y esta **advertencia fija**: «Estimación
  ilustrativa con supuestos declarados, no una predicción: no garantiza resultados ni estima
  visitas o ventas. Los asistentes de IA cambian y la única forma de saber el efecto real del plan
  es volver a medir.»
- **[Caso sintético] (plan escrito a mano):** 25,93 → **30,77** (rango 27,77–33,95), es decir,
  **25,9 → 30,8** (`tests/golden/test_demo_canonico.py`).
- **Estado:** el nodo `plan` la calcula y `GET /studies/{id}` la devuelve (`simulacion`); la web
  la pinta. **No está en el Word** (PENDIENTE, zona E).

### 9. Medición y seguimiento — En el Word (versión básica)

posiq. no vende un score suelto: **vende un seguimiento con método** (ADR 0016). La propuesta es la
puerta de entrada; la re-medición periódica es el servicio recurrente.

#### Lo que hoy pone el Word

Todo lo pone el código (`nodes/write.py`):

- **KPIs:** los de los objetivos del plan (si no hay, «Score de Citación»).
- **Metodología:** «Mismo banco, motores y repeticiones; separar espontánea y asistida.»
- **Cadencia:** «Trimestral».

#### 9b. Serie temporal — Calculado, sin conectar. Endpoints PENDIENTES

Método (`domain/tracking.py`, ADR 0016):

1. Se mide una **línea base**.
2. Cada trimestre se vuelve a medir con el **mismo banco de preguntas** y los mismos motores.
3. **Solo se informa de cambios fuera del margen de error**, y se comparan con los competidores.

- **Comparabilidad:** dos mediciones se comparan solo si coinciden la versión de la metodología,
  la versión del score, la **huella del banco** (una firma, calculada con SHA-256 sobre las
  preguntas, que cambia si cambia cualquier letra de cualquier pregunta) y los
  motores. Si cambia el modelo de un motor, se compara con aviso. Si cambian los competidores del
  mercado, el puesto no se compara.
- **Cambios que se miden:** score, aparición espontánea (global y por motor), puesto y diferencia
  frente a la media de los competidores. Un cambio es significativo si su intervalo al 95 % no
  contiene el 0.
- **Indicadores adelantados** (se mueven antes que el score): cuota de web propia, presencia en
  las 5 fuentes principales, inexactitudes y afirmaciones «a revisar».
- **Textos:** plantillas en español, sin IA. Si nada sale del margen: «Sin cambios fuera del margen
  de error». Con una sola medición: «Línea base: aún no hay con qué comparar.»
- **[Caso sintético]** (`tests/golden/test_serie_alborada.py`): el kit medido dos veces da 0
  cambios significativos, como debe ser. Con un segundo punto **perturbado a propósito** (40
  no-apariciones pasan a 1.ª posición), sale +15,88 [+9,51; +22,47] y del 8.º al 3.er puesto. Es
  una prueba del método, no una mejora real.

**Estado:**

- `POST /studies/{id}/remeasure` existe en `develop`: crea un estudio nuevo con el mismo brief y
  mercado. En modo kit el delta es 0 (mide repetibilidad, no mejora).
- **Banco de la re-medición.** En modo kit, el banco es siempre el del kit (nodo `prompts`,
  `application/nodes/prompts.py`), así que la huella coincide. En modo real, sin la PR #43 la
  re-medición genera un banco nuevo con el LLM y no sería comparable; con la PR #43 reutiliza el
  banco del estudio original.
- **API de serie** (`GET /brands`, `GET /brands/{id}/serie`, `GET /studies/{id}/remeasure/estimate`):
  **PENDIENTE** (no hay PR; es la siguiente tarea de la zona C, `docs/estado/C.md`). Hoy ningún
  endpoint construye la serie.
- **Web de seguimiento:** la vista está en `develop` (PR #38, fusionada), pero **sin datos** hasta
  que existan los endpoints: muestra «Seguimiento no disponible todavía».
- **PENDIENTE: el juez.** Hoy la comparabilidad **no mira qué juez** evaluó cada medición. Como el
  juez cambia el resultado (25,93 con etiquetas frente a 25,87 con reglas en el caso sintético),
  una serie solo es comparable si todas las mediciones usan el mismo juez. Hay que añadirlo y
  decidir un juez único para las mediciones reales (solo reglas: barato pero con fuerza tosca; Jev
  con fallback DeepSeek: mejor pero más caro; o solo DeepSeek). Mezclar no vale.

### 10. Riesgos y supuestos — En el Word

- **Qué contiene:** tabla riesgo → mitigación.
- **Qué redacta la IA:** los riesgos y sus mitigaciones (`ProposalDraft.riesgos`, al menos uno).
  Los supuestos de la IA van a las limitaciones de la sección 3.
- **Qué pone el código:** las limitaciones obligatorias (sección 3). Los supuestos de la
  simulación (8c) todavía no llegan al Word.

### 11. Hoja de ruta y presupuesto — En el Word

- **Qué pone el código** (`assemble_proposal`):
  - **Hitos:** uno al final de cada fase, en la semana acumulada («Fin de Fase 0 · Fundamentos»…).
  - **Responsabilidades:** las acciones agrupadas por responsable.
  - **Presupuesto:** el del plan aprobado.
- **Qué redacta la IA:** el texto del modelo de seguimiento (`hoja_ruta`).
- **[Caso sintético] (plan escrito a mano):** 4 fases (6 + 8 + 16 + 12 semanas), 9 acciones,
  22.000 €, dentro del rango del brief de 18.000–27.000 €.

---

## 4. Lo que el esquema garantiza siempre

Estas reglas las comprueba Pydantic (la librería que valida los datos contra el esquema) al
construir la `Proposal` (`schemas.py`). Si no se cumplen,
la propuesta no se crea:

- Todos los hallazgos, el plan y las métricas son **del mismo estudio**.
- Entre 3 y 7 hallazgos, cada uno con al menos una evaluación (`evaluation_ids`).
- Cada acción tiene al menos un hallazgo (`finding_ids`) y al menos un entregable, y esos
  hallazgos existen en la propuesta.
- Cada punto del encargo enlaza solo a acciones y hallazgos que existen.
- Hay al menos una limitación (`Contexto.limitaciones`) y al menos un riesgo.

Además, al crear **cada evaluación** (validador de `Evaluation` en `schemas.py`, no de
`Proposal`): una evaluación en la que la marca no aparece tiene fuerza 0 y no tiene posición.

---

## 5. Cómo contarlo sin equivocarse

| Decir | No decir |
|---|---|
| «En el caso sintético del reto, nuestro método da a Alborada 25,9 [21,6–30,1].» | «Alborada tiene un 25,9 de visibilidad.» |
| «Las respuestas del kit las escribieron los organizadores.» | «Hemos preguntado a ChatGPT y…» |
| «El modo real está programado, pero no lo hemos ejecutado.» | «Medimos los cuatro motores en real.» |
| «La simulación es una estimación con supuestos: 25,9 → 30,8 en el caso sintético.» | «Con el plan, el score sube a 30,8.» |
| «0 inexactitudes: nada contradice el brief.» | «Todo lo que dicen de la marca es cierto.» |
| «“A revisar por la clínica” es una lista de expresiones.» | «Detectamos publicidad ilegal.» |
| «La auditoría técnica de la web está diseñada; de momento solo existe su contrato.» | «Auditamos la web.» |
| «Márgenes, competidores declarados, fuentes, exactitud y escenarios están calculados y se conectan en la PR #43; aún no salen en el Word.» | «El Word incluye márgenes de error.» |

---

## 6. Dónde se comprueba

**Propuesta y Word**

- `src/posiq/domain/schemas.py`: `Proposal`, `Encargo`, `PuntoBrief`, `Finding`, `Action`,
  `Palanca`, `validate_plan_against_brief`.
- `src/posiq/application/nodes/write.py`: `assemble_proposal`, limitaciones obligatorias.
- `src/posiq/application/schemas_draft.py`: `ProposalDraft` (lo que redacta la IA).
- `src/posiq/application/nodes/plan.py`: plan, reintento, simulación y PlanGuard (el juez que
  revisa la calidad de cada acción del plan).
- `src/posiq/adapters/export/template.py` (`SECCIONES`) y `src/posiq/adapters/export/docx.py`
  (`build_context`, `AVISO_SINTETICO`, `PALANCAS`).
- `src/posiq/prompts/write.v2.md`, `src/posiq/prompts/plan.v1.md`.
- `src/posiq/adapters/llm/fixture.py` y `_fixture_data.py`: textos y plan de la demo sin IA.
- Tests: `tests/golden/test_export.py`, `tests/golden/test_demo_canonico.py`,
  `tests/e2e/test_demo_canonica_api.py`, `tests/golden/test_plan_guard_golden.py`.

**Cálculo** (un **test golden** es una prueba que fija la cifra exacta esperada: si el cálculo
cambia, la prueba falla)

| Bloque | Código | Test | ADR |
|---|---|---|---|
| Score de Citación | `domain/scoring.py` | `tests/golden/test_demo_canonico.py`, `test_metrics_golden.py` | — |
| Métricas | `domain/metrics.py` | `tests/golden/test_metrics_golden.py` | — |
| Hallazgos | `domain/findings.py` | `tests/golden/test_fixtures_alborada.py` | — |
| Juez | `domain/detection.py`, `domain/judge_questions.py` | `tests/golden/test_detection_golden.py`, `test_judge_calibration.py` | 0003, 0014 |
| Márgenes | `domain/stats.py`, `domain/stats_schemas.py` | `tests/golden/test_rigor_alborada.py` | 0008 |
| Encargo y cobertura | `domain/brief_coverage.py` | `tests/golden/test_brief_coverage_golden.py` | 0013 |
| Competidores declarados | `domain/competitor_gap.py` | `tests/golden/test_competitor_gap_golden.py` | 0012 |
| Mapa de fuentes y web propia | `domain/source_map.py` | `tests/golden/test_source_map_golden.py` | 0010 |
| Exactitud de marca | `domain/accuracy.py`, `application/accuracy.py`, `prompts/claims.v1.md` | `tests/golden/test_accuracy_golden.py` | 0011 |
| Escenarios | `domain/scenarios.py` | `tests/golden/test_scenarios_golden.py` | 0009 |
| Simulación | `domain/simulation.py` | `tests/golden/test_simulation_golden.py` | 0007 |
| Serie temporal | `domain/tracking.py`, `domain/tracking_schemas.py` | `tests/golden/test_serie_alborada.py` | 0016 |
| Auditoría técnica de la web | `domain/web_audit_schemas.py` (solo el contrato) | `tests/domain/test_web_audit_schemas.py` | 0019 |

**Estado y PRs abiertas**

- `docs/estado/A.md`, `C.md`, `D.md`, `E.md`.
- PR #43 (`feature/C-diferencial-grafo`): rigor, competidores, oportunidades, exactitud y
  escenarios en el grafo y la API; re-medición con el mismo banco.
- PR #40 (fusionada): contrato de la auditoría técnica y ADR 0019. El análisis sigue sin existir.
- PR #38 (fusionada): login en la web, vista de seguimiento por marca (espera endpoints que aún
  no existen) y re-medición con coste confirmado.

**Kit del reto**

- `data/kit/00_LEEME_Guia_del_kit.md`: todo es ficticio.
- `data/kit/03_Documentacion/02_Metodologia_GEO.md`: score (§7), espontánea frente a asistida
  (§8), palancas (§9), limitaciones (§10).
- `data/kit/03_Documentacion/06_Formato_del_entregable.md`: las 10 secciones y la lista de
  calidad.

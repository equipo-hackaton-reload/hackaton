# Glosario de posiq.

Términos que usamos en la presentación y en los entregables, en orden alfabético. Cada entrada
dice qué es, en 1–3 frases, y dónde se ve en el producto o en el código. Las rutas son relativas a
la raíz del repositorio.

## Antes de leer: la regla de oro

**Todo lo que hemos medido hasta hoy es el caso sintético del reto.** El kit lo dice en su primera
página: «Todos los datos, marcas, personas y cifras son ficticios y sintéticos»
(`data/kit/00_LEEME_Guia_del_kit.md`). Clínica Alborada Visión y sus competidores no existen, las
624 respuestas de los asistentes las escribieron los organizadores y los dominios terminan en
`.example`.

- Toda cifra de Alborada en este glosario (25,93; 8.ª de 10; 25,9 [21,6–30,1]; 18 % en las respuestas atribuidas a ChatGPT…)
  significa **«nuestro método aplicado al caso sintético del reto»**. No dice nada del mercado
  real de la oftalmología. Las marcamos con *(caso sintético)*.
- **El modo real (preguntar a las APIs de ChatGPT, Gemini, Perplexity y Claude) no se ha
  ejecutado nunca.** El código existe y está probado con respuestas simuladas, pero no hay ninguna
  medición real.
- Usamos tres etiquetas de estado:
  - **En develop:** está en la rama de integración y tiene tests.
  - **En desarrollo:** hay código, pero en una rama que aún no está en `develop`, o está en
    `develop` sin conectar a la API o a la web.
  - **PENDIENTE:** decidido, pero sin código.

---

## A

### Acción (`Action`)

Una tarea concreta del plan: qué hacer, con qué palanca, en qué fase del embudo, para qué
motores, con qué esfuerzo e impacto (S/M/L), quién la hace, en cuántas semanas y con qué KPI.
Toda acción lleva `finding_ids`: los hallazgos que intenta resolver. El esquema rechaza una acción
sin ellos, así que no puede haber acciones «porque sí».

- **Dónde:** pantalla «Plan» de la web y sección del plan en el Word. Código:
  `src/posiq/domain/schemas.py` (`Action`, `finding_ids` con `min_length=1`).
- **Ejemplo (caso sintético):** el plan de ejemplo de Alborada tiene 9 acciones (A0-1 … A3-2) en
  4 fases (de la 0 a la 3) y cuesta 22.000 € (`example_plan` en `tests/golden/conftest.py` y
  `src/posiq/adapters/llm/_fixture_data.py`; lo comprueba
  `tests/golden/test_brief_coverage_golden.py`). En la demo ese plan es un ejemplo fijo del modo
  fixture, no lo redacta un LLM.

### «A revisar por la clínica»

Etiqueta que ponemos a una afirmación de un asistente sobre la marca que contiene una expresión
delicada en publicidad sanitaria: garantías de resultado («resultados garantizados»), ausencia de
riesgo («sin riesgo»), absolutos («100 %»), superlativos («la mejor clínica») o comparaciones con
otros centros. **No es un juicio de legalidad**: es una lista explícita de expresiones que la
clínica debería revisar antes de reutilizarlas.

- **Dónde:** `src/posiq/domain/accuracy.py` (`EXPRESIONES_RIESGO`) y
  `src/posiq/domain/accuracy_schemas.py` (`ETIQUETA_RIESGO`). ADR 0011.
- **Ejemplo (caso sintético):** 21 afirmaciones de Alborada, todas por «la opción más recomendada /
  recomendable» (`tests/golden/test_accuracy_golden.py`).
- **Estado:** el cálculo está en develop. Que llegue a la API y la web está **en desarrollo**.

### Afirmación

Ver **Exactitud de marca**.

### Aparición

Que una marca salga nombrada (por su nombre o un alias, sin distinguir mayúsculas ni acentos) en
una respuesta de un motor. La **tasa de aparición** es apariciones / evaluaciones. Es también el
primer componente del Score de Citación (ver **Score de Citación**).

- **Dónde:** `src/posiq/domain/detection.py` (detección por reglas) y
  `src/posiq/domain/metrics.py` (tasas por motor, fase, ciudad, perfil y familia).

### Asistido (prompt)

Ver **Prompt espontáneo y asistido**.

## B

### Banco de prompts y su huella

El **banco de prompts** es la lista de preguntas que se lanzan a los motores. Imita cómo preguntan
los usuarios reales en cada fase del embudo. Cada plantilla se **instancia** con ciudades, una
marca o un par de marcas. La **huella del banco** es un resumen (una huella digital SHA-256: un
código que cambia por completo si cambia cualquier detalle) de lo que se pregunta en
cada prompt: plantilla, familia, fase, instanciación, perfil, ciudad, texto, marcas nombradas y
prioridad. Si cambia una sola pregunta, cambia la huella, y dos mediciones dejan de ser
comparables.

- **Dónde:** el banco del kit está en `data/kit/02_Datos/caso_oftalmologia/banco_prompts.csv`
  (25 plantillas). En modo real lo genera el nodo `prompts`
  (`src/posiq/application/nodes/prompts.py`). Huella: `huella_banco` en
  `src/posiq/domain/tracking.py`. ADR 0016.

### Brief

El documento del cliente con el que empieza todo: su marca, sector, servicios prioritarios,
ciudades, públicos, competidores declarados, objetivos, restricciones, equipo y presupuesto anual.
posiq. lo resume en una ficha estructurada y de ahí salen las preguntas, el plan y el encargo.

- **Ejemplo (caso sintético):** el brief de Clínica Alborada Visión del kit (`data/kit/`), que es
  ficticio.
- **Dónde:** `BriefSummary` en `src/posiq/domain/schemas.py`.

### Bootstrap

Método para calcular el margen de error de una cifra que no tiene fórmula sencilla, como el Score
de Citación. Se sacan muchas muestras al azar, con reemplazo, de las ejecuciones medidas (2.000
réplicas), se recalcula el score en cada una con la misma función y se toma el rango que deja
fuera el 2,5 % más bajo y el 2,5 % más alto. La semilla es fija (`20261021`), así que el mismo
estudio da siempre el mismo intervalo.

- **Variantes:** emparejado (las mismas ejecuciones para dos marcas del mismo estudio) e
  independiente (dos estudios distintos, en la re-medición).
- **Dónde:** `src/posiq/domain/stats.py` (`intervalo_score`, `diferencia_scores`,
  `REPLICAS_BOOTSTRAP`, `SEMILLA_BOOTSTRAP`). ADR 0008.

### Bots de IA

Ver **robots.txt y bots de IA**.

## C

### Calidad de fuente

Cuarto componente del Score de Citación. Ver **Score de Citación**.

### Capa determinista y capa no determinista

Separamos lo que decide el código de lo que decide la IA.

- **Capa determinista:** el mismo dato da siempre el mismo resultado. Son las **reglas**, que
  deciden si la marca aparece y en qué posición, y todo el cálculo de cifras (score, métricas,
  intervalos, hallazgos, simulación).
- **Capa no determinista:** los modelos de IA. **Jev** decide el tipo de mención, la fuerza, el
  sentimiento y el apoyo en fuentes; el **LLM de fallback** responde cuando Jev duda; un LLM
  redacta el plan y la propuesta.
- Frase para la presentación (ADR 0014): «las reglas deterministas ponen el suelo y auditan, Jev
  aporta la semántica calibrada y, si discrepan, revisa un humano».
- **Dónde:** `docs/adr/0014-capa-determinista-y-no-determinista.md`; reglas en
  `src/posiq/domain/detection.py`; jueces en `src/posiq/adapters/judge/`.

### Caso sintético (el kit)

El material que nos dio el reto: un brief de ejemplo (Clínica Alborada Visión, oftalmología, Madrid
y Barcelona), 10 marcas, un catálogo de 25 fuentes, 25 plantillas de prompts, 624 respuestas ya
escritas («ejecuciones»: 4 motores × 3 repeticiones) y 133 evaluaciones de referencia ya
etiquetadas (`muestra_evaluada.csv`, sobre 15 ejecuciones). **Todo es ficticio**, también esas
etiquetas, que escribieron los organizadores: sirve para construir y demostrar el método, no para
sacar conclusiones de mercado.

- **Dónde:** `data/kit/` (datos en `data/kit/02_Datos/caso_oftalmologia/`, documentación en
  `data/kit/03_Documentacion/`). Se carga con `src/posiq/domain/kit_loader.py`.

### Cifra canónica

La cifra de referencia de la demo: **Score de Citación de Alborada = 25,93** (25,9 en la
presentación), 8.ª de 10 marcas, con proyección del plan 25,9 → 30,8 *(caso sintético)*. Sale de
evaluar las 624 respuestas del kit con las **133 etiquetas de referencia del kit**
(`muestra_evaluada.csv`, 15 ejecuciones; también escritas por los organizadores) donde existen y
con **reglas** en el resto (la gran mayoría de los 2.928 pares respuesta-marca). Está fijada en un test: si alguien cambia algo que la mueve, el test falla.

- Con **solo reglas** sale 25,87: la aparición y la posición son iguales, pero la fuerza (3,88
  frente a 3,92) y la calidad de fuente (5,65 frente a 5,67) cambian. Con un decimal, las dos dan
  25,9.
- **Dónde:** `tests/golden/test_demo_canonico.py` y, por la API en modo fixture,
  `tests/e2e/test_demo_canonica_api.py`.

### Comparabilidad

Regla que decide si una medición se puede comparar con la anterior. Hoy dos mediciones son
comparables si coinciden **cuatro** cosas: la versión de la metodología, la versión del score, la
huella del banco de prompts y el conjunto de motores. Si cambia el modelo de un motor (p. ej. otra
versión de GPT), sigue siendo comparable, pero con aviso. Si cambian las marcas del mercado, el
score y la aparición se comparan, pero el puesto y la diferencia frente a los competidores no.

- **PENDIENTE: el juez.** El juez cambia el resultado (en el kit, solo reglas da 25,87 y las
  etiquetas 25,93). Una serie solo es comparable si todas sus mediciones usan el mismo juez, pero
  la regla actual **todavía no lo comprueba**. Hay que añadirlo (planificado para la ola 2) y
  elegir un juez único para las mediciones reales: reglas, Jev con fallback DeepSeek o solo DeepSeek.
- **Dónde:** `comparabilidad` en `src/posiq/domain/tracking.py`; para dos estudios sueltos,
  `diff_metrics` en `src/posiq/domain/metrics.py` (marca «no comparable» si cambia la versión del
  score). ADR 0016.

### Competidores declarados frente a los de la IA

Cruzamos los competidores que el cliente escribe en su brief con el ranking que sale de las
respuestas de los asistentes. Así podemos decir «creías que tu rival era X, pero la IA te compara
con Y». Genera dos hallazgos:

- `F-competidor-no-declarado`: una marca que el cliente no vigila y le saca **5 puntos o más** de
  Score de Citación (impacto L si son 10 o más).
- `F-declarado-poco-visible`: un competidor declarado cuya aparición espontánea es menor que el
  máximo entre 10 % y la mitad de la tasa de la marca.
- **Ejemplo (caso sintético):** Alborada declara Valdecruz (1.ª), Tramuntana (2.ª) y Láser Nítida
  (4.ª). Oftalmos Centro, que no declara, es 3.ª y le saca 13,1 puntos → hallazgo L.
- **Dónde:** `src/posiq/domain/competitor_gap.py`; `tests/golden/test_competitor_gap_golden.py`.
  ADR 0012.
- **Estado:** el cálculo está en develop. Su conexión al grafo y a la API está **en desarrollo**.

### Confianza

Cuánto nos fiamos de un dato, de 0 a 1. Se usa en dos sitios:

- **En una evaluación:** la confianza del juez. Es el mínimo de la confianza de tres preguntas
  (¿aparece?, tipo de mención y fuerza). Si las reglas no ven la marca, solo cuenta ¿aparece?; si
  juez y reglas discrepan, la confianza se limita a 0,5 (y por eso pasa al fallback y a revisión
  humana). Con 0,80 o más se acepta; entre 0,55 y 0,80 se acepta y se marca para revisión humana;
  por debajo de 0,55 pasa al LLM de fallback. Una evaluación solo por reglas lleva 0,3, y una
  etiqueta de referencia del kit, 1. Código: `score_confidence` y `DISCREPANCY_CAP` en
  `src/posiq/adapters/judge/base.py`.
- **En un hallazgo:** depende del tamaño de la muestra que respalda la cifra: 0,8 con 60
  evaluaciones o más, 0,65 con 20 o más y 0,45 con menos.
- **Dónde:** umbrales `JUDGE_CONFIDENCE_ACCEPT` y `JUDGE_CONFIDENCE_FALLBACK` en
  `src/posiq/settings.py`; `confidence_for` en `src/posiq/domain/findings.py`;
  `evaluation_from_detection` en `src/posiq/domain/detection.py`. ADR 0003 y 0014.
- **No confundir** con el **intervalo de confianza**, que es un margen de error estadístico.

### Content-Signal

Una línea que una web puede poner en su `robots.txt` (o como cabecera) para declarar qué permite
hacer con su contenido a los sistemas de IA: entrenar modelos (`ai-train`), aparecer en búsquedas
(`search`) o usarse como fuente de una respuesta (`ai-input`).

- **Estado: en desarrollo.** Forma parte de la **auditoría técnica de la web**, que solo tiene el
  contrato en `develop` (PR #40, ADR 0019), sin implementar. posiq. todavía no lee ninguna web.

### contract-change

Etiqueta obligatoria del PR que cambia un **contrato**: `src/posiq/domain/schemas.py` (los modelos
de datos que comparten todas las zonas) o `src/posiq/ports.py` (las interfaces de los
adaptadores). Existe para que nadie rompa a las demás zonas sin avisar.

- **Dónde:** `CLAUDE.md` (§4) y `CONTRIBUTING.md`.

### Cuentas y propiedad de los estudios

Cada usuario se registra con correo y contraseña, verifica la cuenta con un código de 6 dígitos y
entra con un token de sesión (una clave temporal que identifica al usuario). Cada estudio pertenece a un usuario y nadie más lo ve: si pides uno ajeno, la
API responde 404, igual que si no existiera. La re-medición hereda el propietario del original.

- No hay proveedor de correo: el código de verificación se escribe en el log del servidor (en la
  demo, la API lo devuelve como `codigo_dev`).
- **Dónde:** `src/posiq/interfaces/api/auth.py` (`/auth/register`, `/auth/verify`, `/auth/login`…),
  `src/posiq/application/accounts.py`, `src/posiq/application/security.py`,
  `src/posiq/adapters/repo/accounts.py`. ADR 0015.
- **Estado:** la API y el login en la web están en develop (PR #36 y PR #38).

## E

### Ejecución (`Run`)

Un prompt lanzado a un motor en una repetición concreta, con su respuesta y las fuentes que citó.
Como los asistentes no responden siempre igual, cada prompt se repite (3 veces por motor en el
kit).

- **Dónde:** `Run` en `src/posiq/domain/schemas.py`; en el kit, `ejecuciones.csv` (624 filas,
  todas escritas por los organizadores).

### Encargo y cobertura del brief

El **encargo** es lo que pidió el cliente, copiado **tal cual** del brief sin pasar por la IA:
objetivos, restricciones, servicios prioritarios, ciudades, públicos, competidores declarados y
presupuesto. La **cobertura** dice, para cada punto, dónde lo trata la propuesta (qué acciones o
hallazgos) y si está «cubierto» o «pendiente».

- Las restricciones se cubren solo si todas las acciones las declaran; el presupuesto, si el plan
  no supera el máximo del brief.
- Si falta algo, el redactor lo intenta una vez más y, si sigue faltando, lo declara como
  limitación de la propuesta.
- **Ejemplo (caso sintético):** en la demo, 16 de 16 puntos cubiertos; plan de 22.000 € frente a un
  máximo de 27.000 €.
- **Dónde:** sección «2. Lo que nos habéis pedido» del Word; `proposal.encargo` en
  `GET /studies/{id}`. Código: `src/posiq/domain/brief_coverage.py`, `Encargo` y `PuntoBrief` en
  `src/posiq/domain/schemas.py`; `tests/golden/test_brief_coverage_golden.py`. ADR 0013.

### Escenario y preajustes

Un **escenario** responde a «con este presupuesto, este equipo y estas prioridades, ¿qué parte del
plan hacemos y cuánto se mueve el score?». Decide qué acciones se mantienen y cuáles se aplazan, y
por qué (desactivada, dependencia, fuera de prioridad, fuera de presupuesto o sin capacidad). Nunca
inventa costes: solo cuentan los que declara el consultor.

Hay tres **preajustes** ya hechos:

| Preajuste | Qué hace | Score final esperado *(caso sintético)* |
|---|---|---|
| `minimo_viable` | Lo mínimo para cubrir los hallazgos de mayor impacto | 27,67 |
| `equilibrado` | Lo mínimo para cubrir todos los hallazgos L y M | 28,20 |
| `completo` | Todas las acciones del plan | 30,77 (la canónica 25,9 → 30,8) |

- **Dónde:** `src/posiq/domain/scenarios.py`, `src/posiq/domain/scenario_schemas.py`;
  `tests/golden/test_scenarios_golden.py`. ADR 0009.
- **Estado:** el cálculo está en develop. En la API el campo `escenarios` sale vacío (`null`)
  hasta que se fusione la rama `feature/C-diferencial-grafo` (**en desarrollo**).

### Estudio (`Study`)

Una medición de una marca en una fecha, con su brief, su modo (`kit` o `real`) y las versiones de
la metodología y del score. Todo resultado (ejecuciones, evaluaciones, hallazgos, plan, trazas)
lleva el `study_id`, así que nunca se mezclan datos de dos mediciones.

- **Dónde:** `Study` en `src/posiq/domain/schemas.py`. ADR 0002.

### Evaluación (`Evaluation`)

El juicio sobre **una marca en una respuesta**: si aparece, en qué posición, tipo de mención, fuerza
(de −1 a 3), sentimiento, tipo de fuente, confianza, quién la hizo (`jev`, `fallback` o `humano`)
y si necesita revisión humana. Su id es `<id de la ejecución>:<id de la marca>`.

- **Ojo:** una evaluación solo por reglas también lleva origen `fallback` (no existe un origen
  «reglas»); se reconoce por su confianza de 0,3 (`evaluation_from_detection` en
  `src/posiq/domain/detection.py`).

- **Ejemplo (caso sintético):** el kit tiene 2.928 evaluaciones posibles; 240 son de Alborada en
  prompts espontáneos.
- **Dónde:** `Evaluation` en `src/posiq/domain/schemas.py`; en la web, al abrir las evidencias de
  un hallazgo (`GET /studies/{id}/evaluations?ids=`).

### `evaluation_ids`

La lista de evaluaciones que respaldan una cifra. Todo hallazgo la lleva, y el esquema la exige
(mínimo una). Es lo que nos permite decir «esta cifra sale de estas respuestas concretas» y
enseñarlas.

- **Dónde:** `Finding.evaluation_ids` en `src/posiq/domain/schemas.py`; botón de evidencias de cada
  hallazgo en la web. Comprobación: `src/posiq/domain/evidence.py`.

### Exactitud de marca

Que un asistente nombre la marca no basta: lo que dice tiene que ser cierto. Extraemos de las
respuestas las **afirmaciones** sobre la marca (servicios, sedes, profesionales, precios,
resultados clínicos) y las comparamos con el brief. Cada una queda como **correcta**,
**incorrecta**, **no verificable** o **a revisar por la clínica**. Es conservadora a propósito:
nunca marca «incorrecta» por falta de datos.

- **Ejemplo (caso sintético):** 276 afirmaciones sobre Alborada: 62 correctas, 0 incorrectas, 193
  no verificables y 21 a revisar. «0 inexactitudes» significa «nada contradice el brief», no
  «todo está confirmado».
- **Dónde:** `src/posiq/domain/accuracy.py` (reglas), `src/posiq/application/accuracy.py` (capa
  opcional con LLM), `tests/golden/test_accuracy_golden.py`. ADR 0011.
- **Estado:** el cálculo está en develop. Su conexión a la API y a la web está **en desarrollo**.

## F

### Fallback (juez de)

Un segundo juez, un LLM (DeepSeek), que responde **las mismas preguntas** que Jev cuando la
confianza de Jev es baja (menos de 0,55) o cuando Jev contradice a las reglas sobre si la marca
aparece. Si hay contradicción, la evaluación va siempre a revisión humana: un segundo modelo no
desempata contra las reglas.

- **Dónde:** `src/posiq/adapters/judge/llm_fallback.py` y `src/posiq/adapters/judge/jev.py`.
  ADR 0003 y 0014.
- **Estado:** nunca se ha ejecutado con claves reales.

### Fase del embudo

El momento de la decisión del usuario en el que está una pregunta. Hay cuatro: **descubrimiento**
(qué opciones hay), **comparación** (contrastar), **validación** (¿es fiable?) y **decisión**
(elegir). Ver dónde entra y dónde se cae una marca es uno de los análisis más útiles.

- **Dónde:** `FaseEmbudo` en `src/posiq/domain/schemas.py`; métricas por fase en
  `src/posiq/domain/metrics.py`; hallazgo `F-caida-embudo` en `src/posiq/domain/findings.py`.
  Metodología del kit: `data/kit/03_Documentacion/02_Metodologia_GEO.md` (§3).
- **Ojo (caso sintético):** la caída de descubrimiento a decisión de Alborada es significativa si
  se remuestrean ejecuciones, pero deja de serlo si se remuestrean prompts enteros: solo hay 4
  prompts de decisión. Es un indicio, no una conclusión firme (ADR 0008).

### Fixture

Una respuesta fija y preparada que sustituye a un servicio de pago. Con `LLM_PROVIDER=fixture`,
el sistema no llama a ninguna IA: `FixtureLLM` devuelve textos y un plan de ejemplo (el resumen
empieza con «DEMO SIN IA») y `FixtureJudge` usa las etiquetas de referencia del kit (sintéticas)
y reglas. Así la demo
funciona sin claves, gratis y siempre igual.

- **Dónde:** `src/posiq/adapters/llm/fixture.py` y `src/posiq/adapters/llm/_fixture_data.py`.

### Fuerza (de recomendación)

Tercer componente del Score de Citación: cuánto recomienda el motor a la marca. Escala del kit:
3 recomendación principal, 2 recomendación secundaria, 1 mención neutra, 0 no aparece, −1 aparece
con advertencia. Ver **Score de Citación**.

## G

### GEO (Generative Engine Optimization)

Medir y mejorar la presencia de una marca en las respuestas de los asistentes de IA generativa. No
sustituye al SEO: lo complementa. Cambia qué se mide (si el asistente te nombra y te recomienda) y
dónde hay que estar (también en las fuentes que los asistentes citan).

- **Dónde:** `data/kit/03_Documentacion/02_Metodologia_GEO.md` (§1 y §11).

## H

### Hallazgo (`Finding`)

Una conclusión del diagnóstico con su cifra, su impacto (S/M/L), su confianza, la métrica de la
que sale (`origen_cifra`) y sus `evaluation_ids`. Los genera **código**, con reglas explícitas y
umbrales fijos, no la IA. Como máximo hay 7 por propuesta.

- Reglas: caída en el embudo, motor débil, fuente del líder, ciudad baja, brecha con el líder,
  asistida frente a espontánea, recomendación débil y menciones negativas.
- **Ejemplo (caso sintético):** Alborada tiene 7 hallazgos; 6 admiten contraste estadístico y los 6
  son significativos (ADR 0008).
- **Dónde:** `src/posiq/domain/findings.py`; pantalla «Diagnóstico» de la web.

### Huella del banco

Ver **Banco de prompts y su huella**.

## I

### Indicador adelantado

Una cifra que se mueve **antes** que el Score de Citación y avisa de si el plan va por buen
camino. Hay cuatro por medición: cuota de citas a la web propia, presencia en las 5 fuentes
ganadas más citadas del sector, número de inexactitudes y número de afirmaciones «a revisar». Si
la medición no trae los datos, el valor queda vacío: nunca se inventa.

- **Ejemplo (caso sintético):** web propia 5,9 % (0,0585), presencia en el top 5 de fuentes 74,1 %, 0
  inexactitudes y 21 a revisar (`tests/golden/test_serie_alborada.py`).
- **Dónde:** `IndicadorAdelantado` en `src/posiq/domain/tracking_schemas.py`; cálculo en
  `src/posiq/domain/tracking.py`. ADR 0016.

### Intervalo de confianza (IC)

El rango en el que, con un 95 % de confianza, está el valor verdadero de una cifra medida con una
muestra. Se escribe «valor [inferior–superior]». Dice cuánto de la cifra puede ser ruido de
muestreo.

- **Ejemplo (caso sintético):** Score de Citación de Alborada **25,9 [21,6–30,1]**; aparición
  espontánea en ChatGPT **18 % [11–30 %]** con 60 ejecuciones.
- **Límite:** el intervalo solo cubre el azar de las respuestas, no los errores del juez. Y es algo
  optimista, porque las 3 repeticiones de un mismo prompt se parecen entre sí.
- **Dónde:** `src/posiq/domain/stats.py` (`formato_intervalo`); `tests/golden/test_rigor_alborada.py`.
  ADR 0008.
- **Estado:** el cálculo está en develop. En la API, el campo `rigor` sale vacío hasta que se
  fusione `feature/C-diferencial-grafo` (**en desarrollo**).

## J

### Jev

El modelo de TypeSafe (System One) que usamos como **juez principal**. Responde preguntas tipadas
(sí/no, elección entre opciones, puntuación) y da la probabilidad de cada respuesta, lo que nos
sirve como confianza. Tenemos fijada la versión `jev-1.13` para que los resultados sean
reproducibles.

- **Dónde:** `src/posiq/adapters/judge/jev.py`; preguntas en `src/posiq/domain/judge_questions.py`;
  versión en `src/posiq/settings.py` (`jev_model`). ADR 0003 y 0014.
- **Estado:** **nunca se ha llamado con una clave real.** La cifra canónica no usa Jev. La
  calibración contra las etiquetas del kit está **PENDIENTE** (`docs/calibracion/`).

### JSON-LD y schema.org

**schema.org** es un vocabulario común para describir datos en una web (una organización, sus
sedes, sus servicios, preguntas frecuentes). **JSON-LD** es la forma de escribirlo dentro de la
página. Ayuda a que buscadores y asistentes reconozcan la marca y sus datos sin adivinarlos.

- **Dónde:** la metodología del kit cita schema.org («datos estructurados (schema.org)») dentro de
  la palanca «Entidad y datos estructurados» (`02_Metodologia_GEO.md`, §9); que JSON-LD es la
  forma de escribirlo es una explicación nuestra. El el brief de Alborada dice que no tiene datos estructurados. En
  posiq. aparece como recomendación en la mitigación de errores
  (`src/posiq/domain/accuracy.py`, ADR 0011).
- **Estado:** comprobar si la web de la marca tiene JSON-LD es parte de la auditoría técnica, **en
  desarrollo** (solo el contrato está en `develop`, PR #40, ADR 0019).

### Juez

La pieza que convierte una respuesta de un motor en evaluaciones. Hay tres niveles:

| Juez | Qué hace | Cuándo |
|---|---|---|
| **Reglas** | Aparición y posición por alias y orden en el texto. Si aparece, fuerza 1 y fuente sin resolver | Siempre: es el suelo y audita a los demás |
| **Jev** | Tipo de mención, fuerza, sentimiento y apoyo en fuentes, con confianza | Modo real, si hay clave de TypeSafe |
| **Fallback (LLM, DeepSeek)** | Las mismas preguntas | Cuando Jev duda o contradice a las reglas; sin clave de TypeSafe, es el **juez único** |

- **Qué juez se usa en modo real** (`build_judge` en `src/posiq/adapters/judge/__init__.py`; nodo
  `judge` en `src/posiq/application/nodes/judge.py`):
  1. Con clave de TypeSafe: juzga Jev, con DeepSeek de fallback.
  2. Solo con clave de DeepSeek: DeepSeek es el único juez, sin Jev.
  3. Sin claves, o con `JUDGE_PROVIDER=reglas`: juzgan solo las reglas (si faltan claves, el
     nodo lo anota en los errores del estudio y la propuesta lo declara como limitación).
- Para que una serie sea comparable, todas sus mediciones deben usar la misma de estas tres
  opciones.

- Las preguntas del juez viven en un solo sitio y las comparten Jev y el fallback:
  `src/posiq/domain/judge_questions.py`.
- `JUDGE_PROVIDER=reglas` obliga a usar solo reglas (más barato, pero la fuerza siempre vale 1).
- **El juez cambia el resultado:** en el caso sintético, etiquetas del kit 25,93 y solo reglas
  25,87. Por eso las mediciones de una serie deben usar el mismo juez (ver **Comparabilidad**).
- **Dónde:** `src/posiq/adapters/judge/`; nodo `judge` en `src/posiq/application/nodes/judge.py`.

## K

### Kit

Ver **Caso sintético (el kit)** y **Modo kit**.

## L

### Línea base

La primera medición de una marca. Es el punto de partida con el que se comparan las siguientes.
En la serie temporal sale marcada como «Línea base: es la primera medición de la serie.», no como
un aviso.

- **Dónde:** `MOTIVO_LINEA_BASE` en `src/posiq/domain/tracking.py`. ADR 0016.

### LLM (modelo de lenguaje grande)

Un modelo de IA que lee y escribe texto, como ChatGPT, Claude o DeepSeek. En posiq. hay dos usos:
los **motores** son LLM a los que preguntamos como lo haría un usuario, y otros LLM trabajan
dentro del sistema (juez de fallback, redacción del plan y de la propuesta). Dentro del sistema
siempre se llaman con `LLM.structured`, que devuelve datos validados y no texto libre, y solo
reciben cifras ya calculadas por el código.

- **Dónde:** el puerto `LLM` en `src/posiq/ports.py`; adaptadores en `src/posiq/adapters/llm/`.

### llms.txt

Un fichero de texto en la raíz de una web (`/llms.txt`) que resume para los modelos de IA qué hay
en el sitio y enlaza las páginas importantes. Es una convención reciente, no un estándar oficial.

- **Estado: en desarrollo.** Comprobar si existe es parte de la auditoría técnica (solo el contrato
  está en `develop`, PR #40, ADR 0019). posiq. todavía no lo comprueba.

## M

### Mapa de fuentes

Qué fuentes (dominios) citan los motores en un sector, con su tipo y su cuota de citas, en
general, por motor, por fase y por ciudad. Está **anonimizado**: una fuente solo entra si la citan
respuestas sobre al menos 2 marcas, y todas las webs propias se agregan en una sola entrada.

- **Ejemplo (caso sintético):** 1.631 citas; la primera entrada son las webs propias agregadas
  (11,3 %), seguidas de un directorio médico (8,6 %) y un medio de salud (8,5 %).
- **Dónde:** `src/posiq/domain/source_map.py`; `tests/golden/test_source_map_golden.py`. ADR 0010.
- **Estado:** el cálculo está en develop. Para usarlo con varios estudios del sector falta poder
  listarlos por sector en el repositorio (**PENDIENTE**).

### Margen de error

La mitad de la anchura del intervalo de confianza (la mayor de las dos mitades, porque el
intervalo no siempre es simétrico). Se lee «valor ± margen».

- **Ejemplo (caso sintético):** aparición espontánea de Alborada en ChatGPT 18 % ± 12 pp; global
  39 % ± 6 pp. «pp» son puntos porcentuales.
- **Dónde:** `Intervalo.margen` en `src/posiq/domain/stats_schemas.py` y `formato_margen` en
  `src/posiq/domain/stats.py`.

### Mitigación

La acción que proponemos cuando un asistente dice algo **incorrecto** de la marca. Va a la fuente
de la que sale el error: corregir la ficha en un directorio, corregir la web propia, responder en
un foro, pedir la corrección a un medio o, si no hay fuente, publicar el dato correcto con datos
estructurados.

- **Ejemplo (caso sintético):** ninguna, porque el kit no tiene inexactitudes de Alborada. Los
  casos de error solo están en tests con respuestas inventadas y marcadas.
- **Dónde:** `acciones_mitigacion` en `src/posiq/domain/accuracy.py`;
  `tests/domain/test_accuracy.py`. ADR 0011.

### Modo kit

El modo de estudio que usa las 624 respuestas sintéticas del kit en lugar de preguntar a los
motores. **Siempre es gratis**, aunque haya claves en el entorno: usa el `FixtureLLM` y el
`FixtureJudge`. Solo con `KIT_IA_REAL=true` usaría IA de pago sobre el kit. Solo admite el brief
de Alborada, porque es el único caso con datos.

- **Dónde:** `ModoEstudio` en `src/posiq/domain/schemas.py`; `src/posiq/adapters/engines/kit.py`;
  `tests/e2e/test_kit_sin_coste.py`. ADR 0018.

### Modo real

El modo de estudio que pregunta de verdad a las APIs de ChatGPT, Gemini, Perplexity y Claude, con
búsqueda web activada, y guarda los dominios que citan. Si hay clave de TypeSafe, juzga Jev con
DeepSeek de fallback; si solo hay clave de DeepSeek, DeepSeek es el único juez; si no hay claves o
`JUDGE_PROVIDER=reglas`, juzgan solo las reglas (ver **Juez**).

- **Estado: nunca se ha ejecutado.** Los adaptadores existen y están probados con respuestas
  simuladas de cada SDK, pero no hay claves. Los precios del código son provisionales. Con esos
  precios, las llamadas a los motores de un estudio del tamaño del kit cuestan unos 10,56 €; con
  el juez, el total va de 10,57 € (solo reglas) a 12,42 € (solo DeepSeek). Todo ello supera el
  tope de 5 € por estudio: habrá que subir el tope o reducir el estudio. Son estimaciones, no
  gastos reales (`docs/conceptos/kit-vs-real.md`, `src/posiq/application/estimate.py`,
  `docs/estado/C.md`).
- **Dónde:** `src/posiq/adapters/engines/` (`openai.py`, `gemini.py`, `perplexity.py`,
  `anthropic.py`); `scripts/smoke_engines.py`. ADR 0006.

### Motor

Cada asistente de IA consultado: **ChatGPT, Gemini, Perplexity y Claude**. Las métricas se dan
también por motor, porque cada uno se comporta distinto.

- **Ejemplo (caso sintético):** aparición espontánea de Alborada: Perplexity 65 %, Gemini 57 %,
  ChatGPT 18 %, Claude 15 % (ADR 0008).
- **Dónde:** `Motor` en `src/posiq/domain/schemas.py`.

## N

### Newcombe

Método para calcular el intervalo de confianza de la **diferencia entre dos tasas** (por ejemplo,
la aparición en Perplexity menos la de Claude, o la de este trimestre menos la del anterior).
Combina los dos intervalos de Wilson. Lo preferimos al método clásico (Wald) porque este falla con
tasas pequeñas.

- **Dónde:** `diferencia_proporciones` en `src/posiq/domain/stats.py`. ADR 0008.

## O

### Oportunidad de fuente

Una fuente que acompaña a los competidores más que a la marca en las respuestas espontáneas,
ponderada por lo importante que es en el sector. Se calcula `valor = cuota en el sector ×
(presencia con competidores − presencia con la marca)` y se clasifica como Alta, Media o Baja con
umbrales fijos.

- **Ejemplo (caso sintético):** la primera oportunidad de Alborada es wikipedia.org (Media). La
  lectura es que las fuentes que acompañan a Alborada son casi las de sus competidores: su
  problema es que aparece menos, no con qué fuentes.
- **Dónde:** `oportunidades_fuente` en `src/posiq/domain/source_map.py`. ADR 0010.
- **Estado:** el cálculo está en develop; en la API sale vacío hasta que se fusione
  `feature/C-diferencial-grafo` (**en desarrollo**).

## P

### Palanca

El tipo de intervención de una acción. Hay siete: `autoridad_terceros` (rankings, medios,
directorios), `contenido`, `entidad_datos` (perfil coherente y datos estructurados), `reputacion`,
`comunidades`, `tecnico` (que los bots puedan leer la web) y `medicion` (volver a medir). La
metodología del kit las llama «hipótesis de la industria, no garantías».

- **Dónde:** `Palanca` en `src/posiq/domain/schemas.py`; impacto supuesto de cada una en
  `IMPACTO_POR_PALANCA` (`src/posiq/domain/simulation.py`).

### Plan

El conjunto de acciones ordenadas en fases, con objetivos (KPI, valor actual, valor objetivo,
plazo) y un presupuesto estimado. Lo redacta un LLM a partir de los hallazgos ya calculados, pasa
por revisión humana y el código comprueba que respeta el presupuesto y las restricciones del
brief.

- **Dónde:** `Plan`, `Phase` y `validate_plan_against_brief` en `src/posiq/domain/schemas.py`;
  nodo `plan` en `src/posiq/application/nodes/plan.py`; pantalla «Plan» de la web.

### PlanGuard

Un juez de calidad del plan: hace cinco preguntas por acción (¿es específica?, ¿coherente con su
hallazgo?, ¿respeta las restricciones?, ¿es realista para el equipo?, calidad global). Es
orientativo y **no bloquea nada**.

- **Dónde:** `src/posiq/adapters/judge/plan_guard.py`; preguntas en
  `src/posiq/domain/plan_questions.py`. ADR 0007.
- **Estado:** sin claves no se ejecuta, así que en la demo `calidad_plan` sale vacío.

### Posición

Segundo componente del Score de Citación: en qué orden sale la marca entre las del sector
presentes en la respuesta. Ver **Score de Citación**.

### Presupuesto

En posiq. hay tres presupuestos distintos:

| Cuál | Qué es | Dónde |
|---|---|---|
| **Del estudio** | Tope de gasto en llamadas a IA por estudio: 5 € por defecto. Al superarlo, el estudio se para | `BUDGET_EUR_MAX` en `src/posiq/settings.py`; `src/posiq/adapters/budget.py` |
| **Del cliente** | Lo que el cliente puede gastar al año en el plan, según su brief | `BriefSummary.presupuesto_anual_eur` |
| **Del escenario** | Lo que el consultor fija para decidir qué acciones caben | `presupuesto_eur` en `src/posiq/domain/scenario_schemas.py` |

- **Ejemplo (caso sintético):** el brief de Alborada da 18.000–27.000 € al año y el plan de
  ejemplo cuesta 22.000 €.
- `GET /estimate` estima el coste de un estudio antes de lanzarlo (`src/posiq/application/estimate.py`).
  En modo kit es 0 €.

### Propuesta (`Proposal`)

El entregable final de un estudio: resumen ejecutivo, contexto, diagnóstico, competencia,
hallazgos, estrategia, plan, medición, riesgos, hoja de ruta y encargo (lo que pidió el cliente y
dónde se trata), y su exportación a Word. La simulación del plan se entrega junto a ella (campo
`simulacion` del estudio). Todas las cifras las calcula el código; el LLM solo redacta el texto a su
alrededor.

- **Dónde:** `Proposal` en `src/posiq/domain/schemas.py`; exportación en
  `src/posiq/adapters/export/docx.py`; campo `proposal` de `GET /studies/{id}`.

### Prompt espontáneo y asistido

La distinción más importante de la metodología.

- **Espontáneo:** la pregunta **no nombra** la marca (instanciación `generico` o `ciudad`). Mide si
  el asistente la conoce y la propone por iniciativa propia.
- **Asistido:** la pregunta **nombra** la marca (`marca` o `par`). La marca aparece casi siempre
  porque la pregunta la nombra; mide qué dice de ella, no si la descubre.
- Se calculan **siempre por separado**, y el Score de Citación usa **solo prompts espontáneos**.
- **Dónde:** `ESPONTANEAS` y `tipo_de_instanciacion` en `src/posiq/domain/schemas.py`;
  `data/kit/03_Documentacion/02_Metodologia_GEO.md` (§8).

### Propio y ganado

Clasificación de cada fuente citada. **Propio** es la web de una marca (por el catálogo o por el
dominio de la marca). **Ganado** es todo lo demás: medios, rankings, directorios, reseñas, foros,
es decir, lo que otros dicen de ti.

- **Dónde:** `src/posiq/domain/source_map.py`. ADR 0010.

## R

### Re-medición

Volver a medir la misma marca más tarde (la idea es cada trimestre) para ver si algo ha cambiado.
Crea un estudio nuevo, que no sobrescribe el anterior, y calcula la diferencia con él
(`metrics_delta`). En modo kit la diferencia es 0: demuestra que la medición se repite igual, no
que haya una mejora.

- **Dónde:** `POST /studies/{id}/remeasure` en `src/posiq/interfaces/api/main.py`; `diff_metrics`
  en `src/posiq/domain/metrics.py`; significancia en `significancia_remedicion`
  (`src/posiq/domain/stats.py`).
- **Estado:** el endpoint está en develop, pero hoy **regenera** el banco de prompts. En modo real
  eso cambiaría la huella y la serie saldría «no comparable». Reutilizar el banco anterior está
  **en desarrollo** (rama `feature/C-diferencial-grafo`). En la web, el botón «Volver a medir» ya
  está en develop (`apps/web/src/pages/DiagnosisPage.tsx`). Desde la PR #38 pide confirmar el coste
  estimado antes de re-medir (con `GET /estimate`, marcado como aproximado).

### Reglas (juez por reglas)

Ver **Juez** y **Capa determinista y capa no determinista**.

### robots.txt y bots de IA

`robots.txt` es el fichero de una web que dice qué rastreadores pueden leer qué páginas. Los
asistentes tienen sus propios **bots** (por ejemplo GPTBot y OAI-SearchBot de OpenAI, ClaudeBot de
Anthropic, PerplexityBot de Perplexity, Google-Extended de Google). Si la web los bloquea, ese
asistente no puede leerla.

- **Estado: en desarrollo.** La auditoría que lo comprobaría solo tiene el contrato (en `develop`, PR #40,
  ADR 0019). Hoy, la palanca `tecnico` del plan puede
  *recomendar* revisarlo, pero posiq. no lo comprueba.

## S

### Score de Citación

Un número de 0 a 100 que resume lo visible y bien recomendada que está una marca en los
asistentes. Se calcula por marca y por marca y motor. Los pesos y la fórmula son los de la §7 de
la metodología del kit (`data/kit/03_Documentacion/02_Metodologia_GEO.md`). Que solo cuenten los
**prompts espontáneos** es una decisión nuestra, basada en la §8 (si se mezclan, los prompts que
nombran la marca inflan la visibilidad). La fórmula vive en un solo sitio del código:

| Componente | Máximo | Cálculo |
|---|---|---|
| **Aparición** | 30 | 30 × tasa de aparición |
| **Posición** | 20 | 20 × peso medio de posición / 3 (1.ª = 3; 2.ª–3.ª = 2; 4.ª o más = 1; no aparece = 0) |
| **Fuerza** | 30 | 30 × fuerza media / 3 (no aparece = 0; si la media es negativa, vale 0) |
| **Calidad de fuente** | 20 | 20 × tasa de aparición × calidad media de las fuentes de sus apariciones |

Las medias de posición y fuerza son sobre todas las evaluaciones (quien no aparece aporta 0).
Calidad por tipo de fuente: ranking / institución 1,0; medio 0,9; web propia 0,7; directorio y
reseñas 0,6; red social / foro 0,4; sin fuente 0,2. Si el tipo de fuente no está resuelto, se usa
la calidad media de las fuentes que citó esa respuesta en el catálogo (0,2 si no citó ninguna).
Con cero evaluaciones no hay score («sin datos»), nunca 0.

**Ejemplo (caso sintético):** 240 evaluaciones espontáneas de Alborada.

| Componente | Valor | Lectura |
|---|---|---|
| Aparición | 11,62 | aparece en el 39 % de las respuestas |
| Posición | 4,72 | cuando aparece, suele salir entre la 2.ª y la 4.ª |
| Fuerza | 3,92 | la nombran, pero apenas la recomiendan (fuerza media ≈ 1) |
| Calidad de fuente | 5,67 | calidad media de sus fuentes ≈ 0,73 |
| **Score** | **25,93** | 8.ª de 10 |

- **Dónde:** `src/posiq/domain/scoring.py` (fórmula y `QUALITY_BY_TYPE`, versión `SCORE_VERSION`
  1.0); `tests/golden/test_demo_canonico.py`; pantalla «Diagnóstico» de la web.

### Serie temporal

La sucesión de mediciones de una marca (línea base, re-mediciones). Para cada par de mediciones
seguidas comprueba si son comparables, calcula los cambios de score, aparición, puesto y
diferencia frente a la **media** de los competidores (en el caso sintético, 25,93 frente a 34,52:
−8,59), cada uno con su intervalo, y solo cuenta como noticia los cambios **fuera del margen de
error**. Si no hay ninguno, dice exactamente «Sin cambios fuera del margen de error».

- **Ejemplo (caso sintético):** el kit medido dos veces da 8 cambios calculados, todos de 0, y
  ninguno significativo («Sin cambios fuera del margen de error»). Con un segundo punto inventado
  (40 no-apariciones pasan a aparecer en 1.ª posición como recomendación activa, fuerza 3) sale
  +15,88 [+9,51; +22,47] y del 8.º al 3.er puesto.
- **Dónde:** `construir_serie` en `src/posiq/domain/tracking.py`;
  `tests/golden/test_serie_alborada.py`. ADR 0016.
- **Estado:** el cálculo está en develop. El endpoint `GET /brands/{id}/serie` está
  **PENDIENTE** (aún no hay código en la API: `docs/estado/C.md`, «Siguiente tarea»). La vista de
  seguimiento en la web ya está en develop (PR #38), pero todavía no tiene a qué llamar: muestra
  «Seguimiento no disponible todavía».

### Significancia

Una diferencia es **significativa** si su intervalo de confianza al 95 % no contiene el 0: es
decir, si no se puede explicar por azar de la muestra. No damos p-valores, para que nunca puedan
contradecir al intervalo.

- **Ejemplo (caso sintético):** la diferencia de score con el líder, 40,53 [35,34–45,56], es
  significativa. Las reglas `F-fuente-lider` y `F-menciones-negativas` no admiten contraste
  porque son recuentos, no estimaciones.
- **Dónde:** `significancia_hallazgos` y `significancia_remedicion` en `src/posiq/domain/stats.py`.
  ADR 0008.

### Simulación

Estimación de cuánto podría subir el score si se ejecuta el plan, con un rango (mínimo, esperado,
máximo) por fase. Usa supuestos explícitos: una tabla de mejora por palanca y tamaño, rendimientos
decrecientes (la k-ésima acción sobre un mismo segmento aporta solo 0,6^k de su mejora) y un tope
de +20 puntos porcentuales (pp) en la tasa de aparición de cada segmento, sin pasar del 95 % de
aparición (`TOPE_SEGMENTO`, `TASA_MAXIMA`); después se recalcula el score con la misma fórmula.
Solo se mueve la aparición espontánea: la posición, la fuerza y la calidad de las apariciones se
mantienen como hoy, y las acciones de medición no suman. **No son +20 puntos de score.** Siempre va con esta advertencia: es una
estimación ilustrativa, no una predicción, y no estima visitas ni ventas.

- **Ejemplo (caso sintético):** 25,93 → 30,77 (27,77–33,95), es decir, 25,9 → 30,8.
- **Dónde:** `src/posiq/domain/simulation.py` (`IMPACTO_POR_PALANCA`, `ADVERTENCIA`, `SUPUESTOS`);
  `tests/golden/test_simulation_golden.py`; campo `simulacion` de `GET /studies/{id}`. ADR 0007.
- **Límite:** la tabla de impacto es una hipótesis del equipo; hay que revisarla con
  re-mediciones reales.

## T

### Traza (`Trace`)

El registro de cada llamada externa: estudio, nodo, modelo, versión del prompt, tokens (los trozos
de texto por los que cobra un modelo) de entrada y salida, coste en euros, duración y fecha. Se registra también lo pagado en llamadas que fallan.
Las trazas suman el coste del estudio y alimentan el presupuesto.

- **Dónde:** `Trace` en `src/posiq/domain/schemas.py`; `GET /studies/{id}/traces`; panel de trazas
  de la web. ADR 0018.
- En modo fixture las trazas marcan 0 tokens y 0 €: no hay llamadas de pago.

## W

### Web propia (cuota de)

Qué parte de las citas de las respuestas donde aparece la marca van a su propia web. Sirve para
saber si su web es una fuente que los asistentes usan.

- **Ejemplo (caso sintético):** `alboradavision.example` recibe 33 de 564 citas (5,9 %), por encima
  de la media de sus competidores (3,3 %): su web no es el problema.
- **Dónde:** `hallazgo_web_propia` en `src/posiq/domain/source_map.py` (hallazgo `F-web-propia`).
  También es un indicador adelantado de la serie. ADR 0010.

### Wilson

Método para calcular el intervalo de confianza de una **tasa** (por ejemplo, el % de respuestas en
las que aparece la marca). Lo preferimos al método clásico (Wald) porque con tasas pequeñas Wald
da límites negativos o un intervalo de anchura cero.

- **Ejemplo (caso sintético):** en Barcelona, Alborada aparece en 1 de 24 respuestas: 4 %
  [1–20 %]. Con tan pocas respuestas, el margen es grande.
- **Dónde:** `wilson` en `src/posiq/domain/stats.py`. ADR 0008.

---

## Qué está hecho y qué no (resumen para no equivocarse en la presentación)

| Pieza | Estado |
|---|---|
| Score, métricas, hallazgos, simulación, plan, propuesta y Word sobre el kit | En develop |
| Rigor estadístico, escenarios, mapa de fuentes, exactitud, competidores declarados, serie temporal (cálculo en `domain/`) | En develop, con tests golden |
| Esos mismos bloques en la API (`rigor`, `escenarios`, `oportunidades_fuente`, `exactitud`) | En desarrollo (`feature/C-diferencial-grafo`); en develop los campos existen y salen `null` |
| Campo de competidores declarados en la API | En desarrollo: todavía no existe en la API de develop (lo añade `feature/C-diferencial-grafo`) |
| Cuentas y propiedad de estudios en la API | En develop |
| Botón «Volver a medir» en la web | En develop |
| Login, vista de seguimiento y re-medición con confirmación de coste en la web | En develop (PR #38); la vista de seguimiento, sin datos hasta que exista `GET /brands/{id}/serie` |
| Endpoint `GET /brands/{id}/serie` | PENDIENTE (sin código en la API) |
| Re-medición que reutiliza el banco de prompts | En desarrollo |
| Juez dentro de la regla de comparabilidad | PENDIENTE |
| Auditoría técnica de la web (robots.txt, bots de IA, llms.txt, JSON-LD, Content-Signal) | En desarrollo: solo el contrato está en develop (PR #40, ADR 0019); sin análisis |
| Consenso del juez (`ConsensusJudge`) dentro del flujo | PENDIENTE (existe, pero `build_judge` no lo usa) |
| Jev y fallback con claves reales; calibración del juez | PENDIENTE |
| Modo real con las APIs de los motores | Nunca ejecutado |

## Dónde se comprueba

Todas las cifras de este glosario salen de estos ficheros. Para ejecutar los tests sin gastar
nada (con las claves vacías y `LLM_PROVIDER=fixture`):

```sh
python -m uv run pytest tests/golden tests/domain
```

| Tema | Código | Test o documento |
|---|---|---|
| Score de Citación y cifra canónica | `src/posiq/domain/scoring.py` | `tests/golden/test_demo_canonico.py`, `tests/e2e/test_demo_canonica_api.py` |
| Métricas y re-medición entre dos estudios | `src/posiq/domain/metrics.py` | `tests/golden/test_metrics_golden.py`, `tests/domain/test_metrics.py` |
| Hallazgos y confianza | `src/posiq/domain/findings.py`, `src/posiq/domain/evidence.py` | `tests/domain/test_findings.py`, `tests/domain/test_evidence.py` |
| Detección por reglas | `src/posiq/domain/detection.py` | `tests/golden/test_detection_golden.py` |
| Intervalos, Wilson, bootstrap, Newcombe, significancia | `src/posiq/domain/stats.py`, `src/posiq/domain/stats_schemas.py` | `tests/golden/test_rigor_alborada.py`, `tests/domain/test_stats.py`, ADR 0008 |
| Serie temporal, comparabilidad, línea base, indicadores | `src/posiq/domain/tracking.py`, `src/posiq/domain/tracking_schemas.py` | `tests/golden/test_serie_alborada.py`, `tests/domain/test_tracking.py`, ADR 0016 |
| Simulación | `src/posiq/domain/simulation.py` | `tests/golden/test_simulation_golden.py`, ADR 0007 |
| Escenarios y preajustes | `src/posiq/domain/scenarios.py` | `tests/golden/test_scenarios_golden.py`, `tests/domain/test_scenarios.py`, ADR 0009 |
| Mapa de fuentes, propio/ganado, oportunidades, web propia | `src/posiq/domain/source_map.py` | `tests/golden/test_source_map_golden.py`, ADR 0010 |
| Exactitud de marca, «a revisar», mitigación | `src/posiq/domain/accuracy.py`, `src/posiq/application/accuracy.py` | `tests/golden/test_accuracy_golden.py`, `tests/domain/test_accuracy.py`, ADR 0011 |
| Competidores declarados frente a los de la IA | `src/posiq/domain/competitor_gap.py` | `tests/golden/test_competitor_gap_golden.py`, ADR 0012 |
| Encargo y cobertura del brief | `src/posiq/domain/brief_coverage.py` | `tests/golden/test_brief_coverage_golden.py`, ADR 0013 |
| Juez (reglas, Jev, fallback, consenso) | `src/posiq/domain/judge_questions.py`, `src/posiq/domain/consensus.py`, `src/posiq/adapters/judge/` | `tests/golden/test_judge_calibration.py`, `tests/domain/test_consensus.py`, ADR 0003 y 0014 |
| Modo kit gratis, trazas y estimación de coste | `src/posiq/adapters/llm/fixture.py`, `src/posiq/application/estimate.py`, `src/posiq/adapters/budget.py` | `tests/e2e/test_kit_sin_coste.py`, ADR 0018 |
| Motores reales | `src/posiq/adapters/engines/` | ADR 0006 (sin probar en real) |
| Cuentas y propiedad | `src/posiq/interfaces/api/auth.py`, `src/posiq/application/accounts.py` | ADR 0015 |
| Contratos | `src/posiq/domain/schemas.py`, `src/posiq/ports.py` | `tests/domain/test_schemas.py`, `CONTRIBUTING.md` |
| Metodología del kit | — | `data/kit/03_Documentacion/02_Metodologia_GEO.md`, `data/kit/03_Documentacion/03_Diccionario_de_datos.md` |
| Estado por zona | — | `docs/estado/A.md` … `docs/estado/E.md` |

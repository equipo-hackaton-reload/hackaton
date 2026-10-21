# Rigor estadístico y seguimiento con método

Este documento explica dos ideas que diferencian a posiq.:

1. **Cada cifra debe ir con su margen de error.** Un score sin margen puede engañar. (El cálculo
   del margen está hecho; mostrarlo en la API, la web y el Word está **PENDIENTE**, ver §0.)
2. **posiq. no vende un score suelto, vende un seguimiento.** Se mide una línea base, se vuelve a
   medir con el mismo método y solo se informa de lo que cambia de verdad.

Está escrito para el equipo que presenta y redacta los entregables, y para el jurado. Cada cifra y
cada regla se pueden comprobar en el código o en un test: la ruta va al lado y la lista completa
está en [Dónde se comprueba](#dónde-se-comprueba).

---

## 0. Antes de nada: caso sintético frente a medición real

> **Todas las cifras de este documento son nuestro método aplicado al caso sintético del reto.**

El kit del reto es ficticio. Lo dice su guía (`data/kit/00_LEEME_Guia_del_kit.md`): «Todos los
datos, marcas, personas y cifras son ficticios y sintéticos». Por tanto:

- Clínica Alborada Visión y sus competidores **no existen**.
- Las 624 respuestas de los asistentes **las escribieron los organizadores**. No son respuestas
  reales de ChatGPT, Gemini, Perplexity ni Claude.
- Los dominios de las fuentes terminan en `.example`.

Cuando aquí aparece «25,9 [21,6–30,1]», «18 % en las respuestas sintéticas atribuidas a ChatGPT» o
«8.ª de 10», hay que leerlo así:
*esto es lo que calcula nuestro método con los datos sintéticos del kit*. Sirve para demostrar que
el método funciona y que es reproducible. **No dice nada del mercado real.**

**El modo real (llamar a las APIs de los motores con búsqueda web) todavía no se ha ejecutado
nunca.** Ninguna cifra de este documento sale de una medición real.

### Qué está hecho y qué no

| Pieza | Estado |
|---|---|
| Cálculo de intervalos y significancia (`domain/stats.py`) | Hecho y fijado por tests golden |
| Serie temporal de seguimiento (`domain/tracking.py`) | Hecho y fijado por tests golden |
| Re-medición de un estudio (`POST /studies/{id}/remeasure`) | Hecho en la API; solo probado en modo kit (respuestas fijas, ver §7.3). Nunca ejecutado con motores reales |
| Mostrar los intervalos en la API (`GET /studies/{id}`, bloque `rigor`) | **PENDIENTE.** El campo existe pero hoy sale vacío (`null`): el grafo aún no lo rellena |
| Mostrar intervalos y serie en la web y en el Word | **PENDIENTE** |
| Endpoint de la serie (`GET /brands/{id}/serie`) | **PENDIENTE** (siguiente tarea de la zona C, `docs/estado/C.md`) |
| Que la re-medición real reutilice el mismo banco de preguntas | **PENDIENTE** (ver §6.3) |
| Exigir el mismo juez para comparar dos mediciones | **PENDIENTE** (planificado para la ola 2; hoy la regla de comparabilidad no mira el juez, ver §6.3) |

---

## 1. Por qué un score sin margen engaña

posiq. resume la visibilidad de una marca en el **Score de Citación**, de 0 a 100. Suma cuatro
componentes: si la marca aparece (30 puntos), en qué posición (20), con qué fuerza la recomiendan
(30) y la calidad de la fuente que la apoya (20). La fórmula está en `src/posiq/domain/scoring.py`.

Ese número sale de **una muestra** de respuestas, no de todas las respuestas posibles. Los
asistentes de IA no contestan siempre lo mismo: si repites la misma pregunta, la respuesta cambia.
Así que el score que medimos es una estimación, y toda estimación tiene un error.

Un ejemplo con el caso sintético. Alborada aparece en el 18 % de las respuestas sintéticas
atribuidas a ChatGPT y en el 15 % de las atribuidas a Claude. ¿ChatGPT la ve más que Claude? Con 60 respuestas por motor, el margen de
cada cifra es de unos ±11–12 puntos porcentuales. Esa diferencia de 3 puntos **es ruido**: no se
puede afirmar que un motor la vea más que el otro.

Sin margen, un informe diría «ChatGPT te ve más que Claude» y el cliente actuaría sobre algo que no
existe. Con margen, decimos lo que sabemos y lo que no.

Por eso la regla de diseño de posiq. es: **ninguna cifra importante debe salir sin su margen de
error, y ninguna diferencia se presenta como real si cabe dentro de ese margen** (ADR 0008,
`docs/adr/0008-rigor-estadistico.md`). El cálculo está hecho en `src/posiq/domain/stats.py`;
mostrarlo en la API, la web y el Word está **PENDIENTE** (hoy el bloque `rigor` de
`GET /studies/{id}` sale vacío, ver §0).

---

## 2. El intervalo de confianza, explicado sin estadística

Un **intervalo de confianza al 95 %** es un rango de valores. Se escribe así:

> **25,9 [21,6–30,1]**

Se lee: «hemos medido 25,9; con los datos que tenemos, el valor de verdad está, con un 95 % de
confianza, entre 21,6 y 30,1».

Una forma intuitiva de pensarlo: si repitiéramos el estudio entero muchas veces, con nuevas
respuestas de los asistentes, el método acertaría (el rango contendría el valor de verdad) en 95 de
cada 100 repeticiones.

Tres ideas clave:

- **El margen** es la distancia mayor entre la cifra medida y uno de los dos límites del
  intervalo (`margen` en `src/posiq/domain/stats_schemas.py`). En las tasas pequeñas el intervalo
  no es simétrico: en las respuestas sintéticas atribuidas a ChatGPT, 18 % [11–30 %] tiene +12 pp
  hacia arriba y −7 pp hacia abajo, y el margen se da como ± 12 pp. (*pp* = puntos porcentuales:
  pasar del 18 % al 30 % es subir 12 pp.)
- **Más datos, menos margen.** El margen baja con la raíz cuadrada del número de respuestas: para
  reducirlo a la mitad hacen falta unas cuatro veces más respuestas. Se ve en el caso sintético:
  con 60 respuestas por motor el margen de la aparición es de ±11–13 pp; con las 240 juntas, de
  ±6 pp.
- **Nivel fijo del 95 %.** Es el estándar habitual y está fijado en el código (`NIVEL = 0.95` en
  `src/posiq/domain/stats.py`).

posiq. usa dos métodos para calcular intervalos, según el tipo de cifra.

### 2.1 Para la aparición: el intervalo de Wilson

La **tasa de aparición** es una proporción: en cuántas respuestas de cada 100 aparece la marca.
Para las proporciones usamos el **intervalo de Wilson**.

¿Por qué Wilson y no la fórmula «de libro» (la de Wald, la que se enseña primero)? Porque la de
Wald falla con tasas pequeñas o muestras pequeñas: puede dar límites negativos (una tasa por debajo
de 0 %, que es imposible) o un intervalo de ancho cero. Wilson no tiene ese problema.

Ejemplo del caso sintético: en Barcelona, Alborada aparece en **1 de 24** respuestas. Wilson da
**4 % [1–20 %]**. Es un intervalo ancho, y está bien que lo sea: con 24 respuestas sabemos poco.

posiq. calcula Wilson para la aparición espontánea y la asistida, en cada segmento: global, por
motor, por fase del embudo, por ciudad, por perfil y por familia de preguntas
(`intervalos_aparicion` y `aparicion_por_motor` en `src/posiq/domain/stats.py`). Qué significa cada
término (más detalle en [score-de-citacion.md](score-de-citacion.md)):

- **Aparición espontánea**: la pregunta **no** nombra la marca («¿qué clínica me recomiendas para
  operarme de miopía en Madrid?»). Es la que cuenta para el score.
- **Aparición asistida**: la pregunta **sí** nombra la marca («¿qué opinas de Clínica Alborada?»).
- **Fase del embudo**: el momento de la compra en que está quien pregunta, desde el
  **descubrimiento** (todavía explora) hasta la **decisión** (está a punto de elegir).
- **Perfil**: el tipo de paciente que simula la pregunta.
- **Familia de preguntas**: el grupo temático al que pertenece la pregunta en el banco.
- **Líder**: la marca con más Score de Citación del mercado del estudio.

**Caso sintético del reto, aparición espontánea por motor** (`tests/golden/test_rigor_alborada.py`):

| Motor (n = 60 respuestas) | Aparición | Intervalo 95 % | Margen |
|---|---|---|---|
| ChatGPT | 18 % | [11–30 %] | ± 12 pp |
| Claude | 15 % | [8–26 %] | ± 11 pp |
| Gemini | 57 % | [44–68 %] | ± 13 pp |
| Perplexity | 65 % | [52–76 %] | ± 13 pp |
| **Global (n = 240)** | **39 %** | **[33–45 %]** | **± 6 pp** |

Por ciudad (n = 24): Madrid 54 % [35–72 %] y Barcelona 4 % [1–20 %].

Lectura: ChatGPT y Claude se solapan, así que no se distinguen entre sí. Gemini y Perplexity
también se solapan entre ellos. Pero el grupo de arriba (Gemini, Perplexity) y el de abajo
(ChatGPT, Claude) no se tocan: esa diferencia sí es real (dentro del caso sintético).

### 2.2 Para el score: el bootstrap

El Score de Citación no es una proporción simple: combina cuatro componentes. No hay una fórmula
cerrada para su intervalo. Por eso usamos el **bootstrap**, una técnica que simula repetir el
estudio usando solo los datos que ya tenemos:

1. Tenemos 240 respuestas espontáneas (en el caso sintético).
2. Sacamos 240 al azar **con reemplazo**: algunas salen dos veces y otras ninguna. Es una
   «réplica» del estudio.
3. Recalculamos el score de esa réplica **con la misma función de siempre** (`score_citacion` de
   `scoring.py`). La fórmula no se duplica en ningún sitio.
4. Repetimos 2000 veces. Tenemos 2000 scores posibles.
5. Los ordenamos. Descartamos el 2,5 % más bajo y el 2,5 % más alto. Lo que queda es el intervalo
   al 95 %.

Dos decisiones de diseño (ADR 0008):

- **Semilla fija** (`SEMILLA_BOOTSTRAP = 20261021`) y **2000 réplicas** (`REPLICAS_BOOTSTRAP`). El
  azar del bootstrap es siempre el mismo azar, así que **el mismo estudio da siempre el mismo
  intervalo**. Es reproducible y los tests lo pueden fijar. Con 2000 réplicas, el error propio del
  método es de centésimas: no cambia la primera cifra decimal.
- **La unidad que se remuestrea es la respuesta** (cada ejecución de una pregunta en un motor).

**Caso sintético del reto:** el Score de Citación de Alborada es **25,93**, con intervalo
**25,9 [21,6–30,1]** sobre 240 respuestas espontáneas (`tests/golden/test_rigor_alborada.py`).
El intervalo contiene la cifra canónica 25,93 (`tests/golden/test_demo_canonico.py`).

Score por motor, mismo método:

| Motor | Score [IC 95 %] |
|---|---|
| ChatGPT | 11,4 [5,9–17,7] |
| Claude | 9,7 [4,2–15,7] |
| Gemini | 38,5 [30,3–47,1] |
| Perplexity | 44,2 [35,6–52,2] |

(Fuente: tabla del ADR 0008, generada por `scripts/informe_rigor.py`; el test fija la fila de
Claude.)

### 2.3 Advertencia: las respuestas no son del todo independientes

Wilson y el bootstrap por respuestas suponen que cada respuesta es independiente de las demás. No
es del todo cierto: cada pregunta se lanza **3 veces** en cada motor y esas tres respuestas se
parecen entre sí. Eso hace que los intervalos sean **algo optimistas** (más estrechos de lo que
deberían).

Para medir cuánto, el código permite remuestrear **preguntas enteras** con todas sus respuestas
(`unidad="prompt"` en `intervalo_score`). En el caso sintético:

| Unidad de remuestreo | IC 95 % del score |
|---|---|
| Respuesta (por defecto) | [21,6–30,1] |
| Pregunta entera | **[19,7–31,8]** |

El intervalo se ensancha, como se esperaba (`test_ic_del_score_por_prompt_es_mas_ancho`). Lo
contamos abiertamente: el intervalo de referencia es el de la respuesta, y el de la pregunta es la
prueba de sensibilidad.

---

## 3. Significancia: cuándo una diferencia es real

Muchas afirmaciones de una propuesta son **diferencias**: «Perplexity te ve más que Claude», «el
líder te saca 40 puntos», «este trimestre has subido». Una diferencia también tiene margen de
error.

**Regla de posiq.:** una diferencia es **significativa** si y solo si su intervalo al 95 % **no
contiene el 0**. Si contiene el 0, no podemos descartar que la diferencia real sea nula. No damos
p-valores, para que nunca puedan contradecir al intervalo (`src/posiq/domain/stats.py`).

«**Fuera del margen de error**» es la forma corta de decir lo mismo: el cambio o la diferencia es
significativa. «**Dentro del margen de error**» quiere decir que puede ser ruido.

### 3.1 Qué método se usa en cada caso

| Qué se compara | Método | Por qué |
|---|---|---|
| Dos tasas de aparición (por ejemplo, dos motores, o antes y después) | **Newcombe** (método 10, «hybrid score»), que combina los dos intervalos de Wilson | Mismo motivo que Wilson: la fórmula de libro falla con tasas pequeñas |
| Score de dos marcas del **mismo** estudio | Bootstrap **emparejado**: en cada réplica se remuestrean las mismas respuestas para las dos marcas | Las dos marcas se evalúan en las mismas respuestas |
| Score de la misma marca en **dos** estudios (re-medición) | Bootstrap **independiente**: cada estudio se remuestrea por separado | Son muestras distintas |

Funciones: `diferencia_proporciones`, `diferencia_scores` y `significancia_remedicion` en
`src/posiq/domain/stats.py`.

### 3.2 La significancia de los hallazgos

Los **hallazgos** son las conclusiones del diagnóstico («Claude casi no te ve», «el líder te saca
mucha ventaja»…). Cada uno lleva su contraste (`significancia_hallazgos`). Dos hallazgos no admiten
contraste, y el sistema lo dice en lugar de inventarse uno:

- **Fuente del líder**: es un recuento sin tasa de referencia con la que comparar.
- **Menciones negativas**: es un recuento de casos concretos; basta con un caso para que exista.

**Caso sintético del reto** (`tests/golden/test_rigor_alborada.py`): 6 de los 7 hallazgos admiten
contraste y los 6 son significativos al 95 %.

| Hallazgo | Diferencia [IC 95 %] | ¿Significativo? |
|---|---|---|
| Motor débil (Perplexity − Claude) | 0,50 [0,33–0,63] | Sí |
| Barcelona (tasa − umbral del 30 %) | −0,26 [−0,29; −0,10] | Sí |
| Brecha con el líder (puntos de score) | 40,53 [35,34–45,56] | Sí |
| Caída del embudo (descubrimiento − decisión) | 0,197 [0,037–0,329] | Sí, pero frágil (ver abajo) |
| Asistida frente a espontánea | 0,61 [0,54–0,67] | Sí |
| Recomendación débil (fuerza media − 1,5, ver nota) | −0,49 [−0,50; −0,47] | Sí |
| Fuente del líder | — | Sin contraste |

Nota sobre la recomendación débil. La **fuerza** de una aparición va de −1 a 3: **3** = recomendación
principal, **2** = recomendación positiva secundaria, **1** = mención neutra, **0** = no aparece,
**−1** = aparece con advertencia o percepción negativa (`data/kit/03_Documentacion/02_Metodologia_GEO.md`;
`MAX_FUERZA = 3` en `src/posiq/domain/scoring.py`). El hallazgo se dispara cuando la fuerza media de
las apariciones espontáneas está por debajo de **1,5**, un umbral fijo (`MAX_FUERZA_DEBIL` en
`src/posiq/domain/findings.py`; ADR 0008, línea 52). En el caso sintético la media está cerca de 1
(«la nombran, pero apenas la recomiendan»), así que la diferencia con 1,5 es de −0,49.

**Un caso que hay que contar con cuidado.** Si se remuestrean preguntas enteras (§2.3), la caída
del embudo **deja de ser significativa**: su intervalo pasa a [−0,08–0,44], que contiene el 0. La
fase de decisión tiene solo 4 preguntas. Conclusión honesta: «la visibilidad cae de descubrimiento
a decisión» es un **indicio**, no una conclusión firme; hay que confirmarlo con más preguntas de
decisión (ADR 0008, «Límites»). La brecha con el líder ([33,9–47,2]) y Perplexity − Claude
([0,32–0,68]) siguen siendo significativas con ese método.

---

## 4. El seguimiento con método

Una sola medición es una foto. Lo que el cliente quiere saber es **si lo que hace funciona**. Para
eso posiq. propone un seguimiento en tres pasos (ADR 0016, `docs/adr/0016-seguimiento-con-metodo.md`):

1. **Línea base.** La primera medición. Es el punto de partida; todavía no hay con qué comparar.
2. **Re-medición.** Cada cierto tiempo se vuelve a medir **con el mismo método**: mismo banco de
   preguntas, mismos motores, misma versión de la fórmula.
3. **Informe de cambios.** Solo se informa de lo que sale del margen de error, y se compara con los
   competidores.

Técnicamente, cada medición es un estudio. La función `construir_serie` de
`src/posiq/domain/tracking.py` toma varios estudios de una marca, los ordena por fecha y produce la
**serie** (`SerieMarca`): los puntos, los cambios, los indicadores adelantados y un resumen en
texto.

La API ya permite lanzar una re-medición (`POST /studies/{id}/remeasure`): crea un estudio nuevo
con el mismo brief y el mismo mercado confirmado. El endpoint que devuelve la serie
(`GET /brands/{id}/serie`) está **PENDIENTE**.

### 4.1 Comparabilidad: qué tiene que coincidir

Dos mediciones solo se pueden comparar si se midieron igual. Si cambia lo que se pregunta o cómo se
puntúa, un cambio de score no se puede atribuir a la marca. Por eso cada punto de la serie se
compara con el anterior y la función `comparabilidad` decide:

| Qué cambia entre dos mediciones | Resultado |
|---|---|
| Versión de la metodología (hoy `reload-geo-2026`) | **No comparable.** No se calcula ningún cambio |
| Versión de la fórmula del score (hoy `1.0`) | **No comparable** |
| Banco de preguntas (su huella, ver abajo) | **No comparable** |
| Conjunto de motores (por ejemplo, se quita Claude) | **No comparable** |
| El modelo concreto de un motor (por ejemplo, una versión nueva de ChatGPT) | **Comparable, con aviso:** «parte del cambio puede deberse al modelo» |
| El modelo consta en una medición y en la otra no | Comparable, con aviso |
| Las marcas del mercado (entra o sale un competidor) | El score y la aparición **sí** se comparan. El puesto y la diferencia frente a los competidores **no** |
| El juez que decide la fuerza, el tipo de mención y el apoyo en fuentes (aparición y posición las deciden siempre las reglas) | **PENDIENTE** (planificado para la ola 2; hoy la regla de comparabilidad no mira el juez, ver §6.3) |

Cuando no es comparable, el sistema **dice por qué** y no calcula ningún cambio. Mejor no decir
nada que decir algo falso.

**¿Por qué importa el mercado?** El puesto y la media de los competidores dependen de quién esté en
el mercado. Sin esta regla, un mismo score (25,93 → 25,93) podría pasar de 8.ª de 10 a 2.ª de 4
solo porque se han quitado marcas, y saldría como mejora (ADR 0016).

**La huella del banco de preguntas.** Para saber si el banco es el mismo sin compararlo pregunta a
pregunta, se calcula una **huella**: un código que resume todo lo que se pregunta
(plantilla, familia, fase, instanciación —espontánea o asistida—, perfil, ciudad, texto exacto,
marcas nombradas y prioridad). Se calcula con SHA-256 y se guarda como `sha256:` seguido de los 16
primeros caracteres hexadecimales.
Si cambia una sola palabra de una pregunta, la huella cambia. No depende del orden de las
preguntas (`huella_banco` en `tracking.py`).

### 4.2 Qué cambios se calculan

Entre dos mediciones comparables consecutivas se calculan estos cambios (`CambioSerie` en
`src/posiq/domain/tracking_schemas.py`):

| Métrica | Qué mide | Método |
|---|---|---|
| `score` | El Score de Citación de la marca | Bootstrap independiente |
| `aparicion_espontanea:global` | Aparición sin nombrar la marca, en total | Newcombe |
| `aparicion_espontanea:<Motor>` | Lo mismo, en cada motor | Newcombe |
| `posicion` | Puesto en el ranking del mercado (negativo = mejora) | Bootstrap |
| `diferencia_vs_competidores` | Score de la marca menos la media del resto del mercado | Bootstrap |

### 4.3 Comparación frente a competidores

Una subida del score no es buena noticia si todos los competidores han subido más. Por eso la serie
mide dos cosas relativas al mercado:

- **El puesto** en el ranking (1 = primero).
- **La diferencia frente a la media de los competidores**: el score de la marca menos la media del
  score del resto. Negativa = por debajo de la media.

Para su margen de error, en cada réplica del bootstrap se recalcula el score de **todas** las
marcas sobre las mismas respuestas, con la misma fórmula (`score_from_profile`), y de ahí sale el
puesto y la diferencia.

**Caso sintético del reto** (`tests/golden/test_serie_alborada.py`): Alborada tiene 25,93, es la
**8.ª de 10**, la media de sus competidores es 34,52 y su diferencia es **−8,59** puntos.

### 4.4 Solo se informa de lo que sale del margen

Todos los cambios se calculan y se guardan, pero **solo los significativos** pasan a la lista de
cambios significativos y al resumen. Un cambio que cabe en el margen de error no es noticia, y
contarlo como noticia sería engañar al cliente.

Un ejemplo construido para probarlo (**SINTÉTICO, no es un dato del reto**): en el test se toma el
estudio del kit y, a propósito, se cambian 40 respuestas en las que Alborada no aparecía para que
aparezca la primera y recomendada. Es una perturbación controlada para comprobar que el método
detecta un cambio grande (`tests/golden/test_serie_alborada.py`). Resultado:

- El score sube de 25,93 a 41,81 en el punto perturbado sintético: **+15,88**, con intervalo **[+9,51; +22,47]**. No contiene el 0:
  sale del margen.
- El puesto pasa de 8.ª a 3.ª.
- También son significativos la aparición global, la de ChatGPT, la de Claude y la diferencia
  frente a los competidores.
- **Gemini y Perplexity suben 10 pp, pero dentro del margen.** No van al resumen. Es exactamente
  la disciplina que queremos: una subida de 10 puntos con 60 respuestas puede ser ruido.

El texto que genera el sistema para el score es, literalmente:

> Del 14/09/2026 al 14/12/2026: el Score de Citación sube de 25,9 a 41,8 (+15,9 puntos; IC 95 % del
> cambio: [+9,5; +22,5]). Sale del margen de error.

(Fechas y cifras ficticias del test: punto perturbado a propósito sobre el caso sintético. No es
una medición ni una mejora real. Las fechas son `LINEA_BASE` y `TRIMESTRE_2` de
`tests/golden/test_serie_alborada.py`.)

### 4.5 Los textos del resumen

El resumen de la serie lo escriben **plantillas fijas en español**, no un modelo de lenguaje. Así
nunca exagera ni se inventa un cambio (`_resumen` y las constantes al inicio de `tracking.py`):

| Situación | Texto del resumen |
|---|---|
| Ninguna medición | «Sin mediciones: aún no hay con qué comparar.» |
| Solo una medición | «Línea base: aún no hay con qué comparar.» |
| Dos mediciones no comparables | «Del … al …: no comparable con la medición anterior: *motivos*» |
| Cambia el mercado | «Del … al …: Cambian los competidores del mercado: entran …; salen … (n → m marcas). El score y la aparición se comparan; el puesto y la diferencia frente a los competidores, no.» |
| Comparables pero sin datos para ningún cambio | «Del … al …: No hay datos para calcular cambios con la medición anterior.» |
| Hay cambios significativos | El texto de cada uno, en orden |
| Se calcularon cambios y ninguno es significativo | «Sin cambios fuera del margen de error» |
| Igual, pero con avisos previos (un par no comparable, un cambio de competidores o un par sin datos) | Esos avisos y «Sin cambios fuera del margen de error en lo que sí es comparable.» |

Matiz importante: «Sin cambios fuera del margen de error» **solo se dice si se ha comparado algo**.
Con una sola medición, el sistema no dice «sin cambios», dice «línea base».

Cada texto de cambio lleva el periodo, la cifra, el intervalo del cambio y una de tres
conclusiones: «Sale del margen de error.», «Está dentro del margen de error.» o «Sin contraste
estadístico: no se puede decir si sale del margen de error.».

---

## 5. Indicadores adelantados

### 5.1 Por qué existen

El score **tarda en moverse**. Si la clínica publica una buena página o consigue salir en un medio,
los asistentes de IA no lo reflejan al día siguiente. Si solo miráramos el score, durante meses
parecería que nada funciona.

Los **indicadores adelantados** son cifras que se mueven **antes** que el score y que anuncian si
va en buena dirección. posiq. calcula cuatro por medición (`_indicadores` en `tracking.py`):

| Indicador | Qué mide | Por qué adelanta |
|---|---|---|
| Citas a la web propia | De todas las fuentes que citan los asistentes, qué fracción va a la web de la marca | Si la web propia empieza a citarse, los asistentes ya la están leyendo |
| Presencia en las 5 fuentes principales | De las respuestas en las que aparece la marca, cuántas citan al menos una de las 5 fuentes **ganadas** más citadas del mercado de ese estudio (`presencia_top_fuentes`). Una fuente ganada es un medio de terceros, no pagado ni propio: se excluyen las webs de las marcas | Estar en las fuentes que los asistentes usan es lo que luego mueve el score |
| Inexactitudes | Afirmaciones sobre la marca que no cuadran con el brief | Corregirlas es un objetivo en sí mismo |
| A revisar por la clínica | Afirmaciones con expresiones de riesgo que la clínica debe revisar | Ídem |

Si una medición no trae los datos para un indicador, su valor es **vacío**, nunca 0. Un 0 inventado
diría «no hay ninguna», que no es lo mismo que «no lo sabemos».

### 5.2 Caso sintético del reto

`tests/golden/test_serie_alborada.py`:

| Indicador | Valor |
|---|---|
| Citas a la web propia | 5,9 % (33 de 564 citas; 0,0585 en `test_serie_alborada.py`) |
| Presencia en las 5 fuentes principales | 74,1 % |
| Inexactitudes | 0 |
| Afirmaciones a revisar | 21 |

---

## 6. Cadencia y plazos

### 6.1 Cadencia trimestral

La propuesta es **re-medir cada trimestre** con el mismo banco, los mismos motores y la misma
metodología (ADR 0016; ADR 0015, `docs/adr/0015-cuentas-y-propiedad.md`). El plan de acción de la
demo incluye un «Informe de evolución trimestral».

### 6.2 Plazos por motor: orientación, no dato

> Esta sección es **orientación cualitativa** del equipo sobre cómo funcionan los motores. **No es
> una medición de posiq.**, no está en el código y no se ha comprobado con datos reales.

Los motores no se actualizan igual de rápido. Como orientación:

- **Perplexity** busca en la web en tiempo real en cada respuesta. Es el que antes puede reflejar
  un cambio en las fuentes.
- **Gemini** depende en buena medida del índice de Google. Un cambio se nota cuando Google lo ha
  rastreado e indexado.
- **ChatGPT** depende más de fuentes externas y de lo que aprendió el modelo. Suele tardar más:
  meses.

Por eso tiene sentido mirar los resultados **por motor** y no solo el global, y por eso existen los
indicadores adelantados. Cualquier plazo concreto que se cite en una presentación debe presentarse
como estimación, no como dato.

### 6.3 Lo que falta para un seguimiento real fiable

Dos piezas están **pendientes** y afectan directamente al seguimiento real:

1. **Reutilizar el banco de preguntas (PENDIENTE).** Hoy la re-medición vuelve a generar el banco.
   En modo real lo genera un modelo de lenguaje, que puede redactar las preguntas de otra forma. La
   huella cambiaría y la serie diría, con razón, «no comparable». La solución (que la re-medición
   reutilice exactamente las mismas preguntas) es tarea de la zona C (ADR 0016;
   `src/posiq/application/nodes/prompts.py`). En modo kit no pasa porque el banco es siempre el del
   kit.
2. **Exigir el mismo juez (PENDIENTE, planificado para la ola 2).** El **juez** es la pieza que lee cada respuesta y
   decide con qué fuerza se recomienda la marca, cómo la menciona y si la mención se apoya en las
   fuentes citadas (si aparece y en qué posición lo deciden siempre las reglas, ADR 0014). Puede ser
   Jev (con DeepSeek de respaldo), solo DeepSeek (si no hay clave de TypeSafe) o solo **reglas** (más barato). El juez cambia el
   resultado: con solo reglas, la fuerza vale siempre 1 cuando la marca aparece (no distingue «la
   recomiendo» de «existe») y el tipo de fuente no se resuelve. En el caso sintético, eso mueve el
   score de 25,93 a 25,87 (`tests/golden/test_demo_canonico.py`). En el kit solo 13 de las 240
   evaluaciones tienen etiqueta; por eso la diferencia es pequeña y **no** indica que el juez
   importe poco (ver [score-de-citacion.md](score-de-citacion.md) §8). En una medición real, donde
   todo lo decide el juez, la diferencia puede ser mucho mayor. Hoy
   la regla de comparabilidad **no** mira el juez. Mientras no lo haga, **todas las mediciones de
   una serie deben usar el mismo juez**: reglas en todas, Jev en todas o solo DeepSeek en todas.

---

## 7. Limitaciones honestas

Esto es lo que el método **no** permite afirmar. Conviene decirlo antes de que lo pregunte el
jurado.

### 7.1 Atribución causal

Un cambio significativo dice que **algo cambió**, no **por qué**. El score de una marca puede
moverse sin que la marca haga nada:

- **Cambia el motor.** Una versión nueva del modelo puede responder distinto. El sistema avisa si
  consta un cambio de modelo, pero no puede separar su efecto del de las acciones de la marca.
- **Cambian los competidores.** Si un competidor gana visibilidad, puede desplazar a la marca. Por
  eso se miran el puesto y la diferencia frente a la media, pero tampoco eso prueba la causa.
- **Cambia la web.** Aparecen o desaparecen fuentes que los asistentes citan.

Lo que sí podemos hacer: mostrar el cambio, su margen, los indicadores adelantados y el contexto
(competidores, modelos), y dejar claro que la atribución es una interpretación.

### 7.2 Tamaño de muestra frente a coste

Más respuestas dan márgenes más estrechos, pero cada respuesta es una llamada de pago a un motor.
Con los precios provisionales de `settings.py`, solo las llamadas a los motores de un estudio del
tamaño del kit (624 llamadas a 4 motores) costarían unos **10,56 €**; con el juez, el total estimado
va de **10,57 €** (solo reglas) a **12,42 €** (solo DeepSeek) (ver [kit-vs-real.md](kit-vs-real.md)).
El tope de gasto configurado (`BUDGET_EUR_MAX`) es **5 €** (`docs/estado/C.md`). Todo es una
estimación: el modo real no se ha ejecutado nunca. Habrá que elegir entre
subir el tope o medir menos, y medir menos ensancha los márgenes (recordatorio: la mitad de margen
cuesta unas cuatro veces más respuestas).

### 7.3 Con el kit, una re-medición sale idéntica

El kit tiene un único conjunto de respuestas, fijas. Si se re-mide en modo kit, las respuestas son
exactamente las mismas, así que **todos los cambios valen 0** y el resumen dice «Sin cambios fuera
del margen de error» (`test_misma_medicion_dos_veces_sin_cambios`: 8 cambios, todos 0, ninguno
significativo). La serie sale **plana**.

Eso es correcto: demuestra que el método es **repetible** y que no fabrica cambios donde no los
hay. Pero **no demuestra una mejora**. Para enseñar cómo se ve una mejora usamos el segundo punto
perturbado del test (§4.4), que es sintético y así debe presentarse.

### 7.4 Otras limitaciones (ADR 0008)

- **El margen solo cubre el muestreo, no los errores del juez.** Si el juez se equivoca, el
  intervalo no lo recoge. En el kit, la fuerza media tiene un intervalo muy estrecho ([1,00–1,03])
  porque casi todas las evaluaciones vienen de reglas que ponen fuerza 1, no porque la conozcamos
  con precisión.
- **Respuestas correlacionadas**: los intervalos son algo optimistas (§2.3).
- **Muchas comparaciones a la vez.** Se miran muchos segmentos sin corrección por comparaciones
  múltiples. Entre muchos segmentos, alguno puede salir significativo por azar.
- **No se puede afirmar** que una marca esté por encima de otra si sus intervalos se solapan, ni
  que un cambio de re-medición sea real si su intervalo contiene el 0.

---

## 8. Resumen para la presentación

- Regla de diseño: cada cifra con su margen, **25,9 [21,6–30,1]** y no «25,93» a secas (caso
  sintético). El cálculo está hecho; mostrarlo en la API, la web y el Word está **PENDIENTE**.
- Wilson para tasas, bootstrap con semilla fija para el score, Newcombe para diferencias de tasas.
- Una diferencia es real solo si su intervalo no contiene el 0: «fuera del margen de error».
- Seguimiento: línea base, re-medición trimestral con el mismo método, y solo se informa de lo que
  sale del margen, siempre frente a los competidores.
- Dos mediciones solo se comparan si coinciden metodología, versión del score, banco de preguntas
  y motores. Exigir también el mismo juez está **PENDIENTE** (ola 2): hasta entonces, mismo juez en
  todas las mediciones de una serie.
- Los indicadores adelantados existen porque el score tarda en moverse.
- Todo lo anterior está calculado sobre el caso **sintético** del reto. El modo real **no se ha
  ejecutado todavía**.

---

## Dónde se comprueba

| Qué | Dónde |
|---|---|
| Fórmula del Score de Citación | `src/posiq/domain/scoring.py` |
| Wilson, Newcombe, bootstrap, semilla, réplicas, significancia de hallazgos y re-medición | `src/posiq/domain/stats.py`, `src/posiq/domain/stats_schemas.py` |
| Serie, comparabilidad, huella del banco, cambios, indicadores y textos del resumen | `src/posiq/domain/tracking.py`, `src/posiq/domain/tracking_schemas.py` |
| Cifras del rigor en el caso sintético (25,9 [21,6–30,1], márgenes por motor, [19,7–31,8], hallazgos) | `tests/golden/test_rigor_alborada.py` |
| Serie en el caso sintético (8.ª de 10, −8,59, indicadores, re-medición plana, punto perturbado) | `tests/golden/test_serie_alborada.py` |
| Cifra canónica 25,93 y 25,87 con juez por reglas | `tests/golden/test_demo_canonico.py` |
| Tests unitarios | `tests/domain/test_stats.py`, `tests/domain/test_tracking.py` |
| Decisiones y límites | `docs/adr/0008-rigor-estadistico.md`, `docs/adr/0016-seguimiento-con-metodo.md` |
| Re-medición en la API y lo pendiente | `src/posiq/application/runner.py` (`prepare_remeasure`), `src/posiq/interfaces/api/main.py`, `docs/estado/A.md`, `docs/estado/C.md` |
| Banco regenerado en modo real | `src/posiq/application/nodes/prompts.py` |
| Versión de la metodología | `src/posiq/application/deps.py` (`VERSION_METODOLOGIA`) |
| Tope de gasto | `src/posiq/settings.py` (`budget_eur_max`) |
| Que el kit es sintético | `data/kit/00_LEEME_Guia_del_kit.md` |

Para volver a calcular las cifras del rigor (sin claves, sin coste):

```sh
python -m uv run python scripts/informe_rigor.py
python -m uv run pytest tests/golden/test_rigor_alborada.py tests/golden/test_serie_alborada.py
```

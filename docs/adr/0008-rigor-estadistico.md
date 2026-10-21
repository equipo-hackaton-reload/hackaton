# ADR 0008 · Rigor estadístico: intervalos, significancia y consenso del juez

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** A (dominio). El adaptador `ConsensusJudge` es de la Zona B.

## Contexto

Hasta ahora cada cifra salía sin margen de error: «25,93», «15 % en Claude», «4 % en Barcelona».
Con 60 ejecuciones por motor y 24 por ciudad, una diferencia de unos pocos puntos puede ser ruido
de muestreo. Además, los hallazgos se disparaban con umbrales fijos (≥ 20 pp, < 30 %…) sin decir
si la diferencia se distingue del azar. Y el juez evalúa cada respuesta una sola vez.

Regla 1 sigue igual: las cifras las calcula código determinista. Este ADR solo les añade su margen
de error y no cambia ninguna cifra existente (25,93 y el 8.º puesto siguen fijados en
`tests/golden/test_demo_canonico.py`).

## Decisión

Módulo puro `domain/stats.py`, modelos aditivos en `domain/stats_schemas.py` y voto por mayoría en
`domain/consensus.py`. No cambian `schemas.py`, `ports.py`, `Finding`, `MetricsDelta`,
`diff_metrics` ni `detect_findings`.

| Qué | Método | Por qué |
|---|---|---|
| Tasa de aparición (global, motor, fase, ciudad, perfil, familia; espontáneo y asistido) | Wilson al 95 % | Con tasas pequeñas (1 de 24), Wald da límites negativos o amplitud cero. Wilson no. |
| Score de Citación | Bootstrap percentil sobre ejecuciones; el score se recalcula con `scoring.score_citacion` | No hay fórmula cerrada para el score. Se usa la misma función, así que la fórmula no se duplica. |
| Diferencia de dos tasas (hallazgos y re-medición) | Newcombe, método 10 («hybrid score»), a partir de los dos Wilson | Mismo motivo que Wilson frente a Wald. Se descarta Wald. |
| Diferencia de scores de dos marcas del mismo estudio | Bootstrap **emparejado**: las mismas ejecuciones remuestreadas para las dos | Las dos marcas se evalúan en las mismas respuestas. |
| Diferencia de scores entre dos estudios (re-medición) | Bootstrap independiente: cada estudio por separado | Son muestras distintas. |

- **Semilla y réplicas:** `SEMILLA_BOOTSTRAP = 20261021` y `REPLICAS_BOOTSTRAP = 2000`. El mismo
  estudio da siempre el mismo intervalo, y los golden lo fijan. Con 2000 réplicas, el error de
  Monte Carlo de los percentiles es de centésimas: no cambia la primera cifra decimal.
- **Significativa** ⇔ el intervalo al 95 % excluye 0. No se dan p-valores, para que nunca puedan
  contradecir al intervalo.
- **Unidad de remuestreo:** por defecto, la ejecución (`unidad="ejecucion"`). `unidad="prompt"`
  remuestrea prompts enteros, con sus motores y repeticiones (bootstrap por conglomerados). Se usa
  para medir la sensibilidad (ver «Límites»).

### Significancia de los hallazgos (`significancia_hallazgos`)

Devuelve `finding_id → SignificanciaHallazgo` sin tocar el `Finding`.

| Regla | Contraste |
|---|---|
| `caida_embudo` | tasa de la fase de origen − tasa de la de destino (Newcombe) |
| `motor_debil` | tasa del motor más fuerte − tasa del más débil (Newcombe) |
| `ciudad_baja` | tasa de la ciudad − el umbral fijo que disparó la regla (30 %, o la mitad de la global), con el Wilson de la ciudad desplazado |
| `brecha_lider` | score del líder − score de la marca (bootstrap emparejado) |
| `asistida_vs_espontanea` | tasa asistida − tasa espontánea (Newcombe) |
| `recomendacion_debil` | fuerza media de las apariciones − 1,5 (bootstrap de las apariciones) |
| `fuente_lider` | **Sin contraste.** Es un recuento sin tasa de referencia, y las ejecuciones del líder y de la marca son las mismas (no son muestras independientes). |
| `menciones_negativas` | **Sin contraste.** Es un recuento de casos concretos, no una estimación: basta con un caso para que exista. |

### Re-medición (`significancia_remedicion`)

Para cada `VisibilityDelta` (mismos segmentos y el mismo delta redondeado) se calcula Newcombe. Si
un lado no tiene datos, el resultado es None. Para el score se usa bootstrap independiente.

Recibe las `Muestra` (evaluaciones, ejecuciones y prompts) de las dos mediciones. Si el score que
se recalcula con una muestra no coincide con el de sus `Metrics`, lanza un error: así se evita
comparar datos que no son los medidos.

### Consenso del juez

**`domain/consensus.consenso`** hace un voto por mayoría sobre N evaluaciones de la misma marca en
la misma respuesta:

1. Primero se vota `aparece`. Solo las evaluaciones que coinciden con el ganador votan el resto de
   campos, así el resultado siempre es coherente.
2. **Empates:**
   - En los campos del score (`aparece`, `posicion`, `fuerza`, `tipo_fuente`) gana el valor que
     menos sube el score. Un empate nunca infla la visibilidad.
   - En los demás campos gana la evaluación más temprana.
3. **Confianza:** es el menor acuerdo (votos del ganador / N) entre los campos del score. Es el
   mismo criterio de mínimo que `score_confidence`.
4. **Revisión:** se marca si la confianza es menor que 0,75. Con N = 3, solo la unanimidad evita la
   revisión.

**`adapters/judge/consensus.ConsensusJudge`** (Zona B) implementa `ports.Judge` y lo que usa el
grafo (`aevaluate_many`, `traces`):

- Llama a sus jueces internos, o N veces al mismo con `ConsensusJudge.repetido(juez, n)`.
- **Trazas:** las registra cada juez interno (modelo, versión de preguntas, tokens y coste), igual
  que hoy. `traces` las reúne sin duplicarlas.
- **Caché:** `repetido` rechaza un juez con caché. Con caché devolvería N veces la misma respuesta
  y el consenso sería falso.
- **Concurrencia:** las N pasadas van en serie para no multiplicar la concurrencia por N.
- **Pendiente:** `build_judge` todavía no lo usa. Activarlo es decisión de las Zonas B/C, porque
  multiplica por N el coste del juez.

## Cifras de Alborada (kit, etiquetas del kit como la canónica)

Salen de `uv run python scripts/informe_rigor.py` y las fija
`tests/golden/test_rigor_alborada.py`.

**Score de Citación: 25,9 [21,6–30,1]**, IC 95 % bootstrap sobre 240 ejecuciones (inf 21,60, sup
30,15). Contiene 25,93.

| Motor (n = 60) | Aparición espontánea | Margen | Score |
|---|---|---|---|
| ChatGPT | 18 % [11–30 %] | ± 12 pp | 11,4 [5,9–17,7] |
| Claude | 15 % [8–26 %] | ± 11 pp | 9,7 [4,2–15,7] |
| Gemini | 57 % [44–68 %] | ± 13 pp | 38,5 [30,3–47,1] |
| Perplexity | 65 % [52–76 %] | ± 13 pp | 44,2 [35,6–52,2] |
| **Global (n = 240)** | 39 % [33–45 %] | ± 6 pp | 25,9 [21,6–30,1] |

Por ciudad (n = 24): Madrid 54 % [35–72 %] (± 19 pp) y Barcelona 4 % [1–20 %] (± 16 pp).

**Hallazgos:** 6 de los 7 admiten contraste y los 6 son significativos al 95 %. Ninguno es «no
significativo». `F-fuente-lider` no admite contraste.

| Hallazgo | Delta [IC 95 %] |
|---|---|
| F-motor-debil (Perplexity − Claude) | 0,50 [0,33–0,63] |
| F-ciudad-barcelona (tasa − 30 %) | −0,26 [−0,29; −0,10] |
| F-brecha-lider | 40,53 [35,34–45,56] |
| F-caida-embudo (descubrimiento − decisión) | 0,197 [0,037–0,329] |
| F-asistida-vs-espontanea | 0,61 [0,54–0,67] |
| F-recomendacion-debil (fuerza − 1,5) | −0,49 [−0,50; −0,47] |

## Límites: qué NO se puede afirmar

- **Las ejecuciones no son independientes.** Cada prompt se lanza 3 veces por motor y las
  repeticiones se parecen. Wilson y el bootstrap por ejecuciones suponen independencia, así que los
  intervalos son algo optimistas. Remuestreando prompts enteros:
  - El IC del score pasa de [21,6–30,1] a **[19,7–31,8]**.
  - La brecha con el líder sigue siendo significativa: [33,9–47,2].
  - El contraste Perplexity − Claude, también: [0,32–0,68].
  - **La caída del embudo deja de serlo:** [−0,08–0,44]. La fase de decisión tiene solo 4 prompts.
  - Conclusión: «la visibilidad cae de descubrimiento a decisión» es un indicio, no una conclusión
    firme. Hay que confirmarla con más prompts de decisión.
- **Los intervalos solo cubren el muestreo de respuestas, no el error del juez.** La mayoría de
  evaluaciones del kit vienen de reglas (fuerza 1 si aparece), así que el IC de la fuerza media
  ([1,00–1,03]) es estrecho porque la medida apenas varía, no porque la sepamos con precisión. El
  `ConsensusJudge` ataca este error, pero solo con un juez real.
- **Umbrales fijos.** En `ciudad_baja` y `recomendacion_debil`, el umbral de la regla (30 %, la
  mitad de la global, 1,5) se trata como fijo. Si el umbral es la mitad de la tasa global, no se
  propaga su incertidumbre.
- **El hallazgo `motor_debil` contrasta solo el par extremo.** Los motores «también lejos» de la
  descripción no se contrastan.
- **Comparaciones múltiples.** Hay 7 hallazgos y decenas de segmentos sin corrección
  (Bonferroni/Holm). Un segmento significativo entre muchos puede serlo por azar. Los hallazgos son
  pocos y con márgenes amplios (todos menos la caída del embudo excluyen 0 con holgura).
- **El kit es sintético.** Las cifras ilustran el método. No dicen nada del mercado real.
- **No se puede afirmar** que Alborada esté por encima o por debajo de una marca cuyo IC se solape
  con el suyo, ni que un cambio de re-medición sea real si su intervalo contiene 0.

## Consecuencias

- La web (D), el Word (E) y la API (C) pueden enseñar «25,9 [21,6–30,1]» y el margen por motor,
  con `formato_intervalo` y `formato_margen` (formato español).
- La integración en el grafo y en `GET /studies/{id}` es de la Zona C: `informe_rigor(metrics,
  findings, Muestra(evaluations, runs, prompts))`. Tarda unos 4 s con Alborada y es determinista.
- Cambiar la semilla o las réplicas cambia los intervalos: hay que actualizar los golden y este ADR.

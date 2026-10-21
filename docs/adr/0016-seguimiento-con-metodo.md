# ADR 0016 · Seguimiento con método: serie temporal de mediciones

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** A (`domain/tracking.py`, `domain/tracking_schemas.py`). Lo consumen C (API de
  seguimiento) y D (web).

## Contexto

posiq. no vende un score suelto. Vende un seguimiento con método:

1. Se mide una línea base.
2. Cada trimestre se vuelve a medir con el mismo banco y la misma versión de los motores.
3. Solo se informa de los cambios que salen del margen de error, y se comparan con los
   competidores.

`diff_metrics` y `stats.significancia_remedicion` ya comparan dos mediciones. Faltaba la serie: el
orden, la comparabilidad de cada punto con el anterior, la posición frente al mercado y un resumen
que no cuente ruido como noticia.

## Decisión

Módulo puro `domain/tracking.py`. Sus modelos viven en `domain/tracking_schemas.py`
(`PuntoSerie`, `CambioSerie`, `IndicadorAdelantado`, `ValorIndicador` y `SerieMarca`). No cambian
`schemas.py` ni `ports.py`.

`construir_serie(brand_id, nombre, mediciones)` recibe una `MedicionSerie` por estudio. Cada una
trae `Study`, `Metrics` y `stats.Muestra`. Opcionalmente trae también `Market` y el catálogo de
fuentes (para los indicadores de fuentes) y un `HallazgoExactitud` (para los de exactitud).

### Comparabilidad

Un punto es comparable con el anterior si coinciden estas cinco cosas:

- `version_metodologia`
- la versión del score
- el juez (`PuntoSerie.juez`, ver «Juez»)
- la huella del banco de prompts, o hay un núcleo común (ver «Núcleo común del banco»)
- el conjunto de motores

| Qué cambia | Resultado |
|---|---|
| Versión de la metodología, del score, juez o motores | No comparable, con un motivo por cada diferencia. No se calcula ningún cambio. |
| Banco de prompts sin ninguna pregunta en común | No comparable («Cambia el banco de prompts (… → …).»). |
| Banco de prompts que crece o se recorta, con preguntas comunes | Comparable **sobre el núcleo común**, con aviso. El banco completo se informa aparte, sin comparar. |
| El juez consta en una medición y no en la otra | Comparable, con aviso. |
| Versión del mercado (`version_mercado`), mismas marcas | Como el cambio de marcas: puesto y diferencia frente a los competidores, no comparables. |
| Versión del perfil (`version_perfil`) | No afecta a la comparación. Solo se marca en el gráfico. |
| Modelo de un motor (`Run.modelo`) | Comparable, con aviso: parte del cambio puede deberse al modelo. |
| El modelo consta en una medición y no en la otra | Comparable, con aviso. |
| Conjunto de marcas del mercado (`PuntoSerie.marcas_mercado`) | Score y aparición, comparables. Puesto y diferencia frente a los competidores, **no**: `competidores_comparables = False`, no se calculan como cambio y el motivo («Cambian los competidores del mercado: entran …; salen … (n → m marcas). …») va en `avisos` y en el resumen. |
| Primer punto | `comparable_con_anterior = False`, con el motivo «Línea base: es la primera medición de la serie.». |

El conjunto de marcas cuenta porque el puesto y la media de los competidores dependen de quién
esté en el mercado. Sin esta regla, un estudio con el mismo score (25,93 → 25,93) pasaba del 8.º
de 10 al 2.º de 4 y salía como cambio «fuera del margen de error». Si en un punto no consta el
mercado (`marcas_mercado` vacío, datos anteriores a este campo), no se declara cambio.

La huella del banco (`huella_banco`) es el SHA-256 de lo que se pregunta en cada prompt:
plantilla, familia, fase, instanciación, perfil, ciudad, texto, marcas nombradas y prioridad.
No depende del orden ni de los ids de instancia.

**La huella incluye el texto del prompt.** Si la re-medición vuelve a generar el banco (por
ejemplo, si el LLM reescribe las preguntas), la huella cambia y la serie dice, con razón, que no
es comparable: no se puede atribuir un cambio de score a la marca si cambió lo que se pregunta.
Por eso la re-medición real debe **reutilizar el banco** de la medición anterior (mismos
`PromptInstance`, no uno regenerado). Hoy `POST /studies/{id}/remeasure` arranca en `prompts` y
regenera el banco; lo corrige otro paquete en el runner y el nodo de prompts (zona C). Hasta
entonces, una serie de re-mediciones reales sale «no comparable» por el banco, que es lo honesto.

### Juez

El juez decide si una marca aparece, en qué posición y con qué fuerza: cambiarlo cambia la
medida. `PuntoSerie.juez` («proveedor/modelo») lo calcula `juez_medicion`, en este orden:

1. `MedicionSerie.juez`, si quien construye la serie lo declara (la API, con la configuración del
   estudio).
2. Las trazas del juez del estudio (`Trace.nodo` = `judge:<proveedor>`, `Trace.modelo`): por
   ejemplo `jev/jev-1.13`; varios (un consenso) se unen con « + ». No cuentan `plan_guard:*`,
   `run:*` ni trazas de otros estudios.
3. Sin trazas, `Evaluation.origen`: `jev` si alguna evaluación es de Jev; si no, `humano`
   (etiquetas del kit); si todas son `fallback`, `reglas`. Una revisión humana de algunas
   evaluaciones no cambia el juez de la medición.

Si los dos puntos tienen juez y no coincide, el par no es comparable: «Cambia el juez (a → b).».
Si falta en uno, es comparable con aviso. No se tocó `schemas.py`: el juez se deduce de lo que
ya se guarda o lo declara la medición.

### Núcleo común del banco

Si la marca abre una ciudad o un servicio, el banco crece y la huella cambia. Antes eso dejaba la
serie sin comparar. Ahora:

- **Clave de una pregunta** (`clave_pregunta`): plantilla, familia, fase, instanciación, perfil,
  ciudad, texto, marcas nombradas y prioridad, en JSON. Es la fila de `huella_banco`, sin el id
  de instancia (cambia en cada medición). Incluye el texto a propósito: si el LLM reescribe una
  pregunta, deja de ser la misma.
- **Núcleo común:** las claves presentes en los dos bancos. Si hay al menos una y lo demás es
  comparable, el par se compara solo sobre ellas: `restringir_a_preguntas` filtra prompts,
  ejecuciones y evaluaciones de cada medición y recalcula sus métricas con `compute_metrics`; con
  eso se calculan score, aparición, puesto y diferencia, con los mismos métodos de siempre.
- **Qué se ve:** `PuntoSerie.nucleo_comun` (`NucleoComun`: huella del núcleo, preguntas comunes,
  del banco anterior y del actual, y el score de cada medición sobre el núcleo). Los cambios llevan
  `sobre_nucleo_comun=True` y su texto dice «(núcleo común de N preguntas)». El aviso «Cambia el
  banco de prompts (… → …). El score, la aparición y la posición se comparan sobre las N preguntas
  comunes …» va en `avisos` y en el `resumen`.
- **El banco ampliado se informa aparte:** `PuntoSerie.score` sigue siendo el del banco completo
  de esa medición, pero no se compara con el anterior.

### Configuración versionada (perfil y mercado)

El perfil de la marca y su mercado (competidores) se editan por versiones, vigentes desde una
fecha; nunca se sobrescriben. Cada medición guarda las suyas (`MedicionSerie.version_perfil` y
`version_mercado` → `PuntoSerie`).

- `SerieMarca.cambios_configuracion`: lista de `CambioConfiguracion` (`study_id`, `que_cambia` ⊂
  {`perfil`, `mercado`}, `texto`) en cada punto donde cambia alguna versión respecto al anterior
  (las dos deben constar). La web pinta una marca vertical en ese `study_id`.
- Cambio de mercado: el puesto y la diferencia frente a los competidores no son comparables
  (con las mismas marcas, «Cambian los competidores del mercado: cambia la versión del mercado …»).
- Cambio de perfil: no afecta al score ni a la comparabilidad.
- **Exactitud contra el perfil vigente:** `VersionPerfil`/`VersionMercado` (en
  `tracking_schemas`), `vigente_en(versiones, fecha)` (la de `vigente_desde` más reciente no
  posterior; error si dos empiezan a la vez), `exactitud_con_perfil(study, brand, version, runs)`
  (error si la versión es posterior a la medición) y `exactitud_en_fecha(study, brand, versiones,
  runs)`. Una afirmación correcta en marzo no pasa a ser inexacta porque el perfil cambie en junio.

### Cambios entre puntos consecutivos comparables

| Métrica (`CambioSerie.metrica`) | Método | `relativo_a_competidores` |
|---|---|---|
| `score` | Bootstrap independiente de cada estudio (`stats.significancia_remedicion`) | no |
| `aparicion_espontanea:global` y `aparicion_espontanea:<Motor>` | Newcombe (`stats.significancia_remedicion`) | no |
| `posicion` | Bootstrap del puesto (ver abajo). Delta negativo = mejora. | sí |
| `diferencia_vs_competidores` | Bootstrap de score − media del resto del mercado | sí |

Para el puesto y la diferencia, cada réplica remuestrea las ejecuciones de cada estudio por
separado (los estudios son independientes). Dentro de cada estudio recalcula el score de **todas**
las marcas sobre las mismas ejecuciones (emparejado). Usa `scoring.score_from_profile`, así que la
fórmula no se duplica. Se usan la misma semilla y las mismas réplicas que en `stats`.

Un cambio es significativo si y solo si su IC al 95 % excluye 0. Solo los significativos van a
`cambios_significativos` y al `resumen`. Si una métrica no admite contraste, `significancia = None`
y `significativo = False`, y el texto lo dice.

### Resumen

«Sin cambios» solo se dice si se ha comparado algo. El `resumen` distingue:

| Caso | Resumen |
|---|---|
| Un solo punto | «Línea base: aún no hay con qué comparar.» |
| Ningún punto | «Sin mediciones: aún no hay con qué comparar.» |
| Par no comparable | «Del … al …: no comparable con la medición anterior: <motivos>» |
| Par con cambio de competidores | «Del … al …: Cambian los competidores del mercado: …» |
| Par comparado sobre el núcleo común | «Del … al …: Cambia el banco de prompts (… → …). El score, la aparición y la posición se comparan sobre las N preguntas comunes …» |
| Par comparable sin datos para ningún cambio | «Del … al …: No hay datos para calcular cambios con la medición anterior.» |
| Cambios significativos | Sus textos, en orden. |
| Se calcularon cambios, ninguno significativo y nada más que decir | Exactamente «Sin cambios fuera del margen de error». |
| Igual, pero con alguna línea anterior (no comparable o competidores) | Esas líneas y «Sin cambios fuera del margen de error en lo que sí es comparable.» |

### Indicadores adelantados

Son cifras que se mueven antes que el score. Hay uno por punto. Si la medición no trae los datos,
el valor es None: nunca se inventa.

| Clave | Cálculo |
|---|---|
| `cuota_web_propia` | `source_map.hallazgo_web_propia(...).cifra`: fracción de las citas que van a la web de la marca |
| `presencia_top_fuentes` | Fracción de las respuestas en las que aparece la marca que citan al menos una de las 5 fuentes **ganadas** más citadas del mercado de ese estudio (`mapa_fuentes`, sin la entrada agregada de webs propias) |
| `inexactitudes` | `HallazgoExactitud.n_incorrectas` |
| `a_revisar` | `HallazgoExactitud.n_riesgo_regulatorio` (afirmaciones «a revisar por la clínica») |

### Textos

Los textos salen de plantillas en español, con coma decimal y menos tipográfico. Llevan siempre el
periodo («Del 14/09/2026 al 14/12/2026: …») y el IC del cambio. Ningún LLM interviene.

## Cifras con el kit (golden `tests/golden/test_serie_alborada.py`)

- **El kit medido dos veces** (re-etiquetado con otro `study_id` y otra fecha):
  - Punto: 25,93, IC [21,6; 30,15], 8.º de 10.
  - Media de los competidores: 34,52, con una diferencia de −8,59.
  - Los 8 cambios valen 0 y ninguno es significativo: «Sin cambios fuera del margen de error».
  - Indicadores: web propia 5,85 %, presencia en las 5 fuentes principales 74,1 %, 0
    inexactitudes y 21 afirmaciones a revisar.
- **Segundo punto perturbado (sintético):** 40 no-apariciones espontáneas pasan a 1.ª activa.
  - Score de 25,93 a 41,81: +15,88, con IC [+9,51; +22,47].
  - Puesto del 8.º al 3.º.
  - También son significativas la aparición global, ChatGPT, Claude y la diferencia frente a los
    competidores.
  - Gemini y Perplexity suben 10 pp, pero quedan dentro del margen.

## Consecuencias

- Hasta ahora una re-medición con el mismo resultado no producía titulares. Así debe ser: el kit
  medido dos veces da 0 cambios.
- Los intervalos asumen ejecuciones independientes, como en el ADR 0008. Son algo optimistas,
  porque las repeticiones de un mismo prompt se parecen.
- La serie no filtra por estado. La API (C) solo le pasa estudios completados del usuario.
- El primer punto se marca como no comparable con el motivo «línea base». La web (D) debería
  pintarlo como línea base, no como aviso.
- `tracking.py` importa algunos ayudantes privados de `stats` y `source_map` (`_es`,
  `_limites_percentil`, `_Resolver`, `_dominios` y `_marcas_por_run`), para no duplicar la lógica
  dentro del mismo paquete.

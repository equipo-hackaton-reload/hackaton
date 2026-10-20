# ADR 0002 · Cada resultado conserva el id del estudio

- **Estado:** aceptado
- **Fecha:** 2026-10-20
- **Zona:** A

## Contexto

Un `Study` es una medición de una marca en una fecha, con su brief, su modo (`kit` o `real`), la
versión de la metodología y la del score. El reto pide medir varias marcas sin cruzar sus datos,
repetir la medición y comparar mediciones de forma honesta (doc 07, N3.3 y N3.6). También pide
distinguir siempre los datos sintéticos del kit de los obtenidos de APIs reales. Sin un
identificador común, una evaluación, un hallazgo o una traza no dicen de qué medición vienen.

## Decisión

- `Run`, `Evaluation`, `Finding`, `Metrics`, `Plan`, `Proposal` y `Trace` llevan `study_id`
  obligatorio. Las acciones heredan el del `Plan` que las contiene.
- Los cargadores reciben el `study_id`. `compute_metrics` falla si recibe ejecuciones o evaluaciones
  de otro estudio, y `Proposal` valida que sus hallazgos, su plan y sus métricas son del mismo.
- `Metrics.comparado_con` apunta al estudio anterior. `diff_metrics(actual, anterior)` devuelve un
  `MetricsDelta` con el cambio de score y de tasas por motor, fase y ciudad. Lo marca como no
  comparable si cambia la versión del score.

## Consecuencias

- **Multimarca y multimedición:** pueden convivir en la misma base de datos sin mezclarse; el
  repositorio guarda y filtra por `study_id`.
- **Trazabilidad:** cualquier cifra de una propuesta se rastrea hasta sus evaluaciones y
  ejecuciones dentro del mismo estudio, y las trazas de coste se suman por estudio.
- **Re-medición:** una medición nueva es un estudio nuevo, que no sobrescribe el anterior; el estudio
  previo se conserva para comparar.
- **Límite de la comparación:** dos mediciones cercanas demuestran el mecanismo de seguimiento, no un
  efecto causal del plan.
- **Ids no globales:** los ids de `Evaluation` (`<run_id>:<brand_id>`) solo son únicos dentro de un
  estudio; la clave global es (`study_id`, `id`).
- **Coste del cambio:** añadir `study_id` es un cambio de contrato. Quien construya estos modelos
  (adaptadores, nodos, API) tiene que pasarlo.

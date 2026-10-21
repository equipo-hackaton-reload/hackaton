# Zona A · dominio (`src/posiq/domain/`, `tests/domain/`, `tests/golden/`)

## En develop
- Dominio puro completo: esquemas, `kit_loader`, detección, `judge_questions`, score de citación,
  métricas, hallazgos, evidencias, `plan_questions`, `quality_schemas`, `simulation.simulate_plan`.
- Tests de dominio y golden de Alborada; `scripts/evaluate_system.py` (informe en `docs/evaluacion/`).

## Falta
- Cuadrar el score de Alborada: la API (fixture, juez por detección) da **25,87**; `evaluate_system.py` da **25,93**.
  Decidir cuál es la cifra canónica y fijarla en un golden.
- Que `simulate_plan` y la calidad del plan lleguen a la API (la integración es de C).

## Siguiente tarea
- `feature/A-score-canonico`: explicar la diferencia 25,87 / 25,93 y añadir golden de la cifra de la demo.
- Cierre de hito: CHANGELOG, `VERSION`, PR `develop → main` y tag.

## No tocar
- `schemas.py` y `ports.py` sin PR `contract-change`.
- Nada de I/O en `domain/`.

# Zona A · dominio (`src/posiq/domain/`, `tests/domain/`, `tests/golden/`)

## En develop
- Dominio puro completo: esquemas, `kit_loader`, detección, `judge_questions`, score de citación,
  métricas, hallazgos, evidencias, `plan_questions`, `quality_schemas`, `simulation.simulate_plan`.
- Tests de dominio y golden de Alborada; `scripts/evaluate_system.py` (informe en `docs/evaluacion/`).

## Falta
- Que `simulate_plan` y la calidad del plan lleguen a la API (la integración es de C).

## Siguiente tarea
- Hecho en `feature/A-score-canonico`: cifra canónica **25,93** (etiquetas del kit; 25,9 en la deck),
  8.ª de 10, proyección 25,9 → 30,8, fijadas en `tests/golden/test_demo_canonico.py`. La API en
  fixture da 25,87 porque su juez por reglas no clasifica tipo de fuente ni gradúa la fuerza.
- Medir la cifra con Jev real cuando haya `TYPESAFE_API_KEY` y compararla con la canónica.
- Cierre de hito: CHANGELOG, `VERSION`, PR `develop → main` y tag.

## No tocar
- `schemas.py` y `ports.py` sin PR `contract-change`.
- Nada de I/O en `domain/`.

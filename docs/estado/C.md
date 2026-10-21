# Zona C · orquestación y API (`application/`, `interfaces/api/`)

## En develop
- Grafo LangGraph (intake, market, prompts, run, judge, analyze, plan, write) con revisiones por
  `interrupt()` y checkpointer SQLite; `SqlStudyRepo`.
- API: `POST /studies`, `GET /studies`, `GET /studies/{id}`, `POST /studies/{id}/resume` (409 fuera de
  turno), `GET /studies/{id}/evaluations?ids=`, `GET /studies/{id}/traces`, `GET /estimate?modo=`,
  `GET /studies/{id}/export?formato=docx|pdf`, `/health`. CORS para `localhost:5173`.
- Demo sin claves: `LLM_PROVIDER=fixture` + `scripts/demo_kit.py`.

## Falta
- `POST /studies/{id}/remeasure` (hoy 404); `diff_metrics` ya existe en domain.
- `GET /studies/{id}` no devuelve simulación (`simulate_plan`) ni calidad del plan (`PlanGuard`).

## Siguiente tarea
- `feature/C-simulacion-calidad`: nodo o paso tras `plan` que llame a `simulate_plan` y `PlanGuard`
  (con degradación si no hay clave) y exponerlo en la vista del estudio.
- `feature/C-remeasure`: endpoint de re-medición con `diff_metrics`.

## No tocar
- Cifras: se calculan en `domain/`, nunca en nodos ni en la API.

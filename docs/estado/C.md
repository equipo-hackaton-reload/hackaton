# Zona C · orquestación y API (`application/`, `interfaces/api/`)

## En develop
- Grafo LangGraph (intake, market, prompts, run, judge, analyze, plan, write) con revisiones por
  `interrupt()` y checkpointer SQLite; `SqlStudyRepo`.
- API: `POST /studies`, `GET /studies`, `GET /studies/{id}`, `POST /studies/{id}/resume` (409 fuera de
  turno), `GET /studies/{id}/evaluations?ids=`, `GET /studies/{id}/traces`, `GET /estimate?modo=`,
  `GET /studies/{id}/export?formato=docx|pdf`, `/health`. CORS para `localhost:5173`.
- `revision_pendiente` es `null` cuando no hay revisión pendiente.
- Simulación y calidad del plan: el nodo `plan` añade `simulacion` (`simulate_plan`) y
  `calidad_plan` (PlanGuard). Sin claves de juez, `calidad_plan` es `null` y no bloquea. Si la
  persona edita el plan, ambas se recalculan. Las dos salen en `GET /studies/{id}`.
- Demo sin claves: `LLM_PROVIDER=fixture` + `scripts/demo_kit.py`.

## Falta
- `POST /studies/{id}/remeasure` (hoy 404); `diff_metrics` ya existe en domain y `analyze` ya
  compara con la medición anterior de la misma marca.
- Estudio de Alborada con DeepSeek real → `docs/ejemplos/` (bloqueado: falta `DEEPSEEK_API_KEY`).
- `StudyRunner.fallos` vive en memoria y se pierde al reiniciar.
- Con los precios de `settings`, un estudio real completo (624 llamadas, 4 motores) cuesta unos
  10,56 € y `BUDGET_EUR_MAX` es 5 €: hay que subir el tope o reducir el estudio.

## Siguiente tarea
- `feature/C-remeasure`: endpoint de re-medición que crea un estudio nuevo con el brief y el mercado
  confirmado del original.
- README de arranque reproducible (clonar, `uv sync`, `.env`, uvicorn, `npm run dev`).

## No tocar
- Cifras: se calculan en `domain/`, nunca en nodos ni en la API.

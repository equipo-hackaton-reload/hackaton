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
- Re-medición: `POST /studies/{id}/remeasure` (201; 409 si el estudio no está completado) crea un
  estudio nuevo con el brief y el mercado confirmado del original. Empieza en `prompts`, sin repetir
  intake ni la revisión de competidores; el plan nuevo sí pasa por revisión. `GET /studies/{id}`
  devuelve `metrics_delta` (null en la primera medición). En modo kit el delta es 0: mide
  repetibilidad, no una mejora.
- `JUDGE_PROVIDER=reglas` (por defecto `auto`): el juez de menciones y PlanGuard no llaman a ningún
  LLM aunque haya claves; DeepSeek solo hace intake, plan y redacción (< 0,10 €, minutos). Si las
  menciones se evaluaron por reglas (por elección, sin clave o en modo demo), la propuesta lo
  declara en sus limitaciones. PlanGuard ya no bloquea el plan si su API falla.
- Demo sin claves: `LLM_PROVIDER=fixture` + `scripts/demo_kit.py`.

## Falta
- Estudio de Alborada con DeepSeek real → `docs/ejemplos/` (bloqueado: falta `DEEPSEEK_API_KEY`).
  Dos formas: completo (juez DeepSeek, ≈1–2,5 € y 20–30 min) o rápido con `JUDGE_PROVIDER=reglas`.
- `StudyRunner.fallos` vive en memoria y se pierde al reiniciar.
- Con los precios de `settings`, un estudio real completo (624 llamadas, 4 motores) cuesta unos
  10,56 € y `BUDGET_EUR_MAX` es 5 €: hay que subir el tope o reducir el estudio.

## Siguiente tarea
- README de arranque reproducible (clonar, `uv sync`, `.env`, uvicorn, `npm run dev`).
- Estudio de Alborada con DeepSeek en cuanto haya `DEEPSEEK_API_KEY`.

## No tocar
- Cifras: se calculan en `domain/`, nunca en nodos ni en la API.

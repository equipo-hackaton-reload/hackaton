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
  LLM aunque haya claves; DeepSeek solo hace intake, plan y redacción (< 0,10 €, minutos). Si el
  nodo `judge` evaluó por reglas (por elección o sin clave), la propuesta lo declara en sus
  limitaciones; la demo en fixture explica en sus supuestos que usa etiquetas del kit y reglas.
  PlanGuard ya no bloquea el plan si su API falla.
- Demo sin claves: `LLM_PROVIDER=fixture` + `scripts/demo_kit.py`.
- README de arranque reproducible: requisitos, demo sin claves (API + web o `demo_kit.py`), claves,
  API, desarrollo y limitaciones. Comprobado desde cero en un worktree el 2026-10-21.

## Diferencial v0.4.0 (en curso)
- Base común: el checkpointer admite `stats_schemas`, `scenario_schemas`, `source_map_schemas`,
  `accuracy_schemas` y `application/diferencial.py`. `GET /studies/{id}` ya trae los bloques
  `rigor`, `escenarios`, `oportunidades_fuente`, `exactitud` y `mitigaciones`, en `null` hasta que
  llegue el dominio de cada uno (`feature/A-rigor-estadistico`, `A-escenarios`, `A-mapa-fuentes`,
  `A-exactitud-marca`).
- Forma del JSON para la web y el Word:
  - `rigor`: `{score_global: Intervalo|null, score_por_motor: {Motor: Intervalo},
    aparicion_por_motor: {Motor: Intervalo}, hallazgos: {finding_id: Significancia},
    deltas: {"score_global" | "tipo:dimension:valor": Significancia}}`.
  - `escenarios`: `[{id, elegido, escenario: EscenarioPlan}]`; solo uno elegido.
  - `oportunidades_fuente`: `[OportunidadFuente]`; `exactitud`: `[HallazgoExactitud]` (uno por
    marca); `mitigaciones`: `[AccionMitigacion]`.
- Pendiente, una PR por punto: (1) rigor y `JUDGE_VOTES`, (2) escenarios, (3) mapa de fuentes,
  (4) exactitud.

## Falta
- Estudio de Alborada con DeepSeek real → `docs/ejemplos/` (bloqueado: falta `DEEPSEEK_API_KEY`).
  Dos formas: completo (juez DeepSeek, ≈1–2,5 € y 20–30 min) o rápido con `JUDGE_PROVIDER=reglas`.
- `StudyRunner.fallos` vive en memoria y se pierde al reiniciar.
- Con los precios de `settings`, un estudio real completo (624 llamadas, 4 motores) cuesta unos
  10,56 € y `BUDGET_EUR_MAX` es 5 €: hay que subir el tope o reducir el estudio.

## Siguiente tarea
- Estudio de Alborada con DeepSeek en cuanto haya `DEEPSEEK_API_KEY`.
- Persistir `StudyRunner.fallos` para que el estado `error` sobreviva a un reinicio.

## No tocar
- Cifras: se calculan en `domain/`, nunca en nodos ni en la API.

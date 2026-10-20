# ADR 0005 · Orquestación con LangGraph, revisiones humanas con interrupts y checkpointer SQLite

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** C

## Contexto

Un estudio encadena pasos de naturaleza distinta. Unos son llamadas a LLM (estructurar el brief,
proponer el mercado, el plan y la redacción), otros son llamadas a motores y al juez, y otros son
cálculo puro del dominio. Dos pasos necesitan a una persona: confirmar los competidores antes de
gastar en ejecuciones y aprobar el plan antes de redactar. Esas pausas pueden durar horas, y el
estudio tiene que sobrevivir a un reinicio del servidor. El reto pide además trazar el coste,
respetar un presupuesto y que ninguna cifra de la propuesta salga del LLM.

## Decisión

- **LangGraph 1.x con un grafo lineal:** `intake → market → [revisión: competidores] → prompts →
  run → judge → analyze → plan → [revisión: plan] → write`. Cada nodo es
  `async def nodo(state, deps) -> dict` y devuelve solo lo que cambia. `traces` y `errores` se
  acumulan con un reductor.
- **Las revisiones humanas son nodos con `interrupt()`** y se reanudan con `Command(resume=...)`.
  - Competidores: el resume es un `Market` editado, o una aprobación. Queda
    `confirmado_por_humano=True` y el mercado debe contener la marca del brief.
  - Plan: el resume es un `Plan` editado, o una aprobación. Si es un plan editado, se vuelve a
    validar contra el brief.
  - Antes de `interrupt()` no hay efectos, porque el nodo se repite al reanudar. La API valida el
    payload antes de reanudar y responde 409 o 422.
- **Checkpointer `AsyncSqliteSaver` sobre `DATABASE_URL`**, con `thread_id = study_id`. Comparte la
  base con el repositorio, que usa WAL. Las llamadas al repositorio, que son síncronas, se hacen
  fuera del bucle de eventos (`asyncio.to_thread`); si no, el bucle se bloquea con la transacción
  del checkpointer abierta («database is locked»). El serializador permite de forma explícita los
  modelos de `domain.schemas`.
- **Qué hace el LLM y qué hace el código:**
  - LLM (`LLM.structured`, siempre con un modelo validado): brief → `BriefSummary`, mercado
    propuesto, banco de prompts (solo en modo real), `Plan` y textos de la `Proposal`.
  - Código: la conciliación de ids del mercado con el kit, las ejecuciones, el presupuesto, las
    métricas, los hallazgos, la comparación con la medición anterior y la validación del plan.
    `write` pide `ProposalDraft`, exclusivamente textos, con interpretaciones por id de hallazgo.
    El código construye `Proposal` con métricas, ranking, hallazgos, plan aprobado, objetivos,
    presupuesto, hitos y responsabilidades. `Proposal.marcas` sale de `Market` (id → nombre).
    La narrativa puede citar cifras recibidas, pero no genera los campos numéricos estructurados.
- **El plan se valida contra el brief** (`validate_plan_against_brief` y los hallazgos enlazados).
  Si falla, se reintenta una vez con las violaciones en el `state`. Si siguen, el plan llega a la
  revisión con las violaciones en `errores`.
- **El modo kit no necesita ninguna API para ejecutar y medir.** Los prompts son el banco del kit
  instanciado, los motores son `KitEngine` y, si falta la clave del juez, las evaluaciones salen
  de la detección por reglas (y se anota). Con `LLM_PROVIDER=fixture`, `FixtureLLM` devuelve el
  brief, plan y textos de ejemplo de Alborada, derivados de las fixtures golden y distribuidos en
  el paquete sin importar tests ni pytest. No interpreta otras marcas. Sus trazas cuestan 0.
  Sin claves de juez, `FixtureJudge` usa detección con fuerza 1 si aparece; no inventa sentimiento.
  El informe identifica explícitamente el modo demo y las evaluaciones por reglas.
- **Reintentos:** los nodos que llaman a servicios externos usan `RetryPolicy` (3 intentos, espera
  exponencial 1 s → 16 s) solo ante errores transitorios (red, 5xx). `BudgetExceeded`,
  `MissingCredentialError` y las salidas inválidas del LLM no se reintentan.
- **Presupuesto por estudio:** se reconstruye en cada nodo a partir de las `traces` del estado, así
  que sobrevive a las reanudaciones. `run` mira el saldo antes de cada llamada; como el coste se
  conoce al terminar, el gasto puede pasarse del máximo en las llamadas que ya estaban en curso.
- **Persistencia (`StudyRepo` → `SqlStudyRepo`, SQLModel):** hay una tabla por resultado, con clave
  compuesta (`study_id`, `id`) y el modelo completo como JSON. Los `save_*` son idempotentes porque
  los nodos se pueden repetir. Las tablas se crean con `create_all`, sin migraciones; Alembic queda
  para después del hackathon.
- **API:** `StudyRunner` encapsula el grafo (crear, lanzar, reanudar, consultar). FastAPI lanza el
  grafo con `BackgroundTasks` y muestra el estado del checkpoint. Si el grafo falla, el estudio
  queda en estado `error` con el mensaje.

## Consecuencias

- **Un estudio pausado sobrevive a un reinicio:** el e2e reabre el checkpointer entre las dos
  revisiones y completa el estudio.
- **La demo de Nivel 1 corre en CI sin claves** (`tests/e2e/test_kit_pipeline.py`): 624 ejecuciones,
  propuesta válida, todo persistido con el mismo `study_id` y coste 0.
- **El `Study` se crea antes del brief estructurado:** `POST /studies` guarda un brief vacío y
  `brand_id` vacío. `intake` y `market` los rellenan. Hasta entonces, el estudio no aparece al
  filtrar por marca.
- **El estado de fallo vive en memoria** (`StudyRunner.fallos`) y se pierde al reiniciar; el
  checkpoint sigue en el último paso completado.
- **SQLite con un solo proceso:** con varios workers habría que cambiar a Postgres (el checkpointer
  `langgraph-checkpoint-postgres` y el repositorio por `DATABASE_URL`).
- **Integración con B y E:** `build_engines(settings, modo, brand_ids)` se instancia para el modo
  real después de confirmar el mercado, con presupuesto compartido; no se duplica el gasto ya
  registrado por el motor. `/export` usa el puerto `Exporter` con `DocxExporter`/`PdfExporter`.
  Antes de completar la propuesta devuelve 409; sin LibreOffice, PDF devuelve 503.
- **Multipart:** `python-multipart` es dependencia directa. La API acepta texto, Word, JSON y
  formularios multipart; no hace falta una instalación adicional para subir el brief.
- **Demo HTTP reproducible:** `LLM_PROVIDER=fixture uv run uvicorn posiq.interfaces.api.main:app`
  y `uv run python scripts/demo_kit.py`. El script crea el estudio, espera y confirma competidores,
  espera y aprueba el plan y descarga el Word a `data/demo/` (ignorado en Git). El modo fixture es
  una demostración sintética explícita, no una prueba de calidad semántica ni de APIs reales.
- **Estado observable:** mientras el grafo sigue activo se devuelve `en_curso`, aunque un nodo
  haya persistido el estado de revisión, evitando reanudar antes de alcanzar `interrupt()`.

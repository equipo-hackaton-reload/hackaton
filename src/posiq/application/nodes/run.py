"""Nodo `run`: lanza cada prompt a cada motor y registra las `Run`.

- Modo real: `REPETICIONES_REAL` repeticiones por prompt y motor. `marcas_a_evaluar` pasa a ser el
  mercado confirmado, que es lo que se va a juzgar.
- Modo kit: todas las repeticiones que existan en el kit; si un motor no tiene ese prompt
  (`KitMissError` en la primera repetición) se salta y se anota en `errores`.

Antes de cada llamada se mira el presupuesto; si se agota, se para y se anota. Cada `Run` con coste
deja una `Trace` (las del kit cuestan 0 y no la dejan). Los pares prompt × motor van en paralelo
(`CONCURRENCIA`); dentro de un par, las repeticiones van en orden. Como el coste se conoce al
terminar cada llamada, el gasto puede pasarse del máximo en las llamadas que ya estaban en curso
(como mucho `CONCURRENCIA - 1`).
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from posiq.adapters.budget import Budget, BudgetExceeded
from posiq.adapters.engines.base import RealEngine
from posiq.adapters.engines.kit import KitMissError
from posiq.application.deps import Deps, cost_update, db, persist_traces, study_budget
from posiq.application.state import StudyState
from posiq.domain.schemas import PromptInstance, Run, Trace
from posiq.ports import Engine

REPETICIONES_REAL = 3
MAX_REPETICIONES_KIT = 10
CONCURRENCIA = 8


class _Run:
    """Estado compartido de las tareas del nodo (se ejecutan en el mismo bucle de eventos)."""

    def __init__(self, budget: Budget) -> None:
        self.budget = budget
        self.traces: list[Trace] = []
        self.errores: list[str] = []
        self.sin_kit: dict[str, list[str]] = {}
        self.agotado = False

    def stop(self, motivo: str) -> None:
        if not self.agotado:
            self.agotado = True
            self.errores.append(f"run: presupuesto agotado, se paran las ejecuciones ({motivo})")


def _trace(run: Run, engine: Engine, prompt: PromptInstance, start: float) -> Trace:
    return Trace(
        study_id=run.study_id,
        nodo=f"run:{engine.name}",
        modelo=run.modelo or engine.name,
        prompt_version=f"banco:{prompt.template_id}",
        tokens_in=run.tokens or 0,
        tokens_out=0,
        coste_eur=run.coste_eur,
        duracion_ms=round((time.perf_counter() - start) * 1000),
        fecha=datetime.now(UTC),
    )


async def _pair(
    ctx: _Run,
    state: StudyState,
    prompt: PromptInstance,
    engine: Engine,
    semaphore: asyncio.Semaphore,
) -> list[Run]:
    kit = state["modo"] == "kit"
    marcas = [b.id for b in state["market"].marcas]
    runs: list[Run] = []
    async with semaphore:
        for repeticion in range(1, (MAX_REPETICIONES_KIT if kit else REPETICIONES_REAL) + 1):
            if ctx.agotado:
                break
            if ctx.budget.remaining_eur <= 0:
                ctx.stop(f"{ctx.budget.total_eur:.4f} €")
                break
            start = time.perf_counter()
            try:
                run = await asyncio.to_thread(
                    engine.ask, prompt, repeticion=repeticion, study_id=state["study_id"]
                )
            except KitMissError:
                if repeticion == 1:
                    ctx.sin_kit.setdefault(prompt.id, []).append(engine.name)
                break
            except BudgetExceeded as exc:
                ctx.stop(str(exc))
                break
            if not kit:
                run = run.model_copy(update={"marcas_a_evaluar": marcas})
            runs.append(run)
            if run.coste_eur > 0 or run.origen == "api":
                trace = _trace(run, engine, prompt, start)
                try:
                    # Los adaptadores reales ya registran su llamada en el presupuesto compartido.
                    if not (
                        isinstance(engine, RealEngine)
                        and engine.budget is ctx.budget
                        and run.coste_eur > 0
                    ):
                        ctx.budget.record(trace)
                except BudgetExceeded as exc:
                    ctx.stop(str(exc))
    return runs


async def run(state: StudyState, deps: Deps) -> dict[str, Any]:
    ctx = _Run(study_budget(deps, state))
    initial_traces = len(ctx.budget.traces)
    engines = (
        deps.engine_factory([b.id for b in state["market"].marcas], ctx.budget)
        if deps.engine_factory is not None
        else deps.engines
    )
    if not engines:
        raise RuntimeError(f"no hay motores configurados para el modo {state['modo']}")
    semaphore = asyncio.Semaphore(CONCURRENCIA)
    pairs = [(p, e) for p in state["prompts"] for e in engines]
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(_pair(ctx, state, p, e, semaphore)) for p, e in pairs]
    runs = [r for t in tasks for r in t.result()]
    ctx.traces = ctx.budget.traces[initial_traces:]

    for prompt_id, motores in ctx.sin_kit.items():
        ctx.errores.append(f"run: el kit no tiene {prompt_id} para {', '.join(motores)}; se salta")
    if not runs:
        raise RuntimeError("run: ninguna ejecución; no hay nada que juzgar")

    await db(deps.repo.save_runs, state["study_id"], runs)
    if ctx.traces:
        await persist_traces(deps, state, ctx.traces)
    return {"runs": runs, "errores": ctx.errores, **cost_update(state, ctx.traces)}

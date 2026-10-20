"""Dependencias de los nodos y utilidades comunes (LLM, presupuesto, estudio nuevo)."""

import asyncio
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel

from posiq.adapters.budget import Budget
from posiq.application.state import StudyState
from posiq.domain.schemas import (
    Brand,
    BriefSummary,
    Evaluation,
    Market,
    ModoEstudio,
    Run,
    Study,
    Trace,
)
from posiq.domain.scoring import SCORE_VERSION
from posiq.ports import LLM, Engine, StudyRepo
from posiq.settings import Settings

VERSION_METODOLOGIA = "reload-geo-2026"


class AsyncJudge(Protocol):
    """Lo que el grafo necesita de un juez: evaluar en lote sin bloquear y exponer sus trazas.

    `adapters.judge.SystemOneJudge` lo cumple; `ports.Judge.evaluate` es la versión síncrona.
    """

    name: str
    traces: list[Trace]

    async def aevaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]: ...


JudgeFactory = Callable[[Market, Budget], AsyncJudge]
BudgetFactory = Callable[[str], Budget]


@dataclass(frozen=True)
class Deps:
    """`budget` crea el presupuesto de un estudio (con su `study_id`); `judge_factory` construye
    el juez con el mercado confirmado y ese presupuesto."""

    llm: LLM
    engines: list[Engine]
    judge_factory: JudgeFactory
    repo: StudyRepo
    budget: BudgetFactory
    settings: Settings


def study_budget(deps: Deps, state: StudyState) -> Budget:
    """Presupuesto del estudio con lo ya gastado (sale del estado: sobrevive a reanudaciones)."""
    budget = deps.budget(state["study_id"])
    budget.traces.extend(state.get("traces", []))
    return budget


def cost_update(state: StudyState, nuevas: Sequence[Trace]) -> dict[str, Any]:
    """Actualización de `traces` (solo las nuevas) y del coste acumulado."""
    return {
        "traces": list(nuevas),
        "coste_acumulado_eur": state.get("coste_acumulado_eur", 0.0)
        + sum(t.coste_eur for t in nuevas),
    }


async def db[**P, R](fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """Llamada al repositorio (síncrono) fuera del bucle de eventos.

    El checkpointer comparte la base SQLite: si el bucle se bloquea en una escritura del repo, el
    checkpointer no puede cerrar su transacción y ambos se quedan esperando («database is locked»).
    """
    return await asyncio.to_thread(fn, *args, **kwargs)


async def persist_traces(deps: Deps, state: StudyState, nuevas: Sequence[Trace]) -> None:
    await db(deps.repo.save_traces, state["study_id"], [*state.get("traces", []), *nuevas])


async def structured[T: BaseModel](
    deps: Deps, state: StudyState, schema: type[T], prompt_name: str, payload: dict[str, Any]
) -> tuple[T, Trace]:
    """`LLM.structured` sin bloquear el bucle y con la traza apuntada en el presupuesto.

    `payload` es DATO (ya serializado a JSON): el adaptador lo manda en el mensaje de usuario.
    """
    output, trace = await asyncio.to_thread(
        deps.llm.structured, schema, prompt_name, payload, study_id=state["study_id"]
    )
    study_budget(deps, state).record(trace)
    return output, trace


def dump(value: Any) -> Any:
    """Modelos (o listas de modelos) a JSON serializable para el `state` de un prompt."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list | tuple):
        return [dump(v) for v in value]
    return value


def brief_pendiente() -> BriefSummary:
    """Brief vacío del estudio recién creado: el nodo `intake` lo sustituye por el real."""
    return BriefSummary(
        marca="",
        sector="",
        subsector="",
        servicios_prioritarios=[],
        publicos=[],
        ciudades=[],
        competidores_declarados=[],
        equipo=[],
        restricciones=[],
        objetivos=[],
        audiencia_del_entregable="",
        tono="",
    )


def new_study(modo: ModoEstudio, *, study_id: str | None = None) -> Study:
    """Estudio en curso, aún sin marca ni brief (los rellenan `intake` y `market`)."""
    return Study(
        id=study_id or uuid.uuid4().hex,
        brand_id="",
        brief=brief_pendiente(),
        modo=modo,
        creado_en=datetime.now(UTC),
        version_metodologia=VERSION_METODOLOGIA,
        score_version=SCORE_VERSION,
    )

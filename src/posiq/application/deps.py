"""Dependencias de los nodos y utilidades comunes (LLM, presupuesto, estudio nuevo)."""

import asyncio
import uuid
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel

from posiq.adapters.budget import Budget, BudgetExceeded
from posiq.adapters.llm.openai_compat import LLMOutputError
from posiq.application.state import StudyState
from posiq.domain.quality_schemas import PlanQuality
from posiq.domain.schemas import (
    Brand,
    BriefSummary,
    Evaluation,
    Finding,
    Market,
    ModoEstudio,
    Plan,
    Run,
    Study,
    Trace,
)
from posiq.domain.scoring import SCORE_VERSION
from posiq.ports import LLM, Engine, StudyRepo, WebFetcher
from posiq.settings import Settings

VERSION_METODOLOGIA = "reload-geo-2026"


class AsyncJudge(Protocol):
    """Lo que el grafo necesita de un juez: evaluar en lote sin bloquear y exponer sus trazas.

    `adapters.judge.SystemOneJudge` lo cumple; `ports.Judge.evaluate` es la versión síncrona.
    """

    name: str
    traces: list[Trace]

    async def aevaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]: ...


class PlanAssessor(Protocol):
    """Lo que el grafo necesita de PlanGuard: evaluar el plan sin bloquear.

    Apunta sus llamadas en el presupuesto con el que se construye; de ahí salen sus trazas.
    """

    async def aassess(
        self, plan: Plan, findings: Sequence[Finding], brief: BriefSummary
    ) -> PlanQuality: ...


JudgeFactory = Callable[[Market, Budget], AsyncJudge]
BudgetFactory = Callable[[str], Budget]
PlanGuardFactory = Callable[[Budget], PlanAssessor]


@dataclass(frozen=True)
class Deps:
    """`budget` crea el presupuesto de un estudio (con su `study_id`); `judge_factory` construye
    el juez con el mercado confirmado y ese presupuesto. Sin `plan_guard_factory` (sin claves de
    juez), la calidad del plan no se evalúa."""

    llm: LLM
    engines: list[Engine]
    judge_factory: JudgeFactory
    repo: StudyRepo
    budget: BudgetFactory
    settings: Settings
    engine_factory: Callable[[list[str], Budget], list[Engine]] | None = None
    plan_guard_factory: PlanGuardFactory | None = None
    # Auditoría técnica de la web (ADR 0019). None: auditoría apagada (`WEB_AUDIT=off`).
    web_fetcher: WebFetcher | None = None


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


_TRAZAS_DE_FALLO = "posiq_trazas_de_fallo"


def adjuntar_trazas(exc: BaseException, traces: Sequence[Trace]) -> None:
    """Apunta en `exc` las trazas de llamadas ya pagadas que el nodo no llegó a devolver.

    Un nodo que lanza no actualiza el estado; el `StudyRunner` las recoge con `trazas_de_fallo` y
    las suma a las trazas y al coste del estudio (ADR 0018). Sin duplicados.
    """
    previas: list[Trace] = getattr(exc, _TRAZAS_DE_FALLO, [])
    vistas = {id(t) for t in previas}
    setattr(exc, _TRAZAS_DE_FALLO, [*previas, *(t for t in traces if id(t) not in vistas)])


def trazas_de_fallo(exc: BaseException) -> list[Trace]:
    return list(getattr(exc, _TRAZAS_DE_FALLO, []))


@contextmanager
def trazas_si_falla(traces: Sequence[Trace]) -> Iterator[None]:
    """Si el bloque lanza, adjunta `traces` (leídas en ese momento) a la excepción."""
    try:
        yield
    except BaseException as exc:
        adjuntar_trazas(exc, traces)
        raise


def record_or_raise(deps: Deps, state: StudyState, trace: Trace) -> None:
    """Apunta `trace` en el presupuesto; si lo supera, la traza viaja con `BudgetExceeded`."""
    try:
        study_budget(deps, state).record(trace)
    except BudgetExceeded as exc:
        adjuntar_trazas(exc, [trace])
        raise


async def structured[T: BaseModel](
    deps: Deps, state: StudyState, schema: type[T], prompt_name: str, payload: dict[str, Any]
) -> tuple[T, Trace]:
    """`LLM.structured` sin bloquear el bucle y con la traza apuntada en el presupuesto.

    `payload` es DATO (ya serializado a JSON): el adaptador lo manda en el mensaje de usuario.
    Si la llamada falla tras intentos ya cobrados (`LLMOutputError.trace`), esa traza cuenta en el
    presupuesto y viaja con la excepción para que el estudio la registre.
    """
    try:
        output, trace = await asyncio.to_thread(
            deps.llm.structured, schema, prompt_name, payload, study_id=state["study_id"]
        )
    except LLMOutputError as exc:
        if exc.trace is not None:
            adjuntar_trazas(exc, [exc.trace])
            try:
                record_or_raise(deps, state, exc.trace)
            except BudgetExceeded as over:
                raise over from exc
        raise
    record_or_raise(deps, state, trace)
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

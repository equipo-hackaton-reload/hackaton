"""Grafo LangGraph de un estudio.

    intake → market → [revisión: competidores] → prompts → run → judge → web_audit → analyze
           → diferencial → plan → [revisión: plan] → write → END

`web_audit` (ADR 0019) no descarga nada con `WEB_AUDIT=off` (por defecto).

Las revisiones son nodos con `interrupt()`; se reanudan con `Command(resume=payload)`. El hilo del
checkpointer es el estudio (`thread_id = study_id`), así que un estudio pausado sobrevive a un
reinicio del proceso. Los nodos que llaman a servicios externos se reintentan con espera creciente
ante errores transitorios (red, 5xx); los errores de lógica, presupuesto o credenciales no.
"""

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy
from pydantic import BaseModel

from posiq.application import diferencial, nodes
from posiq.application.deps import Deps
from posiq.application.state import StudyState
from posiq.domain import (
    accuracy_schemas,
    competitor_gap_schemas,
    quality_schemas,
    scenario_schemas,
    schemas,
    simulation_schemas,
    source_map_schemas,
    stats_schemas,
    web_audit_schemas,
)

Node = Callable[[StudyState, Deps], Awaitable[dict[str, Any]]]

RETRY = RetryPolicy(max_attempts=3, initial_interval=1.0, backoff_factor=2.0, max_interval=16.0)

# (nombre, función, llama a servicios externos)
PIPELINE: list[tuple[str, Node, bool]] = [
    ("intake", nodes.intake, True),
    ("market", nodes.market, True),
    ("review_competidores", nodes.review_competidores, False),
    ("prompts", nodes.prompts, True),
    ("run", nodes.run, True),
    ("judge", nodes.judge, True),
    ("web_audit", nodes.web_audit, True),
    ("analyze", nodes.analyze, False),
    ("diferencial", nodes.diferencial, False),
    ("plan", nodes.plan, True),
    ("review_plan", nodes.review_plan, False),
    ("write", nodes.write, True),
]

StudyGraph = CompiledStateGraph[StudyState, None, StudyState, StudyState]


def _bind(fn: Node, deps: Deps) -> Callable[[StudyState], Awaitable[dict[str, Any]]]:
    async def node(state: StudyState) -> dict[str, Any]:
        return await fn(state, deps)

    node.__name__ = fn.__name__
    return node


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver[Any] | None) -> StudyGraph:
    builder = StateGraph(StudyState)
    previous = START
    for name, fn, external in PIPELINE:
        builder.add_node(  # type: ignore[call-overload]
            name, _bind(fn, deps), retry_policy=RETRY if external else None
        )
        builder.add_edge(previous, name)
        previous = name
    builder.add_edge(previous, END)
    return builder.compile(checkpointer=checkpointer)


# Módulos cuyos modelos viajan en el estado. Los del dominio fuera de `schemas.py` (simulación,
# calidad, diferencial y auditoría web) existen para no tocar el contrato; `diferencial` agrupa
# sus resultados.
STATE_MODULES = (
    schemas,
    simulation_schemas,
    quality_schemas,
    stats_schemas,
    scenario_schemas,
    source_map_schemas,
    accuracy_schemas,
    competitor_gap_schemas,
    web_audit_schemas,
    diferencial,
)


def serializer() -> JsonPlusSerializer:
    """Serializador del checkpointer con los modelos del dominio permitidos explícitamente."""
    allowed = [
        (module.__name__, name)
        for module in STATE_MODULES
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, BaseModel) and obj.__module__ == module.__name__
    ]
    return JsonPlusSerializer(allowed_msgpack_modules=allowed)


def sqlite_path(database_url: str) -> str:
    """Ruta del fichero de una URL `sqlite:///ruta` (la misma base que el repositorio)."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(f"el checkpointer necesita una DATABASE_URL de SQLite: {database_url}")
    path = database_url.removeprefix(prefix)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


@asynccontextmanager
async def sqlite_checkpointer(database_url: str) -> AsyncIterator[AsyncSqliteSaver]:
    async with aiosqlite.connect(sqlite_path(database_url)) as conn:
        saver = AsyncSqliteSaver(conn, serde=serializer())
        await saver.setup()
        yield saver

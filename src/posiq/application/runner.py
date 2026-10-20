"""Ciclo de vida de los estudios sobre el grafo: crear, lanzar, reanudar y consultar.

Hay un grafo por modo (cada uno con sus `Deps`: motores del kit o reales) y todos comparten el
checkpointer. Un fallo dentro del grafo no se propaga a quien lo lanzó en segundo plano: se guarda
en `fallos` y la API lo enseña como estado `error`.
"""

import logging
from typing import Any, Literal, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from pydantic import ValidationError

from posiq.application.deps import Deps, new_study
from posiq.application.graph import StudyGraph, build_graph
from posiq.application.nodes.review import parse_market, parse_plan
from posiq.application.state import StudyState, initial_state
from posiq.domain.schemas import ModoEstudio, Study
from posiq.ports import StudyRepo

log = logging.getLogger(__name__)

Revision = Literal["competidores", "plan"]
REVIEW_NODES: dict[Revision, str] = {
    "competidores": "review_competidores",
    "plan": "review_plan",
}


class ResumeError(ValueError):
    """El resume no corresponde a la revisión pendiente o su payload no valida."""

    def __init__(self, message: str, *, conflict: bool = False) -> None:
        super().__init__(message)
        self.conflict = conflict


class StudyRunner:
    def __init__(
        self,
        deps_by_modo: dict[ModoEstudio, Deps],
        checkpointer: BaseCheckpointSaver[Any],
        repo: StudyRepo,
    ) -> None:
        self.graphs: dict[ModoEstudio, StudyGraph] = {
            modo: build_graph(deps, checkpointer) for modo, deps in deps_by_modo.items()
        }
        self.repo = repo
        self.fallos: dict[str, str] = {}
        self.en_marcha: set[str] = set()

    @staticmethod
    def config(study_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": study_id}}

    def create(self, modo: ModoEstudio) -> Study:
        if modo not in self.graphs:
            raise ValueError(f"modo «{modo}» no disponible; hay {sorted(self.graphs)}")
        study = new_study(modo)
        self.repo.save_study(study)
        return study

    async def start(self, study: Study, brief_texto: str) -> None:
        await self._drive(study, initial_state(study, brief_texto))

    async def resume(self, study_id: str, payload: Any) -> None:
        await self._drive(self.repo.get_study(study_id), Command(resume=payload))

    async def _drive(self, study: Study, graph_input: StudyState | Command[Any]) -> None:
        self.en_marcha.add(study.id)
        self.fallos.pop(study.id, None)
        try:
            await self.graphs[study.modo].ainvoke(graph_input, self.config(study.id))
        except Exception as exc:  # el grafo corre en segundo plano: el fallo se consulta por la API
            log.exception("estudio %s falló", study.id)
            self.fallos[study.id] = f"{type(exc).__name__}: {exc}"
        finally:
            self.en_marcha.discard(study.id)

    async def state(self, study_id: str) -> tuple[StudyState, tuple[str, ...]]:
        """Valores del estado y nodos pendientes (`("review_plan",)` si espera esa revisión)."""
        study = self.repo.get_study(study_id)
        snapshot = await self.graphs[study.modo].aget_state(self.config(study_id))
        values = cast(StudyState, snapshot.values)
        return values, tuple(snapshot.next)

    async def check_resume(self, study_id: str, revision: Revision, payload: Any) -> None:
        """Comprueba que el estudio espera esa revisión y que el payload valida (si no, error)."""
        if study_id in self.en_marcha:
            raise ResumeError(
                "el estudio está en marcha; espera a que pida la revisión", conflict=True
            )
        values, pendientes = await self.state(study_id)
        if REVIEW_NODES[revision] not in pendientes:
            espera = values.get("revision_pendiente", "none") if pendientes else "none"
            raise ResumeError(
                f"el estudio no espera la revisión «{revision}» (pendiente: {espera})",
                conflict=True,
            )
        try:
            if revision == "competidores":
                parse_market(payload, values)
            else:
                parse_plan(payload, values)
        except (ValidationError, ValueError) as exc:
            raise ResumeError(f"payload de «{revision}» inválido: {exc}") from exc

    def estado(self, study: Study) -> str:
        if study.id in self.fallos:
            return "error"
        return "en_curso" if study.id in self.en_marcha else study.estado

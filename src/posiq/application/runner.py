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

from posiq.application.deps import Deps, db, new_study, trazas_de_fallo
from posiq.application.diferencial import MedicionAnterior
from posiq.application.graph import StudyGraph, build_graph
from posiq.application.nodes.review import parse_market, parse_plan
from posiq.application.state import StudyState, initial_state
from posiq.domain.schemas import BriefSummary, Market, ModoEstudio, Study, Trace
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


class RemeasureError(ValueError):
    """El estudio no se puede re-medir: no está completado o le falta el mercado confirmado."""


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

    async def prepare_remeasure(
        self,
        original_id: str,
        *,
        brief: BriefSummary | None = None,
        market: Market | None = None,
        reutilizar_prompts: bool = True,
    ) -> Study:
        """Estudio nuevo de la misma marca con el brief y el mercado confirmado de `original_id`.

        El hilo nuevo se siembra como si ya hubiera pasado la revisión de competidores, así que
        `continue_` arranca en `prompts`: las dos mediciones comparan las mismas marcas y `analyze`
        calcula la diferencia con la medición anterior. `KeyError` si el original no existe.

        También se siembran los prompts del original (el nodo `prompts` los reutiliza): en modo
        real, generarlos de nuevo con el LLM daría otro banco y otra huella
        (`domain.tracking.huella_banco`), y las dos mediciones dejarían de ser comparables. Y la
        `medicion_anterior` (métricas, prompts, ejecuciones y evaluaciones del original), para que
        el nodo `diferencial` diga qué deltas salen del margen de error.

        `brief` y `market` sustituyen a los del original: la configuración VIGENTE de la marca
        (perfil y mercado versionados, `application.tracking`). Con `reutilizar_prompts=False`
        (el perfil cambia servicios, ciudades o públicos en modo real) el banco se genera de nuevo
        y la serie compara sobre el núcleo común de preguntas.
        """
        original = self.repo.get_study(original_id)
        if original.estado != "completado":
            raise RemeasureError(
                f"solo se re-mide un estudio completado; {original_id} está «{original.estado}»"
            )
        values, _ = await self.state(original_id)
        market = market or values.get("market")
        if market is None or not market.confirmado_por_humano:
            raise RemeasureError(f"el estudio {original_id} no tiene el mercado confirmado")

        brief = brief or values["brief"]
        study = new_study(original.modo).model_copy(
            update={"brand_id": original.brand_id, "brief": brief}
        )
        self.repo.save_study(study)
        seed: StudyState = {
            **initial_state(study, values.get("brief_texto", "")),
            "brief": brief,
            "market": market,
        }
        if reutilizar_prompts and values.get("prompts"):
            seed["prompts"] = list(values["prompts"])
        if all(k in values for k in ("metrics", "prompts", "runs", "evaluations")):
            seed["medicion_anterior"] = MedicionAnterior(
                study_id=original_id,
                metrics=values["metrics"],
                prompts=values["prompts"],
                runs=values["runs"],
                evaluations=values["evaluations"],
            )
        await self.graphs[study.modo].aupdate_state(
            self.config(study.id), seed, as_node=REVIEW_NODES["competidores"]
        )
        return study

    async def continue_(self, study: Study) -> None:
        """Avanza el grafo desde su último checkpoint (estudio sembrado por `prepare_remeasure`)."""
        await self._drive(study, None)

    async def _drive(self, study: Study, graph_input: StudyState | Command[Any] | None) -> None:
        self.en_marcha.add(study.id)
        self.fallos.pop(study.id, None)
        try:
            await self.graphs[study.modo].ainvoke(graph_input, self.config(study.id))
        except Exception as exc:  # el grafo corre en segundo plano: el fallo se consulta por la API
            log.exception("estudio %s falló", study.id)
            self.fallos[study.id] = f"{type(exc).__name__}: {exc}"
            await self._registrar_trazas_de_fallo(study, trazas_de_fallo(exc))
        finally:
            self.en_marcha.discard(study.id)

    async def _registrar_trazas_de_fallo(self, study: Study, nuevas: list[Trace]) -> None:
        """Suma al estudio las llamadas pagadas del nodo que falló (ADR 0018).

        El nodo que lanza no actualiza el estado: sin esto, sus intentos fallidos se pagaban sin
        `Trace` ni coste. Se escriben en el checkpoint (cuentan en el presupuesto si el estudio
        sigue) y en el repositorio.
        """
        if not nuevas:
            return
        config = self.config(study.id)
        graph = self.graphs[study.modo]
        try:
            snapshot = await graph.aget_state(config)
            values = cast(StudyState, snapshot.values)
            coste = values.get("coste_acumulado_eur", 0.0) + sum(t.coste_eur for t in nuevas)
            await graph.aupdate_state(config, {"traces": nuevas, "coste_acumulado_eur": coste})
            # Fuera del bucle de eventos, como el resto de escrituras del repo (`deps.db`).
            await db(self.repo.save_traces, study.id, [*values.get("traces", []), *nuevas])
        except Exception:  # registrar el coste no debe tapar el fallo original
            log.exception("no se pudieron registrar las trazas del fallo de %s", study.id)

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

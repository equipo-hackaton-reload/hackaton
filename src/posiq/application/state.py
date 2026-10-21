"""Estado del grafo de un estudio. Viaja por los nodos y se guarda en el checkpointer.

`traces` y `errores` se acumulan (cada nodo devuelve solo lo nuevo); el resto de claves las
sustituye el nodo que las produce. `coste_acumulado_eur` es siempre la suma de `traces`.
"""

import operator
from typing import Annotated, Literal, TypedDict

from posiq.application.diferencial import EscenarioGuardado, Rigor
from posiq.domain.accuracy_schemas import AccionMitigacion, HallazgoExactitud
from posiq.domain.quality_schemas import PlanQuality
from posiq.domain.schemas import (
    BriefSummary,
    Evaluation,
    Finding,
    Market,
    Metrics,
    MetricsDelta,
    ModoEstudio,
    Plan,
    PromptInstance,
    Proposal,
    Run,
    Study,
    Trace,
)
from posiq.domain.simulation_schemas import SimulationResult
from posiq.domain.source_map_schemas import OportunidadFuente

RevisionPendiente = Literal["none", "competidores", "plan"]


class StudyState(TypedDict, total=False):
    study_id: str
    modo: ModoEstudio
    brief_texto: str
    brief: BriefSummary
    market: Market
    prompts: list[PromptInstance]
    runs: list[Run]
    evaluations: list[Evaluation]
    # Juez que evaluó las menciones: su nombre, o "reglas" si solo hubo detección por reglas.
    juez: str
    metrics: Metrics
    metrics_delta: MetricsDelta | None
    findings: list[Finding]
    plan: Plan
    plan_violaciones: list[str]
    simulacion: SimulationResult | None
    calidad_plan: PlanQuality | None
    # Diferencial (v0.4.0): cifras del dominio; las claves faltan hasta que su nodo las calcula.
    rigor: Rigor | None
    escenarios: list[EscenarioGuardado] | None
    oportunidades_fuente: list[OportunidadFuente] | None
    exactitud: list[HallazgoExactitud] | None
    mitigaciones: list[AccionMitigacion] | None
    proposal: Proposal
    traces: Annotated[list[Trace], operator.add]
    coste_acumulado_eur: float
    revision_pendiente: RevisionPendiente
    errores: Annotated[list[str], operator.add]


def initial_state(study: Study, brief_texto: str) -> StudyState:
    return StudyState(
        study_id=study.id,
        modo=study.modo,
        brief_texto=brief_texto,
        traces=[],
        coste_acumulado_eur=0.0,
        revision_pendiente="none",
        errores=[],
    )

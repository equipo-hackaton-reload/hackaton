"""Estado del grafo de un estudio. Viaja por los nodos y se guarda en el checkpointer.

`traces` y `errores` se acumulan (cada nodo devuelve solo lo nuevo); el resto de claves las
sustituye el nodo que las produce. `coste_acumulado_eur` es siempre la suma de `traces`.
"""

import operator
from typing import Annotated, Literal, TypedDict

from posiq.application.diferencial import EscenarioGuardado, MedicionAnterior, Rigor
from posiq.domain.accuracy_schemas import AccionMitigacion, HallazgoExactitud
from posiq.domain.competitor_gap_schemas import BrechaCompetidores
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
from posiq.domain.web_audit_schemas import AuditoriaWeb

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
    # Diferencial (v0.4.0): cifras del dominio; las claves faltan hasta que su nodo las calcula
    # (`diferencial` tras `analyze`; `escenarios` en `plan` y, si se edita, en `review_plan`).
    rigor: Rigor | None
    competidores: BrechaCompetidores | None
    escenarios: list[EscenarioGuardado] | None
    oportunidades_fuente: list[OportunidadFuente] | None
    exactitud: list[HallazgoExactitud] | None
    mitigaciones: list[AccionMitigacion] | None
    # Solo en una re-medición: datos del estudio original para la significancia de los deltas.
    medicion_anterior: MedicionAnterior | None
    # Auditoría técnica de la web (ADR 0019), del nodo `web_audit` (entre `judge` y `analyze`).
    # None si está apagada o la marca no tiene dominio. `hallazgos_web` son sus hallazgos
    # técnicos: `analyze` los suma a `findings` solo si la auditoría es `origen="real"`; los de una
    # auditoría fixture (CASO SINTÉTICO) viajan aparte y no entran en el plan.
    auditoria_web: AuditoriaWeb | None
    hallazgos_web: list[Finding] | None
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

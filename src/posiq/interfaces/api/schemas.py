"""Cuerpos y respuestas de la API (contrato con la web, Zona D)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from posiq.application.diferencial import EscenarioGuardado, Rigor
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
    Motor,
    Plan,
    Proposal,
    Study,
)
from posiq.domain.simulation_schemas import SimulationResult
from posiq.domain.source_map_schemas import OportunidadFuente

EstadoApi = Literal[
    "en_curso",
    "esperando_revision_competidores",
    "esperando_revision_plan",
    "completado",
    "error",
]


class StudyCreate(BaseModel):
    brief_texto: str = Field(min_length=1)
    modo: ModoEstudio = "kit"


# El modo kit mide siempre las respuestas sintéticas de Alborada, se pegue el brief que se pegue
# (ADR 0018): la respuesta de `POST /studies` lo avisa para que nadie lo tome por una medición.
AVISO_KIT = "Modo kit: datos sintéticos de Alborada; el brief no cambia las mediciones"


class StudyCreated(BaseModel):
    study_id: str
    # Solo en modo kit (`AVISO_KIT`); `null` en modo real. Campo aditivo.
    aviso: str | None = None


class RemeasureCreated(BaseModel):
    """Estudio nuevo que re-mide `remedicion_de` con su brief y su mercado confirmado."""

    study_id: str
    remedicion_de: str


class StudyView(BaseModel):
    study: Study
    estado: EstadoApi
    revision_pendiente: Literal["competidores", "plan"] | None
    coste_acumulado_eur: float
    errores: list[str]
    brief: BriefSummary | None = None
    market: Market | None = None
    metrics: Metrics | None = None
    # Diferencia con la medición anterior de la marca (None en la primera medición).
    metrics_delta: MetricsDelta | None = None
    findings: list[Finding] | None = None
    plan: Plan | None = None
    # Ayudas a la revisión del plan: proyección del score (estimación con supuestos, no promesa)
    # y calidad por acción (None si no hay claves de juez).
    simulacion: SimulationResult | None = None
    calidad_plan: PlanQuality | None = None
    # Diferencial (v0.4.0): None hasta que el nodo `diferencial` (tras `analyze`) lo calcula;
    # `escenarios` llega con el plan. Un bloque que no se pudo calcular sigue en None.
    rigor: Rigor | None = None
    # Competidores declarados en el brief frente a los que pone la IA (ADR 0012).
    competidores: BrechaCompetidores | None = None
    escenarios: list[EscenarioGuardado] | None = None
    oportunidades_fuente: list[OportunidadFuente] | None = None
    exactitud: list[HallazgoExactitud] | None = None
    mitigaciones: list[AccionMitigacion] | None = None
    proposal: Proposal | None = None


class ResumeBody(BaseModel):
    revision: Literal["competidores", "plan"]
    payload: Any = None


class ResumeAccepted(BaseModel):
    study_id: str
    revision: Literal["competidores", "plan"]


class Evidence(BaseModel):
    """Una evaluación con el motor, el prompt y un extracto de la respuesta de su ejecución."""

    evaluation: Evaluation
    motor: Motor
    prompt: str
    texto_respuesta: str
    fuentes: list[str]

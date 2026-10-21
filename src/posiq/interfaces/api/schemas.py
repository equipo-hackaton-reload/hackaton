"""Cuerpos y respuestas de la API (contrato con la web, Zona D)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from posiq.domain.quality_schemas import PlanQuality
from posiq.domain.schemas import (
    BriefSummary,
    Evaluation,
    Finding,
    Market,
    Metrics,
    ModoEstudio,
    Motor,
    Plan,
    Proposal,
    Study,
)
from posiq.domain.simulation_schemas import SimulationResult

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


class StudyCreated(BaseModel):
    study_id: str


class StudyView(BaseModel):
    study: Study
    estado: EstadoApi
    revision_pendiente: Literal["competidores", "plan"] | None
    coste_acumulado_eur: float
    errores: list[str]
    brief: BriefSummary | None = None
    market: Market | None = None
    metrics: Metrics | None = None
    findings: list[Finding] | None = None
    plan: Plan | None = None
    # Ayudas a la revisión del plan: proyección del score (estimación con supuestos, no promesa)
    # y calidad por acción (None si no hay claves de juez).
    simulacion: SimulationResult | None = None
    calidad_plan: PlanQuality | None = None
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

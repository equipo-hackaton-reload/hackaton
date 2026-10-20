"""Cuerpos y respuestas de la API (contrato con la web, Zona D)."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from posiq.domain.schemas import (
    BriefSummary,
    Finding,
    Market,
    Metrics,
    ModoEstudio,
    Plan,
    Proposal,
    Study,
)

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
    revision_pendiente: Literal["none", "competidores", "plan"]
    coste_acumulado_eur: float
    errores: list[str]
    brief: BriefSummary | None = None
    market: Market | None = None
    metrics: Metrics | None = None
    findings: list[Finding] | None = None
    plan: Plan | None = None
    proposal: Proposal | None = None


class ResumeBody(BaseModel):
    revision: Literal["competidores", "plan"]
    payload: Any = None


class ResumeAccepted(BaseModel):
    study_id: str
    revision: Literal["competidores", "plan"]

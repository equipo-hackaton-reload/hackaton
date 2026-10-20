"""Salida narrativa del redactor. Las cifras y los contratos finales los construye código."""

from pydantic import BaseModel, ConfigDict, Field

from posiq.domain.schemas import Riesgo


class ProposalDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resumen_ejecutivo: str = Field(min_length=1)
    contexto_alcance: str = Field(min_length=1)
    diagnostico: str = Field(min_length=1)
    competencia: str = Field(min_length=1)
    interpretacion_hallazgos: dict[str, str]
    estrategia: str = Field(min_length=1)
    prioridades: list[str] = Field(min_length=1)
    riesgos: list[Riesgo] = Field(min_length=1)
    supuestos: list[str] = Field(min_length=1)
    hoja_ruta: str = Field(min_length=1)

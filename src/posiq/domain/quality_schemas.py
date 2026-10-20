"""Modelos de la evaluación de calidad del plan (Nivel 3, N3.5). Fuera de `schemas.py`."""

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ActionQuality(_Model):
    """Juicio de una acción del plan. `probabilidades` guarda la probabilidad de cada Noul."""

    action_id: str
    es_especifica: bool
    coherente_con_hallazgo: bool
    respeta_restricciones: bool
    realista_para_equipo: bool
    calidad_global: int = Field(ge=0, le=3)
    probabilidades: dict[str, float]
    confianza: float = Field(ge=0, le=1)
    por_debajo_umbral: bool
    motivos: list[str] = []


class PlanQuality(_Model):
    """Informe de calidad del plan. Orienta la revisión humana; no bloquea nada."""

    study_id: str
    juez: str
    modelo: str
    acciones: list[ActionQuality]
    pct_especificas: float | None
    pct_coherentes: float | None
    pct_respetan_restricciones: float | None
    pct_realistas: float | None
    calidad_media: float | None
    por_debajo_umbral: list[str]
    baja_confianza: list[str]
    nota: str


class EvidenceCoverage(_Model):
    """Cuánta evidencia trazable hay detrás de hallazgos y acciones."""

    n_hallazgos: int = Field(ge=0)
    hallazgos_con_evidencia: int = Field(ge=0)
    pct_hallazgos: float | None
    n_acciones: int = Field(ge=0)
    acciones_con_hallazgos: int = Field(ge=0)
    pct_acciones: float | None
    hallazgos_sin_evidencia: list[str]
    acciones_sin_hallazgos: list[str]

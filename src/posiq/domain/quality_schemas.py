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

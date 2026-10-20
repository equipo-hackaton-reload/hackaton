"""Modelos de la simulación del impacto del plan (Nivel 3, N3.4).

Viven fuera de `schemas.py` para no tocar el contrato compartido.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Escenario(_Model):
    """Rango de un valor simulado: mínimo ≤ esperado ≤ máximo."""

    minimo: float
    esperado: float
    maximo: float

    @model_validator(mode="after")
    def _ordenado(self) -> Self:
        if not self.minimo <= self.esperado <= self.maximo:
            raise ValueError("se espera minimo <= esperado <= maximo")
        return self


class PhaseProjection(_Model):
    """Proyección acumulada tras completar una fase del plan (incluye las anteriores)."""

    fase: str
    indice: int = Field(ge=0)
    acciones: list[str]
    tasa_espontanea: Escenario
    score: Escenario


class SegmentChange(_Model):
    """Cambio simulado de la tasa espontánea de un segmento al terminar el plan."""

    segmento: str
    dimension: Literal["fase_motor", "ciudad"]
    n: float = Field(ge=0)
    tasa_actual: float = Field(ge=0, le=1)
    delta: Escenario
    acciones: list[str]


class IgnoredAction(_Model):
    action_id: str
    motivo: str


class SimulationResult(_Model):
    """Resultado de `simulate_plan`: estimación con supuestos declarados, no una predicción."""

    study_id: str
    marca_foco_id: str
    modelo_version: str
    score_actual: float | None
    tasa_espontanea_actual: float | None
    proyecciones: list[PhaseProjection]
    segmentos: list[SegmentChange]
    acciones_sin_efecto: list[IgnoredAction]
    supuestos: list[str]
    advertencia: str

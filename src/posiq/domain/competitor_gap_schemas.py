"""Modelos del contraste entre competidores declarados en el brief y los que pone la IA (ADR 0012).

Viven fuera de `schemas.py` para no tocar el contrato compartido. Las cifras (puestos, scores,
tasas y ventajas) las calcula `domain/competitor_gap.py`; aquí solo está la forma del resultado.
"""

from pydantic import BaseModel, ConfigDict, Field

from posiq.domain.schemas import Finding


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CompetidorMedido(_Model):
    """Una marca del mercado tal como la midió el estudio.

    `puesto`: posición en `Metrics.ranking` (1 = primera). `ventaja_puntos`: score de la marca −
    score de la marca foco (positivo = por delante). `tasa_espontanea` None = sin datos (n = 0).
    `nombre_declarado`: el nombre con el que la cita el brief, si la declara.
    """

    brand_id: str
    nombre: str
    declarado: bool
    nombre_declarado: str | None = None
    puesto: int | None = Field(default=None, ge=1)
    score: float | None = None
    ventaja_puntos: float | None = None
    tasa_espontanea: float | None = Field(default=None, ge=0, le=1)
    n_espontaneo: int = Field(default=0, ge=0)


class BrechaCompetidores(_Model):
    """Competidores que cree el cliente frente a los que pone la IA.

    - `declarados`: los competidores del brief resueltos a una marca del mercado, por ranking.
    - `no_resueltos`: nombres del brief que no casan con ninguna marca del mercado (no se midieron).
    - `no_declarados_por_delante`: marcas que la IA pone por delante de la foco y el brief no cita.
    - `sorpresas`: ids de las anteriores con ventaja ≥ `umbral_ventaja_puntos` (las relevantes).
    - `declarados_poco_mencionados`: ids de declarados con tasa espontánea < `umbral_tasa`.
    - `hallazgos`: `Finding` listos para la propuesta (vacío si no hay diferencia relevante).
    """

    study_id: str
    marca_foco_id: str
    puesto_foco: int | None = Field(default=None, ge=1)
    score_foco: float | None = None
    tasa_foco: float | None = Field(default=None, ge=0, le=1)
    n_marcas: int = Field(ge=0)
    declarados: list[CompetidorMedido]
    no_resueltos: list[str] = []
    no_declarados_por_delante: list[CompetidorMedido]
    sorpresas: list[str] = []
    declarados_poco_mencionados: list[str] = []
    umbral_ventaja_puntos: float
    umbral_tasa: float = Field(ge=0, le=1)
    hallazgos: list[Finding] = []

"""Modelos del mapa de fuentes del sector y de las oportunidades de fuente por marca.

Viven fuera de `schemas.py` para no tocar el contrato compartido. Las cuotas salen de las fuentes
citadas en las ejecuciones cruzadas con el catálogo (no de `Evaluation.tipo_fuente`).

Anonimización: una fuente solo entra en el mapa del sector si la citan respuestas sobre al menos
`MIN_MARCAS_SECTOR` marcas distintas, y el mapa nunca lleva datos de una marca concreta.
"""

from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from posiq.domain.schemas import Motor, TipoFuenteCatalogo

MIN_MARCAS_SECTOR: Final = 2

Propiedad = Literal["propio", "ganado"]
Puntuacion = Literal["Alta", "Media", "Baja"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FuenteSector(_Model):
    """Una fuente del sector. `propio` = tipo «Web propia» del catálogo; `ganado` = el resto.

    `cuota_citas`: fracción de todas las citas del sector que van a este dominio.
    `por_motor` / `por_segmento`: la misma cuota dentro de cada motor o segmento (0-1).
    """

    dominio: str
    tipo: TipoFuenteCatalogo | None
    propiedad: Propiedad
    citas: int = Field(ge=0)
    cuota_citas: float = Field(ge=0, le=1)
    por_motor: dict[Motor, float] = {}
    por_segmento: dict[str, float] = {}
    n_estudios: int = Field(ge=1)
    n_marcas: int = Field(ge=MIN_MARCAS_SECTOR)

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if (self.propiedad == "propio") != (self.tipo == "Web propia"):
            raise ValueError("propio si y solo si el tipo es «Web propia»")
        cuotas = [*self.por_motor.values(), *self.por_segmento.values()]
        if any(not 0 <= c <= 1 for c in cuotas):
            raise ValueError("las cuotas por motor y segmento van de 0 a 1")
        return self


class MapaFuentes(_Model):
    """Mapa agregado y anonimizado de las fuentes que citan los motores en un sector."""

    sector: str
    fuentes: list[FuenteSector]
    n_estudios: int = Field(ge=1)
    n_marcas: int = Field(ge=0)
    n_citas: int = Field(ge=0)
    min_marcas: int = MIN_MARCAS_SECTOR


class OportunidadFuente(_Model):
    """Fuente (dominio o tipo) donde la marca está menos presente que sus competidores.

    `presencia_*`: fracción de respuestas que citan la fuente entre las que mencionan a la marca
    (o, de media, a sus competidores). `gap` = competidores − marca. `valor` = cuota_sector × gap,
    y `puntuacion` lo clasifica en Alta, Media o Baja con umbrales documentados en el ADR.
    `evaluation_ids`: evidencias de la marca o de los competidores que respaldan el gap.
    """

    brand_id: str
    dominio: str | None = None
    tipo: TipoFuenteCatalogo | None = None
    cuota_sector: float = Field(ge=0, le=1)
    presencia_marca: float = Field(ge=0, le=1)
    presencia_competidores: float = Field(ge=0, le=1)
    gap: float
    valor: float
    puntuacion: Puntuacion
    evaluation_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _con_objetivo(self) -> Self:
        if self.dominio is None and self.tipo is None:
            raise ValueError("una oportunidad necesita dominio o tipo de fuente")
        return self

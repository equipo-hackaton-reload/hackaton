"""Modelos de exactitud de marca: qué afirman los motores sobre la marca y si es cierto.

Viven fuera de `schemas.py` para no tocar el contrato compartido. La verificación la hace código
contra los datos del brief. `riesgo_regulatorio` significa «a revisar por la clínica»: es una lista
explícita de expresiones, nunca un juicio de legalidad.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from posiq.domain.schemas import Motor, Palanca

TipoAfirmacion = Literal["servicio", "sede", "profesional", "precio", "resultado_clinico", "otro"]
EstadoVerificacion = Literal["correcta", "incorrecta", "no_verificable", "riesgo_regulatorio"]
OrigenAfirmacion = Literal["reglas", "llm"]

ETIQUETA_RIESGO = "a revisar por la clínica"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Afirmacion(_Model):
    """Afirmación sobre la marca extraída de una respuesta de un motor.

    `texto` es el fragmento literal de la respuesta. `fuentes_citadas` son los dominios que citó el
    motor en esa respuesta.
    """

    id: str
    texto: str = Field(min_length=1)
    tipo: TipoAfirmacion
    brand_id: str
    evaluation_id: str
    run_id: str
    motor: Motor | None = None
    fuentes_citadas: list[str] = []
    origen: OrigenAfirmacion = "reglas"


class Verificacion(_Model):
    """Resultado de contrastar una afirmación con el brief.

    `dato_brief`: el dato del brief contra el que se comparó (None si no hay con qué comparar).
    `expresiones_riesgo`: expresiones de la lista de revisión encontradas en la afirmación.
    """

    afirmacion_id: str
    estado: EstadoVerificacion
    motivo: str
    dato_brief: str | None = None
    expresiones_riesgo: list[str] = []

    @model_validator(mode="after")
    def _riesgo_con_expresiones(self) -> Self:
        if self.estado == "riesgo_regulatorio" and not self.expresiones_riesgo:
            raise ValueError("riesgo_regulatorio exige al menos una expresión de la lista")
        return self


class HallazgoExactitud(_Model):
    """Resumen de exactitud de una marca en un estudio. Con 0 afirmaciones, todo a 0 y sin ids."""

    id: str
    study_id: str
    brand_id: str
    afirmaciones: list[Afirmacion]
    verificaciones: list[Verificacion]
    n_correctas: int = Field(ge=0)
    n_incorrectas: int = Field(ge=0)
    n_no_verificables: int = Field(ge=0)
    n_riesgo_regulatorio: int = Field(ge=0)
    evaluation_ids: list[str]

    @model_validator(mode="after")
    def _cuadra(self) -> Self:
        ids = {a.id for a in self.afirmaciones}
        if {v.afirmacion_id for v in self.verificaciones} - ids:
            raise ValueError("hay verificaciones de afirmaciones que no están en el hallazgo")
        total = (
            self.n_correctas
            + self.n_incorrectas
            + self.n_no_verificables
            + self.n_riesgo_regulatorio
        )
        if total != len(self.verificaciones):
            raise ValueError("los recuentos no cuadran con las verificaciones")
        if self.afirmaciones and not self.evaluation_ids:
            raise ValueError("con afirmaciones, el hallazgo necesita evaluation_ids")
        return self

    @property
    def n_inexactitudes(self) -> int:
        return self.n_incorrectas


class AccionMitigacion(_Model):
    """Acción para corregir una afirmación incorrecta en su origen.

    `fuente_dominio`: la fuente que citó el motor en esa respuesta (None si no citó ninguna).
    """

    id: str
    afirmacion_ids: list[str] = Field(min_length=1)
    fuente_dominio: str | None = None
    palanca: Palanca
    descripcion: str
    evaluation_ids: list[str] = Field(min_length=1)

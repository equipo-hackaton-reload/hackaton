"""Modelos de rigor estadístico: intervalos de confianza y significancia de diferencias.

Viven fuera de `schemas.py` para no tocar el contrato compartido. Las cifras las calcula código
determinista de `domain/` (Wilson, bootstrap con semilla fija); estos modelos solo las transportan.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MetodoIntervalo = Literal["wilson", "bootstrap", "diferencia_proporciones"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Intervalo(_Model):
    """Estimación puntual con su intervalo de confianza: inf ≤ valor ≤ sup.

    `n` es el tamaño de la muestra sobre la que se calcula (evaluaciones o ejecuciones) y `nivel`
    el nivel de confianza (0,95 = 95 %). `metodo` dice cómo se obtuvo el intervalo.
    """

    valor: float
    inf: float
    sup: float
    n: int = Field(ge=0)
    nivel: float = Field(default=0.95, gt=0, lt=1)
    metodo: MetodoIntervalo

    @model_validator(mode="after")
    def _ordenado(self) -> Self:
        if not self.inf <= self.valor <= self.sup:
            raise ValueError("se espera inf <= valor <= sup")
        return self

    @property
    def margen(self) -> float:
        """Semiamplitud mayor del intervalo (para leerlo como «valor ± margen»)."""
        return max(self.valor - self.inf, self.sup - self.valor)


class Significancia(_Model):
    """Si una diferencia (entre mediciones, o entre marca y referencia) se distingue del ruido.

    `intervalo` es el del propio delta. `significativa` es True solo si el intervalo no contiene 0
    (equivalente a p < 1 − nivel cuando hay p-valor).
    """

    delta: float
    intervalo: Intervalo
    p_valor: float | None = Field(default=None, ge=0, le=1)
    significativa: bool

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if self.intervalo.valor != self.delta:
            raise ValueError("el intervalo debe estar centrado en el delta")
        contiene_cero = self.intervalo.inf <= 0 <= self.intervalo.sup
        if self.significativa == contiene_cero:
            raise ValueError("significativa debe ser True si y solo si el intervalo excluye 0")
        return self

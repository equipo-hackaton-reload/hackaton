"""Modelos de rigor estadístico: intervalos de confianza y significancia de diferencias.

Viven fuera de `schemas.py` para no tocar el contrato compartido. Las cifras las calcula código
determinista de `domain/` (Wilson, bootstrap con semilla fija); estos modelos solo las transportan.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from posiq.domain.schemas import Dimension, Evaluation, TipoVisibilidad

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


class IntervaloSegmento(_Model):
    """Intervalo de Wilson de la tasa de aparición de una marca en un segmento de las métricas.

    Los segmentos son los de `Metrics.visibilidad` (tipo × dimensión × valor). `intervalo` es None
    si el segmento no tiene observaciones (n = 0, «sin datos»), nunca un intervalo inventado.
    """

    brand_id: str
    tipo: TipoVisibilidad
    dimension: Dimension
    valor: str
    intervalo: Intervalo | None


class SignificanciaHallazgo(_Model):
    """Si la diferencia que describe un hallazgo se distingue del ruido de muestreo.

    `contraste` dice en una frase qué se compara. Si el tipo de hallazgo no admite un contraste,
    `significancia` es None y `sin_contraste` explica por qué (nunca se inventa un test).
    """

    finding_id: str
    contraste: str
    significancia: Significancia | None = None
    sin_contraste: str | None = None

    @model_validator(mode="after")
    def _uno_u_otro(self) -> Self:
        if (self.significancia is None) == (self.sin_contraste is None):
            raise ValueError("se espera significancia o el motivo de sin_contraste, no ambos")
        return self

    @property
    def significativo(self) -> bool | None:
        """True/False según el contraste; None si el hallazgo no admite contraste."""
        return self.significancia.significativa if self.significancia else None


class SignificanciaSegmento(_Model):
    """Significancia del cambio de la tasa de un segmento entre dos mediciones.

    Mismos segmentos que `VisibilityDelta`. None si falta un lado (n = 0 en alguna medición).
    """

    tipo: TipoVisibilidad
    dimension: Dimension
    valor: str
    significancia: Significancia | None


class SignificanciaRemedicion(_Model):
    """Significancia de cada delta de una re-medición (complementa a `MetricsDelta`)."""

    study_id: str
    comparado_con: str
    marca_foco_id: str
    score: Significancia | None
    tasas: list[SignificanciaSegmento]


class ConsensoJuez(_Model):
    """Voto por mayoría de N evaluaciones de la misma marca en la misma respuesta.

    `acuerdo` es la menor fracción de votos del valor ganador entre los campos que entran en el
    score; es también la `confianza` de `evaluacion`. `empates` lista los campos que se
    resolvieron con la regla de desempate (ver `domain/consensus.py`).
    """

    evaluacion: Evaluation
    n: int = Field(ge=1)
    acuerdo: float = Field(ge=0, le=1)
    acuerdo_por_campo: dict[str, float]
    empates: list[str] = []


class InformeRigor(_Model):
    """Resumen de rigor de un estudio: IC del score, aparición por segmento y hallazgos."""

    study_id: str
    marca_foco_id: str
    score: Intervalo | None
    aparicion: list[IntervaloSegmento]
    hallazgos: list[SignificanciaHallazgo]
    replicas_bootstrap: int = Field(ge=1)
    semilla_bootstrap: int

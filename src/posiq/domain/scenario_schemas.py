"""Modelos de escenarios del plan: qué acciones se mantienen o aplazan y con qué efecto simulado.

Viven fuera de `schemas.py` para no tocar el contrato compartido. Se llama `EscenarioPlan` (no
`Escenario`) para no chocar con `simulation_schemas.Escenario`, el rango mínimo/esperado/máximo.

El sistema nunca inventa costes: el presupuesto solo se aplica con `costes_declarados` por el
consultor. `capacidad` se mide en puntos de esfuerzo (S = 1, M = 2, L = 3).
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from posiq.domain.schemas import Palanca
from posiq.domain.simulation_schemas import SimulationResult
from posiq.domain.stats_schemas import Intervalo

NombreEscenario = Literal["minimo_viable", "equilibrado", "completo", "personalizado"]
MotivoAplazamiento = Literal[
    "desactivada",
    "dependencia",
    "fuera_de_presupuesto",
    "fuera_de_prioridad",
    "capacidad",
]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EntradaEscenario(_Model):
    """Lo que decide el consultor. Todo opcional salvo qué acciones quiere activas.

    - `acciones_activas`: ids de acciones; None = todas las del plan.
    - `presupuesto_eur`: tope; solo se aplica a acciones con coste en `costes_declarados`.
    - `costes_declarados`: coste en euros por id de acción, declarado por el consultor.
    - `capacidad`: tope de puntos de esfuerzo (S = 1, M = 2, L = 3).
    - `prioridad`: palancas prioritarias; None = todas. Las demás se aplazan.
    """

    acciones_activas: list[str] | None = None
    presupuesto_eur: float | None = Field(default=None, ge=0)
    costes_declarados: dict[str, float] = {}
    capacidad: int | None = Field(default=None, ge=0)
    prioridad: list[Palanca] | None = None

    @model_validator(mode="after")
    def _costes_no_negativos(self) -> Self:
        if any(c < 0 for c in self.costes_declarados.values()):
            raise ValueError("los costes declarados no pueden ser negativos")
        return self


class AccionAplazada(_Model):
    """Acción que queda fuera del escenario y por qué. `detalle` lo explica en una frase."""

    action_id: str
    motivo: MotivoAplazamiento
    detalle: str


class EscenarioPlan(_Model):
    """Resultado de aplicar una entrada (o un preajuste) a un plan.

    `hallazgos_sin_cubrir`: ids de hallazgos a los que no apunta ninguna acción mantenida.
    `coste_declarado_eur`: suma de costes declarados de las mantenidas (None si no hay ninguno).
    `simulacion` e `intervalo` se recalculan con las acciones mantenidas.
    """

    nombre: NombreEscenario
    entrada: EntradaEscenario
    mantenidas: list[str]
    aplazadas: list[AccionAplazada]
    hallazgos_sin_cubrir: list[str]
    esfuerzo_total: int = Field(ge=0)
    coste_declarado_eur: float | None = Field(default=None, ge=0)
    simulacion: SimulationResult | None = None
    intervalo: Intervalo | None = None

    @model_validator(mode="after")
    def _disjuntas(self) -> Self:
        aplazadas = {a.action_id for a in self.aplazadas}
        if len(aplazadas) != len(self.aplazadas):
            raise ValueError("una acción aplazada aparece dos veces")
        if aplazadas & set(self.mantenidas):
            raise ValueError("una acción no puede estar mantenida y aplazada a la vez")
        return self

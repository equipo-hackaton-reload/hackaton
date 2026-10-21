"""Contenedores del diferencial en el estado del grafo y en la vista del estudio (zona C).

Los modelos con cifras (`Intervalo`, `Significancia`, `EscenarioPlan`, …) son del dominio y los
calcula `domain/`; aquí solo se agrupan para que viajen juntos por el grafo y la API.
"""

from pydantic import BaseModel, ConfigDict

from posiq.domain.scenario_schemas import EscenarioPlan
from posiq.domain.schemas import Motor
from posiq.domain.stats_schemas import Intervalo, Significancia


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Rigor(_Model):
    """Incertidumbre de las cifras del estudio.

    - `score_global`, `score_por_motor`, `aparicion_por_motor`: intervalos de la marca foco.
    - `hallazgos`: significancia por id de hallazgo.
    - `deltas`: significancia de cada diferencia con la medición anterior (re-medición); la clave
      `score_global` es la del score y el resto, `tipo:dimension:valor` del segmento.
    """

    score_global: Intervalo | None = None
    score_por_motor: dict[Motor, Intervalo] = {}
    aparicion_por_motor: dict[Motor, Intervalo] = {}
    hallazgos: dict[str, Significancia] = {}
    deltas: dict[str, Significancia] = {}


class EscenarioGuardado(_Model):
    """Escenario guardado del estudio. Solo uno puede estar `elegido`: es el que usa `write`."""

    id: str
    elegido: bool = False
    escenario: EscenarioPlan

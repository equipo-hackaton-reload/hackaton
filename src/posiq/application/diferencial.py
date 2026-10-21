"""Contenedores del diferencial en el estado del grafo y en la vista del estudio (zona C).

Los modelos con cifras (`Intervalo`, `Significancia`, `EscenarioPlan`, …) son del dominio y los
calcula `domain/`; aquí solo se agrupan para que viajen juntos por el grafo y la API.
"""

from typing import TypedDict

from pydantic import BaseModel, ConfigDict

from posiq.domain.scenario_schemas import EscenarioPlan
from posiq.domain.schemas import Evaluation, Metrics, Motor, PromptInstance, Run
from posiq.domain.stats_schemas import Intervalo, Significancia, SignificanciaHallazgo


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Rigor(_Model):
    """Incertidumbre de las cifras del estudio.

    - `score_global`, `score_por_motor`, `aparicion_por_motor`: intervalos de la marca foco.
    - `hallazgos`: significancia por id de hallazgo. Un hallazgo sin contraste posible
      (`F-fuente-lider`, `F-menciones-negativas`) lleva `significancia=None` y el motivo en
      `sin_contraste`: su ausencia de significancia no se lee como «no significativo».
    - `deltas`: significancia de cada diferencia con la medición anterior (re-medición); la clave
      `score_global` es la del score y el resto, `tipo:dimension:valor` del segmento.
    - `replicas_bootstrap` y `semilla_bootstrap`: con qué se calcularon los intervalos bootstrap.
    """

    score_global: Intervalo | None = None
    score_por_motor: dict[Motor, Intervalo] = {}
    aparicion_por_motor: dict[Motor, Intervalo] = {}
    hallazgos: dict[str, SignificanciaHallazgo] = {}
    deltas: dict[str, Significancia] = {}
    replicas_bootstrap: int | None = None
    semilla_bootstrap: int | None = None


class EscenarioGuardado(_Model):
    """Escenario guardado del estudio. Solo uno puede estar `elegido`: es el que usa `write`."""

    id: str
    elegido: bool = False
    escenario: EscenarioPlan


class MedicionAnterior(TypedDict):
    """La medición que re-mide un estudio: lo que hace falta para la significancia de los deltas.

    `prepare_remeasure` la siembra con los datos del estudio original; el nodo `diferencial` la usa
    solo si las métricas nuevas se comparan con ese mismo estudio (`Metrics.comparado_con`).

    Es un `TypedDict` y no un modelo: el checkpointer reconstruye los modelos de un dict, pero no
    los anidados dentro de otro modelo (volverían como dict).
    """

    study_id: str
    metrics: Metrics
    prompts: list[PromptInstance]
    runs: list[Run]
    evaluations: list[Evaluation]

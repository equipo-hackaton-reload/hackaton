"""Presupuesto de llamadas externas de un estudio, a partir de sus `Trace`."""

import threading

from posiq.domain.schemas import Trace
from posiq.settings import Settings, usd_per_m_to_eur

# Órdenes de magnitud de la guía de APIs del kit (05_Guia_de_APIs_y_costes.md).
JUDGE_TOKENS_IN = 1000
JUDGE_TOKENS_OUT = 150


class BudgetExceeded(RuntimeError):
    """El coste acumulado del estudio supera `BUDGET_EUR_MAX`."""


class Budget:
    """Acumula el `coste_eur` de las trazas y lanza `BudgetExceeded` al superar el máximo.

    La traza que cruza el límite se registra igualmente (la llamada ya se ha hecho) y después se
    lanza la excepción para que la orquestación pare antes de la siguiente.
    """

    def __init__(self, max_eur: float, study_id: str | None = None) -> None:
        self.max_eur = max_eur
        self.study_id = study_id
        self.traces: list[Trace] = []
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: Settings, study_id: str | None = None) -> "Budget":
        return cls(settings.budget_eur_max, study_id)

    @property
    def total_eur(self) -> float:
        return sum(t.coste_eur for t in self.traces)

    @property
    def remaining_eur(self) -> float:
        return self.max_eur - self.total_eur

    def record(self, trace: Trace) -> None:
        if self.study_id is not None and trace.study_id != self.study_id:
            raise ValueError(
                f"traza del estudio {trace.study_id} en el presupuesto de {self.study_id}"
            )
        with self._lock:
            self.traces.append(trace)
            total = self.total_eur
        if total > self.max_eur:
            raise BudgetExceeded(
                f"coste acumulado {total:.4f} € supera el máximo de {self.max_eur:.2f} €"
            )

    def by_node(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for t in self.traces:
            out[t.nodo] = out.get(t.nodo, 0.0) + t.coste_eur
        return out


def estimate_judge_cost(
    n_runs: int,
    n_brands: int,
    settings: Settings | None = None,
    *,
    tokens_in: int = JUDGE_TOKENS_IN,
    tokens_out: int = JUDGE_TOKENS_OUT,
) -> float:
    """Coste estimado en EUR de juzgar `n_runs` ejecuciones × `n_brands` marcas con Jev.

    Una llamada por marca y ejecución; tokens por llamada según la guía del kit (≈1.000 de entrada
    y 150 de salida). Úsalo para enseñar la estimación antes de ejecutar.
    """
    s = settings or Settings()
    calls = n_runs * n_brands
    return calls * (
        usd_per_m_to_eur(tokens_in, s.jev_price_in_usd_per_m, s.usd_eur)
        + usd_per_m_to_eur(tokens_out, s.jev_price_out_usd_per_m, s.usd_eur)
    )

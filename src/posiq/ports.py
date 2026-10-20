"""Contratos (Protocols) entre el núcleo y los adaptadores.

Contrato compartido: cambiarlo requiere PR con etiqueta `contract-change`.
Los tipos concretos (esquemas Pydantic) viven en `posiq.domain.schemas`.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel

from posiq.domain.schemas import (
    Brand,
    Evaluation,
    Finding,
    Metrics,
    MetricsDelta,
    Plan,
    PromptInstance,
    Proposal,
    Run,
    Study,
    Trace,
)

if TYPE_CHECKING:
    from posiq.adapters.export.branding import AgencyBrandKit


class LLM(Protocol):
    """Llamada a un LLM que devuelve siempre un modelo Pydantic validado, nunca texto libre."""

    def structured[T: BaseModel](
        self, schema: type[T], prompt_name: str, state: dict[str, Any], *, study_id: str
    ) -> tuple[T, Trace]:
        """Ejecuta el prompt versionado `prompts/<prompt_name>.md` sobre `state`.

        `state` es DATO: viaja serializado en el mensaje de usuario, nunca en las instrucciones.
        Devuelve la salida validada contra `schema` y la `Trace` de la llamada (modelo, versión del
        prompt, tokens, coste y duración). Si la salida no valida tras los reintentos, lanza error.
        """
        ...


class Engine(Protocol):
    """Motor de IA a medir (ChatGPT, Gemini, Perplexity, Claude o el kit): responde a un prompt."""

    name: str

    def ask(self, prompt: PromptInstance, *, repeticion: int, study_id: str) -> Run:
        """Lanza `prompt` (repetición `repeticion`) y devuelve la `Run` del estudio `study_id`."""
        ...


class Judge(Protocol):
    """Juez que evalúa una marca en una respuesta con las preguntas de `judge_questions`."""

    name: str

    def evaluate(self, run: Run, brand: Brand) -> Evaluation:
        """Evalúa `brand` en `run`; la `Evaluation` lleva el `study_id` de la ejecución."""
        ...


class StudyRepo(Protocol):
    """Persistencia de estudios, evaluaciones, hallazgos y propuestas.

    Todo se guarda y se filtra por `study_id`: los ids de `Run`, `Evaluation` y `Finding` solo son
    únicos dentro de su estudio. Los `save_*` son idempotentes (sustituyen lo que ya hubiera con la
    misma clave), porque un nodo puede repetirse al reintentar o al reanudar el grafo.
    """

    def save_study(self, study: Study) -> None:
        """Crea o actualiza el estudio (brief, marca, estado)."""
        ...

    def save_runs(self, study_id: str, runs: Sequence[Run]) -> None: ...

    def save_evaluations(self, study_id: str, evals: Sequence[Evaluation]) -> None: ...

    def save_metrics(
        self, study_id: str, metrics: Metrics, delta: MetricsDelta | None = None
    ) -> None:
        """Guarda las métricas y, si es una re-medición, su diferencia con la anterior."""
        ...

    def save_findings(self, study_id: str, findings: Sequence[Finding]) -> None:
        """Sustituye los hallazgos del estudio por `findings`."""
        ...

    def save_plan(self, study_id: str, plan: Plan) -> None: ...

    def save_proposal(self, study_id: str, proposal: Proposal) -> None: ...

    def save_traces(self, study_id: str, traces: Sequence[Trace]) -> None:
        """Sustituye las trazas del estudio por `traces` (la lista completa acumulada)."""
        ...

    def get_study(self, study_id: str) -> Study:
        """El estudio `study_id`; `KeyError` si no existe."""
        ...

    def list_studies(self, brand_id: str | None = None) -> list[Study]:
        """Estudios (de `brand_id`, si se da), del más reciente al más antiguo."""
        ...

    def latest_metrics(self, brand_id: str, before: datetime | None = None) -> Metrics | None:
        """Métricas del último estudio de `brand_id` creado antes de `before` (re-medición)."""
        ...


class Exporter(Protocol):
    """Exporta la propuesta a Word/PDF.

    No calcula cifras: solo da formato a las que ya trae la `Proposal`. Sin `marca_agencia`, la
    cabecera dice «posiq.».
    """

    def render(
        self,
        proposal: Proposal,
        *,
        formato: Literal["docx", "pdf"],
        marca_agencia: "AgencyBrandKit | None" = None,
    ) -> bytes: ...

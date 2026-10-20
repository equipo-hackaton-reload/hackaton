"""Contratos (Protocols) entre el núcleo y los adaptadores.

Contrato compartido: cambiarlo requiere PR con etiqueta `contract-change`.
Los tipos concretos (esquemas Pydantic) viven en `posiq.domain.schemas`.
"""

from typing import Any, Protocol

from pydantic import BaseModel

from posiq.domain.schemas import Brand, Evaluation, PromptInstance, Run, Trace


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
    """Persistencia de estudios, evaluaciones, hallazgos y propuestas."""


class Exporter(Protocol):
    """Exporta la propuesta a Word/PDF."""

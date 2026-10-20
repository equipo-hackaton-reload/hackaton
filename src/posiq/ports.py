"""Contratos (Protocols) entre el núcleo y los adaptadores.

Contrato compartido: se cierra el primer día. Cambiarlo requiere PR con etiqueta `contract-change`.
Los tipos concretos (esquemas Pydantic) viven en `posiq.domain.schemas`; aquí solo hay stubs.
"""

from typing import Protocol


class LLM(Protocol):
    """Llamada a un LLM que devuelve siempre un modelo Pydantic validado, nunca texto libre.

    Firma prevista: `structured(schema, prompt_name, state) -> schema`. Registra una `Trace`.
    """


class Engine(Protocol):
    """Motor de IA a medir (ChatGPT, Gemini, Perplexity, Claude o el kit): responde a un prompt."""


class Judge(Protocol):
    """Juez que evalúa una respuesta con las preguntas de `domain/judge_questions.py`."""


class StudyRepo(Protocol):
    """Persistencia de estudios, evaluaciones, hallazgos y propuestas."""


class Exporter(Protocol):
    """Exporta la propuesta a Word/PDF."""

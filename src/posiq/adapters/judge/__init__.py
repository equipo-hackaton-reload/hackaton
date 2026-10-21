"""Jueces: Jev (TypeSafe) con fallback LLM, o solo el LLM si no hay clave de TypeSafe."""

from collections.abc import Sequence

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.judge.base import SystemOneJudge
from posiq.adapters.judge.consensus import ConsensusJudge
from posiq.adapters.judge.jev import JevJudge
from posiq.adapters.judge.llm_fallback import LLMJudge
from posiq.domain.schemas import Brand
from posiq.settings import Settings


def build_judge(
    settings: Settings,
    market: Sequence[Brand] = (),
    *,
    budget: Budget | None = None,
    cache: DiskCache | None = None,
) -> SystemOneJudge:
    """`JevJudge` con `LLMJudge` de fallback si hay `TYPESAFE_API_KEY`; si no, solo `LLMJudge`.

    `market` son las marcas del estudio: la posición se calcula entre las marcas presentes. Sin
    `market`, cada marca se detecta sola (posición 1 si aparece); pásalo siempre en un estudio.
    Construir el juez no exige claves: si falta alguna, `MissingCredentialError` al evaluar.
    """
    fallback = LLMJudge(settings, market, budget=budget, cache=cache)
    if settings.typesafe_api_key.get_secret_value():
        return JevJudge(settings, market, fallback=fallback, budget=budget, cache=cache)
    return fallback


__all__ = ["ConsensusJudge", "JevJudge", "LLMJudge", "SystemOneJudge", "build_judge"]

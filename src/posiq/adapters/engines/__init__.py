"""Motores de IA: los cuatro del kit (simulados) o las APIs reales con búsqueda web (ADR 0006)."""

import logging
from collections.abc import Sequence

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.engines.anthropic import AnthropicEngine
from posiq.adapters.engines.base import RealEngine
from posiq.adapters.engines.gemini import GeminiEngine
from posiq.adapters.engines.kit import KitEngine
from posiq.adapters.engines.openai import OpenAIEngine
from posiq.adapters.engines.perplexity import PerplexityEngine
from posiq.domain.schemas import ModoEstudio
from posiq.ports import Engine
from posiq.settings import Settings

logger = logging.getLogger(__name__)

REAL_ENGINES: tuple[type[RealEngine], ...] = (
    OpenAIEngine,
    GeminiEngine,
    PerplexityEngine,
    AnthropicEngine,
)


def build_engines(
    settings: Settings,
    modo: ModoEstudio,
    marcas_a_evaluar: Sequence[str] = (),
    *,
    cache: DiskCache | None = None,
    budget: Budget | None = None,
) -> list[Engine]:
    """Motores del estudio.

    - `kit`: los cuatro `KitEngine` (ChatGPT, Gemini, Perplexity, Claude) sobre `ejecuciones.csv`.
    - `real`: los motores reales cuya clave esté en settings, en ese mismo orden; avisa en el log
      de los que faltan. `marcas_a_evaluar` (ids del mercado) es obligatorio en este modo.
    """
    if modo == "kit":
        return list(KitEngine.from_settings(settings))
    engines = [cls(settings, marcas_a_evaluar, cache=cache, budget=budget) for cls in REAL_ENGINES]
    faltan = [e for e in engines if not e.has_key]
    for e in faltan:
        logger.warning("motor %s desactivado: falta %s en .env", e.motor, e.key_variable)
    if len(faltan) == len(engines):
        logger.warning("modo real sin ninguna clave de motor: no hay motores que lanzar")
    return [e for e in engines if e.has_key]


__all__ = [
    "AnthropicEngine",
    "GeminiEngine",
    "KitEngine",
    "OpenAIEngine",
    "PerplexityEngine",
    "RealEngine",
    "build_engines",
]

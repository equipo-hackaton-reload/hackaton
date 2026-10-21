"""Estimación previa del coste de un estudio (`GET /estimate`), con los precios de `Settings`.

Es un orden de magnitud para decidir antes de ejecutar: los tokens por llamada salen de la guía de
APIs del kit (`05_Guia_de_APIs_y_costes.md`) y se cuenta una búsqueda web por llamada. El coste real
del estudio es la suma de sus `Trace`. Las llamadas de intake, mercado, plan y redacción son unas
pocas por estudio y no se incluyen.
"""

from typing import Literal

from pydantic import BaseModel

from posiq.adapters.budget import JUDGE_TOKENS_IN, JUDGE_TOKENS_OUT, estimate_judge_cost
from posiq.adapters.engines.base import EngineReply, Pricing
from posiq.domain.schemas import ModoEstudio
from posiq.settings import Settings, usd_per_m_to_eur

# Volumen del estudio del kit: 52 prompts instanciados × 4 motores × 3 repeticiones.
KIT_PROMPTS = 52
KIT_MOTORES = 4
KIT_REPETICIONES = 3
KIT_LLAMADAS = KIT_PROMPTS * KIT_MOTORES * KIT_REPETICIONES
# Cota superior: los prompts genéricos y de ciudad evalúan las 10 marcas del sector.
MARCAS_POR_EJECUCION = 10
# Guía del kit: prompt de 100-200 tokens y respuesta de 500-900; se toma el punto medio.
ENGINE_TOKENS_IN = 150
ENGINE_TOKENS_OUT = 700
BUSQUEDAS_POR_LLAMADA = 1

Juez = Literal["jev", "fallback", "reglas"]


class CostEstimate(BaseModel):
    llamadas: int
    coste_estimado_eur: float
    coste_motores_eur: float
    coste_juez_eur: float
    juez: Juez
    presupuesto_max_eur: float


def engine_call_eur(settings: Settings) -> float:
    """Coste medio en EUR de una llamada a los cuatro motores reales."""
    s = settings
    pricings = [
        Pricing(s.pricing_chatgpt_in, s.pricing_chatgpt_out, s.pricing_chatgpt_search),
        Pricing(s.pricing_gemini_in, s.pricing_gemini_out, s.pricing_gemini_search),
        Pricing(s.pricing_perplexity_in, s.pricing_perplexity_out, s.pricing_perplexity_search),
        Pricing(s.pricing_claude_in, s.pricing_claude_out, s.pricing_claude_search),
    ]
    reply = EngineReply(
        texto="",
        urls=[],
        modelo="",
        tokens_in=ENGINE_TOKENS_IN,
        tokens_out=ENGINE_TOKENS_OUT,
        busquedas=BUSQUEDAS_POR_LLAMADA,
    )
    return sum(p.eur(reply, s.usd_eur) for p in pricings) / len(pricings)


def judge_of(settings: Settings) -> Juez:
    """Juez que usará el estudio: reglas si se fuerza (`JUDGE_PROVIDER=reglas`); si no, según las
    claves, Jev, el fallback de DeepSeek o solo reglas."""
    if settings.judge_provider == "reglas":
        return "reglas"
    if settings.typesafe_api_key.get_secret_value():
        return "jev"
    if settings.deepseek_api_key.get_secret_value():
        return "fallback"
    return "reglas"


def judge_eur(juez: Juez, n_runs: int, settings: Settings) -> float:
    if juez == "jev":
        return estimate_judge_cost(n_runs, MARCAS_POR_EJECUCION, settings)
    if juez == "fallback":
        per_call = usd_per_m_to_eur(
            JUDGE_TOKENS_IN, settings.deepseek_price_in_usd_per_m, settings.usd_eur
        ) + usd_per_m_to_eur(
            JUDGE_TOKENS_OUT, settings.deepseek_price_out_usd_per_m, settings.usd_eur
        )
        return n_runs * MARCAS_POR_EJECUCION * per_call
    return 0.0


def estimate_study(
    modo: ModoEstudio,
    settings: Settings,
    *,
    n_prompts: int = KIT_PROMPTS,
    n_motores: int = KIT_MOTORES,
    repeticiones: int = KIT_REPETICIONES,
) -> CostEstimate:
    """En modo kit los motores no cuestan; el juez cuesta si hay claves (sin ellas, reglas)."""
    if min(n_prompts, n_motores, repeticiones) < 1:
        raise ValueError("n_prompts, n_motores y repeticiones deben ser al menos 1")
    llamadas = n_prompts * n_motores * repeticiones
    motores = 0.0 if modo == "kit" else llamadas * engine_call_eur(settings)
    juez = judge_of(settings)
    coste_juez = judge_eur(juez, llamadas, settings)
    return CostEstimate(
        llamadas=llamadas,
        coste_estimado_eur=round(motores + coste_juez, 4),
        coste_motores_eur=round(motores, 4),
        coste_juez_eur=round(coste_juez, 4),
        juez=juez,
        presupuesto_max_eur=settings.budget_eur_max,
    )

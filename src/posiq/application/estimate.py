"""Estimación previa del coste de un estudio (`GET /estimate`), con los precios de `Settings`.

Es un orden de magnitud para decidir antes de ejecutar (ADR 0018); el coste real del estudio es la
suma de sus `Trace`. Cuenta todo lo que se paga:

- Motores: tokens de la guía de APIs del kit (`05_Guia_de_APIs_y_costes.md`) y una búsqueda web por
  llamada. En modo kit no cuestan (respuestas del CSV).
- LLM de los nodos (`LLM_TOKENS`): intake, market, prompts (solo modo real: el kit trae su banco),
  plan y redacción, con tokens típicos estimados sobre el brief de Alborada (52 prompts, 10 marcas,
  7 hallazgos, 9 acciones). Plan y redacción se cuentan dos veces porque reintentan una vez si el
  resultado incumple el brief o deja puntos sin tratar: es una cota, no la media.
- Juez: una llamada por marca y ejecución; con Jev, además, `FRACCION_FALLBACK` de esas llamadas
  repetidas en el fallback de DeepSeek (confianza baja o discrepancia con las reglas, ADR 0014).
- PlanGuard: una llamada por acción del plan (`ACCIONES_PLAN`), con el mismo juez y su fallback.

En modo kit todo es 0 salvo el opt-in `KIT_IA_REAL=true`: sin él, el kit usa `FixtureLLM` y
`FixtureJudge` y no hace ninguna llamada de pago.
"""

from typing import Literal

from pydantic import BaseModel

from posiq.adapters.budget import JUDGE_TOKENS_IN, JUDGE_TOKENS_OUT
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

# Tokens típicos (entrada, salida) y llamadas por estudio de cada nodo con LLM (ver módulo).
LLM_TOKENS: dict[str, tuple[int, int, int]] = {
    "intake": (1_500, 600, 1),
    "market": (2_500, 800, 1),
    "prompts": (2_500, 6_000, 1),
    "plan": (6_000, 2_500, 2),
    "write": (12_000, 4_000, 2),
}
NODOS_SOLO_REAL = frozenset({"prompts"})
NODOS_PRIMERA_MEDICION = frozenset({"intake", "market"})
# Parte de las llamadas de Jev que se repiten en el fallback (cota prudente; ver ADR 0014).
FRACCION_FALLBACK = 0.25
# Acciones de un plan típico (el de Alborada tiene 9): una llamada de PlanGuard por acción.
ACCIONES_PLAN = 10

Juez = Literal["jev", "fallback", "reglas", "kit"]


class CostEstimate(BaseModel):
    """`coste_estimado_eur` = motores + LLM de los nodos + juez (con fallback) + PlanGuard."""

    llamadas: int
    coste_estimado_eur: float
    coste_motores_eur: float
    coste_juez_eur: float
    coste_llm_eur: float = 0.0
    coste_plan_guard_eur: float = 0.0
    llamadas_llm: int = 0
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


def ia_de_pago(modo: ModoEstudio, settings: Settings) -> bool:
    """¿Usa el estudio el LLM y el juez de pago? Siempre en real; en kit, solo con
    `KIT_IA_REAL=true` (ADR 0018)."""
    return modo == "real" or settings.kit_ia_real


def judge_of(settings: Settings, modo: ModoEstudio = "real") -> Juez:
    """Juez que usará el estudio: reglas si se fuerza (`JUDGE_PROVIDER=reglas`); en kit sin
    opt-in, las etiquetas del kit (`FixtureJudge`); si no, según las claves, Jev, el fallback de
    DeepSeek o solo reglas."""
    if settings.judge_provider == "reglas":
        return "reglas"
    if not ia_de_pago(modo, settings):
        return "kit"
    if settings.typesafe_api_key.get_secret_value():
        return "jev"
    if settings.deepseek_api_key.get_secret_value():
        return "fallback"
    return "reglas"


def _judge_tokens_eur(price_in: float, price_out: float, usd_eur: float) -> float:
    return usd_per_m_to_eur(JUDGE_TOKENS_IN, price_in, usd_eur) + usd_per_m_to_eur(
        JUDGE_TOKENS_OUT, price_out, usd_eur
    )


def judge_call_eur(juez: Juez, settings: Settings) -> float:
    """Coste esperado de una pregunta al juez, con la parte que se repite en el fallback."""
    s = settings
    deepseek = _judge_tokens_eur(
        s.deepseek_price_in_usd_per_m, s.deepseek_price_out_usd_per_m, s.usd_eur
    )
    if juez == "jev":
        jev = _judge_tokens_eur(s.jev_price_in_usd_per_m, s.jev_price_out_usd_per_m, s.usd_eur)
        return jev + FRACCION_FALLBACK * deepseek
    if juez == "fallback":
        return deepseek
    return 0.0


def judge_eur(juez: Juez, n_runs: int, settings: Settings) -> float:
    """Juez de menciones: una llamada por marca y ejecución (cota: las 10 marcas)."""
    return n_runs * MARCAS_POR_EJECUCION * judge_call_eur(juez, settings)


def plan_guard_eur(juez: Juez, settings: Settings) -> float:
    """PlanGuard usa el juez de menciones (Jev con fallback, o DeepSeek); con reglas, nada."""
    return ACCIONES_PLAN * judge_call_eur(juez, settings)


def llm_eur(
    modo: ModoEstudio, settings: Settings, *, remedicion: bool = False
) -> tuple[float, int]:
    """Coste y llamadas del LLM de los nodos. Una re-medición no repite intake ni market (hereda
    el brief y el mercado confirmado); `LLM_PROVIDER=fixture` no cuesta."""
    if not ia_de_pago(modo, settings) or settings.llm_provider == "fixture":
        return 0.0, 0
    coste, llamadas = 0.0, 0
    for nodo, (tokens_in, tokens_out, n) in LLM_TOKENS.items():
        if (modo == "kit" and nodo in NODOS_SOLO_REAL) or (
            remedicion and nodo in NODOS_PRIMERA_MEDICION
        ):
            continue
        llamadas += n
        coste += n * (
            usd_per_m_to_eur(tokens_in, settings.deepseek_price_in_usd_per_m, settings.usd_eur)
            + usd_per_m_to_eur(tokens_out, settings.deepseek_price_out_usd_per_m, settings.usd_eur)
        )
    return coste, llamadas


def estimate_study(
    modo: ModoEstudio,
    settings: Settings,
    *,
    n_prompts: int = KIT_PROMPTS,
    n_motores: int = KIT_MOTORES,
    repeticiones: int = KIT_REPETICIONES,
    remedicion: bool = False,
) -> CostEstimate:
    """En modo kit todo es 0 salvo `KIT_IA_REAL=true`; en real, motores, LLM, juez y PlanGuard."""
    if min(n_prompts, n_motores, repeticiones) < 1:
        raise ValueError("n_prompts, n_motores y repeticiones deben ser al menos 1")
    llamadas = n_prompts * n_motores * repeticiones
    motores = 0.0 if modo == "kit" else llamadas * engine_call_eur(settings)
    juez = judge_of(settings, modo)
    coste_juez = judge_eur(juez, llamadas, settings)
    coste_guard = plan_guard_eur(juez, settings)
    coste_llm, llamadas_llm = llm_eur(modo, settings, remedicion=remedicion)
    return CostEstimate(
        llamadas=llamadas,
        coste_estimado_eur=round(motores + coste_juez + coste_guard + coste_llm, 4),
        coste_motores_eur=round(motores, 4),
        coste_juez_eur=round(coste_juez, 4),
        coste_llm_eur=round(coste_llm, 4),
        coste_plan_guard_eur=round(coste_guard, 4),
        llamadas_llm=llamadas_llm,
        juez=juez,
        presupuesto_max_eur=settings.budget_eur_max,
    )

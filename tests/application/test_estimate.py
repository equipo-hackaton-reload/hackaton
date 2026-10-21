"""Estimación previa del coste de un estudio (ADR 0018: cuenta todo lo que se paga)."""

import pytest
from pydantic import SecretStr

from posiq.application.estimate import (
    ACCIONES_PLAN,
    KIT_LLAMADAS,
    MARCAS_POR_EJECUCION,
    engine_call_eur,
    estimate_study,
    judge_call_eur,
    llm_eur,
)
from posiq.settings import Settings
from tests.application.fakes import kit_settings


def ajustes(**kw: object) -> Settings:
    """Settings sin `.env` y con el LLM de pago por defecto, aunque el entorno diga fixture."""
    return kit_settings(**{"llm_provider": "deepseek", **kw})


CLAVES = {
    "deepseek_api_key": SecretStr("k"),
    "typesafe_api_key": SecretStr("k"),
    "openai_api_key": SecretStr("k"),
    "anthropic_api_key": SecretStr("k"),
}


def test_kit_without_judge_keys_is_free() -> None:
    estimate = estimate_study("kit", ajustes())
    assert estimate.llamadas == KIT_LLAMADAS == 624
    assert estimate.coste_estimado_eur == 0
    assert estimate.juez == "kit"
    assert estimate.presupuesto_max_eur == 5.0


@pytest.mark.parametrize("provider", ["deepseek", "fixture"])
def test_kit_is_free_even_with_every_key(provider: str) -> None:
    estimate = estimate_study("kit", ajustes(llm_provider=provider, **CLAVES))
    assert estimate.coste_estimado_eur == 0
    assert estimate.coste_llm_eur == estimate.coste_juez_eur == estimate.coste_plan_guard_eur == 0
    assert estimate.llamadas_llm == 0
    assert estimate.juez == "kit"


def test_kit_opt_in_prices_llm_judge_and_plan_guard_but_not_engines() -> None:
    estimate = estimate_study("kit", ajustes(kit_ia_real=True, **CLAVES))
    assert estimate.juez == "jev"
    assert estimate.coste_motores_eur == 0
    assert estimate.coste_llm_eur > 0 and estimate.coste_juez_eur > 0
    assert estimate.coste_plan_guard_eur > 0
    # El kit trae su banco: no se llama a `prompts`.
    assert estimate.llamadas_llm == 1 + 1 + 2 + 2


def test_real_counts_engines_llm_judge_with_fallback_and_plan_guard() -> None:
    settings = ajustes(typesafe_api_key=SecretStr("k"), budget_eur_max=20)
    estimate = estimate_study("real", settings, n_prompts=10, n_motores=2, repeticiones=1)
    assert estimate.llamadas == 20
    assert estimate.juez == "jev"
    assert estimate.coste_motores_eur == pytest.approx(20 * engine_call_eur(settings), abs=1e-4)
    por_llamada = judge_call_eur("jev", settings)
    assert por_llamada > 0 and judge_call_eur("reglas", settings) == 0
    assert estimate.coste_juez_eur == pytest.approx(
        20 * MARCAS_POR_EJECUCION * por_llamada, abs=1e-4
    )
    assert estimate.coste_plan_guard_eur == pytest.approx(ACCIONES_PLAN * por_llamada, abs=1e-4)
    assert estimate.llamadas_llm == 1 + 1 + 1 + 2 + 2
    assert estimate.coste_estimado_eur == pytest.approx(
        estimate.coste_motores_eur
        + estimate.coste_juez_eur
        + estimate.coste_llm_eur
        + estimate.coste_plan_guard_eur,
        abs=1e-3,
    )
    assert estimate.presupuesto_max_eur == 20


def test_jev_includes_the_share_repeated_by_the_fallback() -> None:
    s = ajustes()
    assert judge_call_eur("jev", s) > judge_call_eur(
        "jev",
        s.model_copy(update={"deepseek_price_in_usd_per_m": 0, "deepseek_price_out_usd_per_m": 0}),
    )


def test_real_costs_more_than_intake_and_market() -> None:
    settings = ajustes(judge_provider="reglas")
    estimate = estimate_study("real", settings, n_prompts=1, n_motores=1, repeticiones=1)
    todo_llm, _ = llm_eur("real", settings)
    sin_intake_market, _ = llm_eur("real", settings, remedicion=True)
    intake_market = todo_llm - sin_intake_market
    assert intake_market > 0
    assert estimate.coste_estimado_eur > intake_market
    assert estimate.coste_llm_eur == pytest.approx(todo_llm, abs=1e-4)


def test_remeasure_skips_intake_and_market() -> None:
    settings = ajustes()
    primera = estimate_study("real", settings)
    otra = estimate_study("real", settings, remedicion=True)
    assert otra.llamadas_llm == primera.llamadas_llm - 2
    assert otra.coste_estimado_eur < primera.coste_estimado_eur


def test_real_with_only_deepseek_prices_the_fallback_judge() -> None:
    jev = estimate_study("real", ajustes(typesafe_api_key=SecretStr("k")))
    deepseek = estimate_study("real", ajustes(deepseek_api_key=SecretStr("k")))
    assert deepseek.juez == "fallback"
    assert deepseek.coste_juez_eur > jev.coste_juez_eur > 0


def test_judge_forced_to_rules_costs_nothing_even_with_keys() -> None:
    settings = ajustes(judge_provider="reglas", kit_ia_real=True, **CLAVES)
    estimate = estimate_study("kit", settings)
    assert estimate.juez == "reglas"
    assert estimate.coste_juez_eur == estimate.coste_plan_guard_eur == 0
    assert estimate.coste_estimado_eur == estimate.coste_llm_eur


def test_counts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        estimate_study("real", ajustes(), n_prompts=0)

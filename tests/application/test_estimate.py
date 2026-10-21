"""Estimación previa del coste de un estudio."""

import pytest
from pydantic import SecretStr

from posiq.adapters.budget import estimate_judge_cost
from posiq.application.estimate import (
    KIT_LLAMADAS,
    MARCAS_POR_EJECUCION,
    engine_call_eur,
    estimate_study,
)
from tests.application.fakes import kit_settings


def test_kit_without_judge_keys_is_free() -> None:
    estimate = estimate_study("kit", kit_settings())
    assert estimate.llamadas == KIT_LLAMADAS == 624
    assert estimate.coste_estimado_eur == 0
    assert estimate.juez == "reglas"
    assert estimate.presupuesto_max_eur == 5.0


def test_real_adds_engines_and_jev_judge() -> None:
    settings = kit_settings(typesafe_api_key=SecretStr("k"), budget_eur_max=20)
    estimate = estimate_study("real", settings, n_prompts=10, n_motores=2, repeticiones=1)
    assert estimate.llamadas == 20
    assert estimate.juez == "jev"
    assert estimate.coste_motores_eur == pytest.approx(20 * engine_call_eur(settings), abs=1e-4)
    assert estimate.coste_juez_eur == pytest.approx(
        estimate_judge_cost(20, MARCAS_POR_EJECUCION, settings), abs=1e-4
    )
    assert estimate.coste_estimado_eur == pytest.approx(
        estimate.coste_motores_eur + estimate.coste_juez_eur, abs=1e-4
    )
    assert estimate.presupuesto_max_eur == 20


def test_kit_with_only_deepseek_prices_the_fallback_judge() -> None:
    jev = estimate_study("kit", kit_settings(typesafe_api_key=SecretStr("k")))
    deepseek = estimate_study("kit", kit_settings(deepseek_api_key=SecretStr("k")))
    assert jev.coste_motores_eur == deepseek.coste_motores_eur == 0
    assert deepseek.juez == "fallback"
    assert deepseek.coste_juez_eur > jev.coste_juez_eur > 0


def test_counts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        estimate_study("real", kit_settings(), n_prompts=0)

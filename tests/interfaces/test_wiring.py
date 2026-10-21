"""Raíz de composición: qué se construye según las claves y `JUDGE_PROVIDER`."""

from pydantic import SecretStr

from posiq.adapters.cache import DiskCache
from posiq.interfaces.api.wiring import plan_guard_factory
from tests.application.fakes import kit_settings


def guard_for(**kw: object) -> object:
    settings = kit_settings(**kw)
    return plan_guard_factory(settings, DiskCache.from_settings(settings))


def test_plan_guard_needs_a_judge_key() -> None:
    assert guard_for() is None
    assert guard_for(deepseek_api_key=SecretStr("k")) is not None
    assert guard_for(typesafe_api_key=SecretStr("k")) is not None


def test_rules_judge_disables_plan_guard_even_with_keys() -> None:
    assert guard_for(judge_provider="reglas", deepseek_api_key=SecretStr("k")) is None

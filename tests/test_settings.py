"""Las claves de proveedores solo se leen del `.env` o del constructor, nunca del entorno del SO."""

from pathlib import Path

import pytest

from posiq.settings import Settings


def test_clave_del_so_se_ignora(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("LLM_PROVIDER=fixture\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-del-so")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-del-so")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-del-so")
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert s.anthropic_api_key.get_secret_value() == ""
    assert s.openai_api_key.get_secret_value() == ""
    assert s.langfuse_secret_key.get_secret_value() == ""


def test_clave_del_env_si_se_lee(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=sk-del-env\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-del-so")
    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert s.anthropic_api_key.get_secret_value() == "sk-del-env"


def test_clave_del_constructor_si_se_lee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-del-so")
    s = Settings(_env_file=None, anthropic_api_key="sk-explicita")  # type: ignore[call-arg, arg-type]
    assert s.anthropic_api_key.get_secret_value() == "sk-explicita"


def test_ajustes_no_secretos_siguen_leyendose_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fixture")
    monkeypatch.setenv("BUDGET_EUR_MAX", "1.5")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_provider == "fixture"
    assert s.budget_eur_max == 1.5

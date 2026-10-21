"""El modo kit no hace ninguna llamada de pago aunque haya claves (ADR 0018).

Con todas las claves definidas y `LLM_PROVIDER=deepseek` (el valor por defecto), un estudio del kit
completo usa `FixtureLLM`, `FixtureJudge` y ningún PlanGuard: los clientes reales están
sustituidos por dobles que fallan si se llaman, el coste es 0 y la cifra sigue siendo la canónica.
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from posiq.adapters.budget import Budget
from posiq.adapters.llm.fixture import FixtureJudge, FixtureLLM
from posiq.adapters.llm.openai_compat import OpenAICompatLLM
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.domain.schemas import Market
from posiq.interfaces.api import wiring
from posiq.interfaces.api.main import create_app
from posiq.settings import Settings
from tests.application.fakes import memory_repo
from tests.auth_helpers import authenticate

ROOT = Path(__file__).resolve().parents[2]
BRIEF = ROOT / "data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md"
FOCO = "clinica-alborada-vision"
CLAVES = {
    name: SecretStr("clave-falsa")
    for name in (
        "deepseek_api_key",
        "typesafe_api_key",
        "openai_api_key",
        "gemini_api_key",
        "perplexity_api_key",
        "anthropic_api_key",
    )
}


def con_claves(tmp_path: Path, **kw: Any) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="deepseek",
        database_url=f"sqlite:///{(tmp_path / 'study.db').as_posix()}",
        cache_enabled=False,
        auth_dev_codes=True,  # login de test con LLM_PROVIDER=deepseek (ADR 0015)
        **{**CLAVES, **kw},
    )


@pytest.fixture
def llamadas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Sustituye cada cliente de pago por un doble que apunta la llamada y falla."""
    hechas: list[str] = []

    def prohibido(nombre: str) -> Any:
        def fake(*_: Any, **__: Any) -> Any:
            hechas.append(nombre)
            raise AssertionError(f"llamada de pago en modo kit: {nombre}")

        return fake

    monkeypatch.setattr(OpenAICompatLLM, "structured", prohibido("deepseek"))
    monkeypatch.setattr("posiq.adapters.llm.openai_compat.OpenAI", prohibido("openai-sdk"))
    monkeypatch.setattr("posiq.adapters.judge.jev.JevJudge._call", prohibido("jev"))
    monkeypatch.setattr("posiq.adapters.judge.llm_fallback.LLMJudge._call", prohibido("fallback"))
    monkeypatch.setattr(wiring, "build_judge", prohibido("build_judge"))
    monkeypatch.setattr(wiring, "build_plan_guard", prohibido("plan_guard"))
    return hechas


def test_kit_con_claves_no_llama_a_nada_y_da_la_cifra_canonica(
    tmp_path: Path, llamadas: list[str]
) -> None:
    with TestClient(create_app(settings=con_claves(tmp_path))) as client:
        authenticate(client)
        estimate = client.get("/estimate", params={"modo": "kit"}).json()
        assert estimate["coste_estimado_eur"] == 0 and estimate["juez"] == "kit"

        brief = BRIEF.read_text(encoding="utf-8")
        response = client.post("/studies", json={"brief_texto": brief, "modo": "kit"})
        assert response.status_code == 201, response.text
        sid = response.json()["study_id"]
        for revision in ("competidores", "plan"):
            response = client.post(
                f"/studies/{sid}/resume", json={"revision": revision, "payload": {"aprobado": True}}
            )
            assert response.status_code == 202, response.text
        view = client.get(f"/studies/{sid}").json()
        traces = client.get(f"/studies/{sid}/traces").json()

    assert llamadas == []
    assert view["estado"] == "completado", view["errores"]
    assert view["coste_acumulado_eur"] == 0
    assert traces and all(t["coste_eur"] == 0 for t in traces)
    assert view["calidad_plan"] is None
    assert view["metrics"]["score_global"]["brand_id"] == FOCO
    assert view["metrics"]["score_global"]["score"] == 25.93


def deps(tmp_path: Path, **kw: Any) -> Any:
    repo: SqlStudyRepo = memory_repo()
    return wiring.build_deps(con_claves(tmp_path, **kw), repo)


def test_kit_wiring_ignores_the_keys(tmp_path: Path, llamadas: list[str]) -> None:
    kit = deps(tmp_path)["kit"]
    assert isinstance(kit.llm, FixtureLLM)
    assert kit.plan_guard_factory is None
    juez = kit.judge_factory(Market(marcas=[]), Budget(1.0))
    assert isinstance(juez, FixtureJudge) and juez.labels  # etiquetas del kit: cifra canónica
    assert llamadas == []


def test_real_mode_keeps_the_paid_adapters(tmp_path: Path) -> None:
    real = deps(tmp_path)["real"]
    assert isinstance(real.llm, OpenAICompatLLM)
    assert real.plan_guard_factory is not None


def test_kit_opt_in_uses_the_paid_adapters(tmp_path: Path) -> None:
    kit = deps(tmp_path, kit_ia_real=True)["kit"]
    assert isinstance(kit.llm, OpenAICompatLLM)
    assert kit.plan_guard_factory is not None

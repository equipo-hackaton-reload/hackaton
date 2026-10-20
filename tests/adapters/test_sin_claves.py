"""Sin claves, los adaptadores se construyen y solo fallan al llamar, nombrando la variable."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from posiq.adapters.errors import MissingCredentialError
from posiq.adapters.judge import JevJudge, LLMJudge, build_judge
from posiq.adapters.llm.openai_compat import OpenAICompatLLM
from posiq.settings import Settings
from tests.domain.factories import brand, run


@pytest.fixture
def sin_claves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    for var in ("TYPESAFE_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    return Settings(_env_file=None, cache_enabled=False)  # type: ignore[call-arg]


def test_build_judge_sin_claves_construye_y_falla_al_evaluar(sin_claves: Settings) -> None:
    judge = build_judge(sin_claves)
    assert isinstance(judge, LLMJudge)
    with pytest.raises(MissingCredentialError, match="DEEPSEEK_API_KEY") as exc:
        judge.evaluate(run(texto="Alborada"), brand())
    assert exc.value.variable == "DEEPSEEK_API_KEY"


def test_jev_sin_clave_nombra_typesafe(sin_claves: Settings) -> None:
    judge = JevJudge(sin_claves, [brand()])
    with pytest.raises(MissingCredentialError, match="TYPESAFE_API_KEY"):
        judge.evaluate(run(texto="Alborada"), brand())


def test_llm_sin_clave_construye_y_falla_al_llamar(sin_claves: Settings, tmp_path: Path) -> None:
    (tmp_path / "intake.v1.md").write_text("Prompt", encoding="utf-8")

    class Out(BaseModel):
        x: int

    llm = OpenAICompatLLM(sin_claves, prompts_dir=tmp_path)
    with pytest.raises(MissingCredentialError, match="DEEPSEEK_API_KEY"):
        llm.structured(Out, "intake.v1", {}, study_id="S-1")

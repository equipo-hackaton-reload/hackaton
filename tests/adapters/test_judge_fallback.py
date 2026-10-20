import asyncio
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from posiq.adapters.judge import JevJudge, LLMJudge, build_judge
from posiq.adapters.judge.llm_fallback import _AdapterSession
from posiq.domain.judge_questions import JUDGE_QUESTIONS, build_state
from posiq.settings import Settings
from tests.adapters.judge_fakes import FakeSystemOneClient, sdk_answers
from tests.domain.factories import brand, run

ALBORADA = brand(aliases=["Alborada"])
RUN = run(texto="No dispongo de información sobre Alborada.")


def test_mismas_preguntas_y_origen_fallback(settings: Settings) -> None:
    fake = FakeSystemOneClient(
        sdk_answers(mention="pasiva", level=1, sentiment="neutro", supported=0.05),
        usage=SimpleNamespace(input_tokens_total=1200, output_tokens_total=300),
    )
    judge = LLMJudge(settings, [ALBORADA], client_factory=lambda: fake)
    e = judge.evaluate(RUN, ALBORADA)
    assert (e.origen, e.tipo_mencion, e.fuerza, e.tipo_fuente) == (
        "fallback",
        "Pasiva",
        1,
        "Sin fuente",
    )
    assert e.por_desconocimiento and not e.necesita_revision
    (call,) = fake.calls
    assert call["questions"] is JUDGE_QUESTIONS and call["state"] == build_state(RUN, ALBORADA)
    (trace,) = judge.traces
    assert (trace.nodo, trace.modelo, trace.tokens_in, trace.tokens_out) == (
        "judge:llm",
        "deepseek-chat",
        1200,
        300,
    )
    assert trace.coste_eur == pytest.approx((1200 * 0.28 + 300 * 0.42) / 1e6 * 0.86)


def test_fallback_con_baja_confianza_se_marca(settings: Settings) -> None:
    fake = FakeSystemOneClient(sdk_answers(confidence=0.4))
    e = LLMJudge(settings, [ALBORADA], client_factory=lambda: fake).evaluate(RUN, ALBORADA)
    assert e.origen == "fallback" and e.necesita_revision


def test_usage_sin_tokens(settings: Settings) -> None:
    fake = FakeSystemOneClient(
        usage=SimpleNamespace(input_tokens_total=None, output_tokens_total=None)
    )
    judge = LLMJudge(settings, [ALBORADA], client_factory=lambda: fake)
    judge.evaluate(RUN, ALBORADA)
    assert judge.traces[0].tokens_in == 0 and judge.traces[0].coste_eur == 0


def test_build_judge(settings: Settings) -> None:
    con_clave = build_judge(settings, [ALBORADA])
    assert isinstance(con_clave, JevJudge) and isinstance(con_clave.fallback, LLMJudge)
    sin_clave = build_judge(
        settings.model_copy(update={"typesafe_api_key": SecretStr("")}), [ALBORADA]
    )
    assert isinstance(sin_clave, LLMJudge) and sin_clave.fallback is None


def test_sesion_real_del_adaptador(settings: Settings) -> None:
    async def open_and_close() -> tuple[str, str]:
        async with LLMJudge(settings, [ALBORADA])._open() as session:
            assert isinstance(session, _AdapterSession)
            return session.provider.model_name, session.provider.api

    assert asyncio.run(open_and_close()) == ("deepseek-chat", "chat_completions")

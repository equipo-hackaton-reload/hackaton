import asyncio
from typing import Any

import pytest
from typesafe_sdk import AsyncTypeSafeClient

from posiq.adapters.budget import Budget, BudgetExceeded
from posiq.adapters.cache import DiskCache
from posiq.adapters.judge.base import SystemOneJudge, discrepa, score_confidence
from posiq.adapters.judge.jev import JevJudge
from posiq.domain.detection import detect_in_run
from posiq.domain.judge_questions import JUDGE_QUESTIONS, build_state
from posiq.domain.schemas import Brand, Run
from posiq.ports import Judge
from posiq.settings import Settings
from tests.adapters.judge_fakes import FakeSystemOneClient, sdk_answers
from tests.domain.factories import brand, run, source

ALBORADA = brand(aliases=["Alborada"])
LIDER = brand(id="lider", nombre="Grupo Valdecruz", rol="lider", aliases=["Valdecruz"])
MARKET = [ALBORADA, LIDER]
RUN = run(
    texto="Valdecruz es la referencia; Alborada también [1].",
    marcas=["alborada", "lider"],
    fuentes=[source()],
)


def jev(settings: Settings, fake: FakeSystemOneClient, **kw: Any) -> JevJudge:
    return JevJudge(settings, MARKET, client_factory=lambda: fake, **kw)


def as_dicts(answers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {k: v.model_dump(mode="json") for k, v in answers.items()}


class StubFallback(SystemOneJudge):
    origen = "fallback"

    def __init__(self, fake: FakeSystemOneClient) -> None:
        super().__init__(
            name="stub",
            model="stub",
            market=MARKET,
            accept=0.8,
            fallback_threshold=0.55,
            price_in_usd_per_m=0,
            price_out_usd_per_m=0,
            usd_eur=1,
        )
        self.fake = fake

    def _open(self) -> Any:
        return self.fake

    async def _call(
        self, client: Any, state: dict[str, Any], questions: Any
    ) -> tuple[dict[str, Any], int, int, str | None]:
        response = await client.system_one(state=state, questions=questions)
        return as_dicts(response.answers), 0, 0, None


def test_cumple_el_contrato_judge(settings: Settings) -> None:
    judge: Judge = jev(settings, FakeSystemOneClient())
    assert judge.name == "jev"


def test_confianza_alta_se_acepta(settings: Settings) -> None:
    fake = FakeSystemOneClient(sdk_answers(confidence=0.9, sentiment_conf=0.1))
    e = jev(settings, fake).evaluate(RUN, ALBORADA)
    assert (e.origen, e.necesita_revision, e.study_id) == ("jev", False, "S-1")
    assert e.confianza == pytest.approx(0.9)  # sentiment no cuenta para la confianza
    assert (e.aparece, e.posicion, e.tipo_mencion, e.fuerza) == (
        True,
        2,
        "Recomendación activa",
        3,
    )
    (call,) = fake.calls
    assert call["questions"] is JUDGE_QUESTIONS
    assert call["state"] == build_state(RUN, ALBORADA)
    assert call["model"] == "jev-1.13"


def test_confianza_intermedia_se_marca_para_revision(settings: Settings) -> None:
    e = jev(settings, FakeSystemOneClient(sdk_answers(strength_conf=0.7))).evaluate(RUN, ALBORADA)
    assert e.origen == "jev" and e.necesita_revision and e.confianza == pytest.approx(0.7)


def test_confianza_baja_delega_en_el_fallback(settings: Settings) -> None:
    fallback = StubFallback(FakeSystemOneClient())
    judge = jev(settings, FakeSystemOneClient(sdk_answers(mention_conf=0.3)), fallback=fallback)
    e = judge.evaluate(RUN, ALBORADA)
    assert e.origen == "fallback" and not e.necesita_revision
    assert len(fallback.fake.calls) == 1


def test_confianza_baja_sin_fallback_se_marca(settings: Settings) -> None:
    e = jev(settings, FakeSystemOneClient(sdk_answers(mention_conf=0.3))).evaluate(RUN, ALBORADA)
    assert e.origen == "jev" and e.necesita_revision


def test_discrepancia_va_a_revision_aunque_el_fallback_este_seguro(settings: Settings) -> None:
    # Las reglas ven a Alborada en RUN; Jev dice que no aparece → discrepancia.
    fallback = StubFallback(FakeSystemOneClient())  # el fallback acierta y con confianza 0,9
    judge = jev(settings, FakeSystemOneClient(sdk_answers(mentioned=0.05)), fallback=fallback)
    outcome = asyncio.run(judge.ajudge(RUN, ALBORADA))
    assert outcome.discrepa and outcome.confianza == pytest.approx(0.5)
    e = judge.evaluate(RUN, ALBORADA)
    assert e.origen == "fallback" and e.confianza == pytest.approx(0.9)
    assert e.necesita_revision
    assert len(fallback.fake.calls) == 1


def test_discrepancia_por_tipo_ausente_tambien_va_a_revision(settings: Settings) -> None:
    fallback = StubFallback(FakeSystemOneClient())
    answers = sdk_answers(mention="ausente")
    e = jev(settings, FakeSystemOneClient(answers), fallback=fallback).evaluate(RUN, ALBORADA)
    assert e.origen == "fallback" and e.necesita_revision


def test_sin_discrepancia_el_fallback_seguro_se_acepta(settings: Settings) -> None:
    fallback = StubFallback(FakeSystemOneClient())
    judge = jev(settings, FakeSystemOneClient(sdk_answers(strength_conf=0.4)), fallback=fallback)
    assert not asyncio.run(judge.ajudge(RUN, ALBORADA)).discrepa
    e = judge.evaluate(RUN, ALBORADA)
    assert e.origen == "fallback" and not e.necesita_revision


def test_discrepa_coincide_con_el_limite_de_confianza() -> None:
    presente = detect_in_run(RUN, MARKET)["alborada"]
    assert discrepa(as_dicts(sdk_answers(mentioned=0.1)), presente)
    assert discrepa(as_dicts(sdk_answers(mention="ausente")), presente)
    assert not discrepa(as_dicts(sdk_answers()), presente)
    assert discrepa(as_dicts(sdk_answers(mentioned=0.9)), None)
    assert not discrepa(as_dicts(sdk_answers(mentioned=0.1)), None)


def test_traza_con_el_modelo_que_respondio(settings: Settings) -> None:
    fake = FakeSystemOneClient(model="jev-1.13.2")
    judge = jev(settings, fake)
    judge.evaluate(RUN, ALBORADA)
    assert judge.traces[0].modelo == "jev-1.13.2"
    assert fake.calls[0]["model"] == "jev-1.13"


def test_discrepancia_con_las_reglas_limita_la_confianza() -> None:
    ausente = as_dicts(sdk_answers(mentioned=0.1))
    assert score_confidence(ausente, None) == pytest.approx(0.8)
    juez_ve_lo_que_reglas_no = as_dicts(sdk_answers(mentioned=0.9))
    assert score_confidence(juez_ve_lo_que_reglas_no, None) == pytest.approx(0.5)


def test_traza_y_presupuesto(settings: Settings) -> None:
    budget = Budget(max_eur=1.0, study_id="S-1")
    judge = jev(settings, FakeSystemOneClient(), budget=budget)
    judge.evaluate(RUN, ALBORADA)
    (trace,) = judge.traces
    assert (trace.nodo, trace.modelo, trace.tokens_in, trace.tokens_out) == (
        "judge:jev",
        "jev-1.13",
        1000,
        20,
    )
    assert trace.coste_eur == pytest.approx(1000 * 0.04e-6 * 0.86)
    assert budget.traces == [trace]
    with pytest.raises(BudgetExceeded):
        jev(settings, FakeSystemOneClient(), budget=Budget(max_eur=0)).evaluate(RUN, ALBORADA)


def test_cache_evita_la_segunda_llamada(settings: Settings) -> None:
    cache = DiskCache.from_settings(settings)
    fake = FakeSystemOneClient()
    first = jev(settings, fake, cache=cache).evaluate(RUN, ALBORADA)
    judge = jev(settings, fake, cache=cache)
    second = judge.evaluate(RUN, ALBORADA)
    assert len(fake.calls) == 1 and first == second
    assert judge.traces[0].coste_eur == 0


def test_lote_concurrente_con_semaforo(settings: Settings) -> None:
    fake = FakeSystemOneClient()
    judge = jev(settings.model_copy(update={"judge_concurrency": 3}), fake)
    runs: list[Run] = [run(id=f"EJ-{i}", texto="Alborada", marcas=["alborada"]) for i in range(10)]
    pairs: list[tuple[Run, Brand]] = [(r, ALBORADA) for r in runs]
    results = judge.evaluate_many(pairs)
    assert [e.run_id for e in results] == [r.id for r in runs]
    assert fake.max_in_flight == 3 and fake.closed == 1


def test_marca_fuera_del_mercado_se_detecta_igual(settings: Settings) -> None:
    otra = brand(id="otra", nombre="Oftalmos Centro")
    r = run(texto="Oftalmos Centro", marcas=["otra"])
    assert jev(settings, FakeSystemOneClient()).evaluate(r, otra).posicion == 1


def test_cliente_real_por_defecto(settings: Settings) -> None:
    assert isinstance(JevJudge(settings, MARKET)._open(), AsyncTypeSafeClient)

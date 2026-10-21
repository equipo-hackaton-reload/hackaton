"""`ConsensusJudge`: N llamadas al juez, voto por mayoría del dominio y trazas de cada llamada."""

from typing import Any

import pytest

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.judge import ConsensusJudge
from posiq.adapters.judge.jev import JevJudge
from posiq.domain.schemas import Brand, Evaluation, Run, Trace
from posiq.ports import Judge
from posiq.settings import Settings
from tests.adapters.judge_fakes import FakeSystemOneClient, sdk_answers
from tests.adapters.test_judge_jev import ALBORADA, MARKET, RUN
from tests.domain.factories import evaluation, run


class CyclingClient(FakeSystemOneClient):
    """Devuelve las respuestas de `secuencia` una tras otra (en bucle)."""

    def __init__(self, secuencia: list[dict[str, Any]]) -> None:
        super().__init__()
        self.secuencia = secuencia

    async def system_one(self, state: Any, questions: Any, **kwargs: Any) -> Any:
        self.answers = self.secuencia[len(self.calls) % len(self.secuencia)]
        return await super().system_one(state, questions, **kwargs)


def jev(settings: Settings, fake: FakeSystemOneClient, **kw: Any) -> JevJudge:
    return JevJudge(settings, MARKET, client_factory=lambda: fake, **kw)


class SyncJudge:
    """Juez solo síncrono (sin `aevaluate_many`), con trazas propias."""

    def __init__(self, name: str, fuerza: int) -> None:
        self.name = name
        self.fuerza = fuerza
        self.traces: list[Trace] = []

    def evaluate(self, run: Run, brand: Brand) -> Evaluation:
        return evaluation(brand.id, run.id, fuerza=self.fuerza, study_id=run.study_id)


def test_cumple_el_puerto_judge() -> None:
    judge: Judge = ConsensusJudge([SyncJudge("a", 3)])
    assert judge.name == "consenso:1xa"


def test_mayoria_de_tres_llamadas_y_trazas(settings: Settings) -> None:
    fake = CyclingClient([sdk_answers(level=3), sdk_answers(level=2), sdk_answers(level=3)])
    budget = Budget(max_eur=1.0, study_id="S-1")
    juez = ConsensusJudge.repetido(jev(settings, fake, budget=budget), 3)
    e = juez.evaluate(RUN, ALBORADA)
    assert len(fake.calls) == 3
    assert e.fuerza == 3
    assert e.confianza == pytest.approx(2 / 3) and e.necesita_revision
    assert [t.nodo for t in juez.traces] == ["judge:jev"] * 3
    assert all(t.tokens_in == 1000 and t.modelo == settings.jev_model for t in juez.traces)
    assert budget.traces == juez.traces
    (detalle,) = juez.consensos
    assert detalle.n == 3 and detalle.acuerdo_por_campo["fuerza"] == pytest.approx(2 / 3)


def test_repetido_con_cache_se_rechaza(settings: Settings) -> None:
    con_cache = jev(settings, FakeSystemOneClient(), cache=DiskCache.from_settings(settings))
    with pytest.raises(ValueError, match="caché"):
        ConsensusJudge.repetido(con_cache, 3)
    with pytest.raises(ValueError):
        ConsensusJudge.repetido(jev(settings, FakeSystemOneClient()), 0)
    with pytest.raises(ValueError):
        ConsensusJudge([])


def test_lote_vota_por_pareja_y_no_duplica_trazas(settings: Settings) -> None:
    fake = CyclingClient([sdk_answers(level=3), sdk_answers(level=1)])
    juez = ConsensusJudge.repetido(jev(settings, fake), 3)
    runs = [run(id=f"EJ-{i}", texto="Alborada", marcas=["alborada"]) for i in range(2)]
    pairs: list[tuple[Run, Brand]] = [(r, ALBORADA) for r in runs]
    out = juez.evaluate_many(pairs)
    assert [e.run_id for e in out] == ["EJ-0", "EJ-1"]
    assert len(fake.calls) == 6 and len(juez.traces) == 6
    assert len(juez.consensos) == 2
    juez.evaluate_many(pairs[:1])
    assert len(juez.traces) == 9


def test_jueces_distintos_y_solo_sincronos() -> None:
    juez = ConsensusJudge([SyncJudge("a", 3), SyncJudge("b", 1), SyncJudge("c", 1)])
    assert juez.name == "consenso:a+b+c"
    (e,) = juez.evaluate_many([(RUN, ALBORADA)])
    assert e.fuerza == 1 and e.confianza == pytest.approx(2 / 3)

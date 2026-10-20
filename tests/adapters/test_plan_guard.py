from typing import Any

import pytest
from typesafe_sdk import NoulAnswer, ScoreAnswer

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.judge import JevJudge, LLMJudge
from posiq.adapters.judge.plan_guard import PlanGuard, build_plan_guard
from posiq.domain.plan_questions import PLAN_QUESTIONS, build_action_state
from posiq.domain.schemas import Finding, Phase, Plan
from posiq.settings import Settings
from tests.adapters.judge_fakes import FakeSystemOneClient
from tests.domain.factories import action, brief

FINDING = Finding(
    id="F1",
    study_id="S-1",
    titulo="Baja visibilidad en Barcelona",
    descripcion="4 %",
    impacto="L",
    confianza=0.65,
    cifra=0.04,
    unidad="fraccion",
    origen_cifra="visibilidad espontánea por ciudad: Barcelona",
    evaluation_ids=["EJ-1:alborada"],
)
PLAN = Plan(
    study_id="S-1",
    objetivos=[],
    fases=[
        Phase(
            nombre="Fase 0",
            semanas=4,
            objetivo="o",
            acciones=[action(id="A1"), action(id="A2", descripcion="Mejorar el SEO")],
        )
    ],
    presupuesto_estimado_eur=1000,
    respeta_restricciones=True,
)


def plan_answers(p: float = 0.9, level: int = 3, conf: float = 0.9) -> dict[str, Any]:
    out: dict[str, Any] = {
        k: NoulAnswer(type="noul", noul=p)
        for k in (
            "es_especifica",
            "coherente_con_hallazgo",
            "respeta_restricciones",
            "realista_para_equipo",
        )
    }
    out["calidad_global"] = ScoreAnswer(
        type="score",
        score=float(level),
        confidence=conf,
        legend={i: f"nivel {i}" for i in range(4)},
        probabilities={i: 0.9 if i == level else 0.03 for i in range(4)},
    )
    return out


def guard(settings: Settings, fake: FakeSystemOneClient, **kw: Any) -> PlanGuard:
    return PlanGuard(JevJudge(settings, [], client_factory=lambda: fake, **kw))


def test_evalua_cada_accion_con_las_preguntas_del_plan(settings: Settings) -> None:
    fake = FakeSystemOneClient(plan_answers())
    budget = Budget(max_eur=1.0, study_id="S-1")
    g = guard(settings, fake, budget=budget)
    q = g.assess(PLAN, [FINDING], brief())
    assert [a.action_id for a in q.acciones] == ["A1", "A2"]
    assert q.pct_especificas == 1.0 and q.calidad_media == 3 and q.por_debajo_umbral == []
    assert (q.study_id, q.juez, q.modelo) == ("S-1", "jev", "jev-latest")
    assert {id(c["questions"]) for c in fake.calls} == {id(PLAN_QUESTIONS)}
    states = [c["state"] for c in fake.calls]
    assert build_action_state(PLAN.acciones[0], [FINDING], brief()) in states
    assert fake.closed == 1
    assert [t.nodo for t in g.judge.traces] == ["plan_guard:jev"] * 2
    assert {t.prompt_version for t in budget.traces} == {"plan_questions@1.0"}


def test_acciones_flojas_por_debajo_de_umbral(settings: Settings) -> None:
    q = guard(settings, FakeSystemOneClient(plan_answers(p=0.2, level=1))).assess(
        PLAN, [FINDING], brief()
    )
    assert q.pct_especificas == 0 and q.por_debajo_umbral == ["A1", "A2"]
    assert "Informe orientativo" in q.nota


def test_baja_confianza_pregunta_al_fallback(settings: Settings) -> None:
    fallback_fake = FakeSystemOneClient(plan_answers(p=0.95, conf=0.9))
    fallback = LLMJudge(settings, [], client_factory=lambda: fallback_fake)
    jev_fake = FakeSystemOneClient(plan_answers(p=0.55, conf=0.9))
    g = guard(settings, jev_fake, fallback=fallback)
    q = g.assess(PLAN, [FINDING], brief())
    assert len(fallback_fake.calls) == 2
    assert all(a.confianza == pytest.approx(0.9) for a in q.acciones)
    assert [t.nodo for t in fallback.traces] == ["plan_guard:llm"] * 2


def test_cache_entre_ejecuciones(settings: Settings) -> None:
    cache = DiskCache.from_settings(settings)
    fake = FakeSystemOneClient(plan_answers())
    guard(settings, fake, cache=cache).assess(PLAN, [FINDING], brief())
    guard(settings, fake, cache=cache).assess(PLAN, [FINDING], brief())
    assert len(fake.calls) == 2


def test_build_plan_guard(settings: Settings) -> None:
    assert isinstance(build_plan_guard(settings).judge, JevJudge)

"""Llamadas pagadas que acaban en error: también dejan `Trace` y cuentan en el coste (ADR 0018)."""

from collections.abc import Sequence
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from posiq.adapters.budget import Budget, BudgetExceeded
from posiq.adapters.engines.kit import KitEngine
from posiq.adapters.llm.openai_compat import LLMOutputError
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application import nodes
from posiq.application.deps import trazas_de_fallo
from posiq.application.graph import serializer
from posiq.application.nodes.judge import trazas_del_juez
from posiq.application.runner import StudyRunner
from posiq.domain.schemas import Brand, Evaluation, Market, Run, Trace
from tests.application.fakes import (
    KIT_DIR,
    DetectionJudge,
    FakeLLM,
    kit_llm,
    make_deps,
    plan_from_findings,
    trace,
)
from tests.application.test_nodes import analyzed_state, kit_state_until_judge

pytestmark = pytest.mark.anyio

BRIEF = "# Brief\n\n**Marca:** Clínica Alborada Visión"


def failing(prompt_name: str, coste: float) -> Any:
    """Handler que falla como `OpenAICompatLLM` tras intentos ya cobrados."""

    def handler(state: dict[str, Any]) -> Any:
        raise LLMOutputError(prompt_name, 3, "no valida", trace("?", prompt_name, coste))

    return handler


class StudyLLM(FakeLLM):
    """FakeLLM cuyas excepciones llevan la traza con el `study_id` real."""

    def structured(self, schema: Any, prompt_name: str, state: Any, *, study_id: str) -> Any:
        try:
            return super().structured(schema, prompt_name, state, study_id=study_id)
        except LLMOutputError as exc:
            assert exc.trace is not None
            exc.trace = exc.trace.model_copy(update={"study_id": study_id})
            raise


def runner(repo: SqlStudyRepo, llm: FakeLLM, **kw: Any) -> StudyRunner:
    deps = make_deps(llm, KitEngine.all_motors(KIT_DIR), repo, **kw)
    return StudyRunner({"kit": deps}, InMemorySaver(serde=serializer()), repo)


@pytest.mark.parametrize("nodo", ["intake.v1", "market.v1"])
async def test_a_failed_llm_call_is_traced_and_costed(repo: SqlStudyRepo, nodo: str) -> None:
    llm = StudyLLM(kit_llm().handlers)
    llm.handlers[nodo] = failing(nodo, 0.012)
    r = runner(repo, llm)
    study = r.create("kit")
    await r.start(study, BRIEF)

    assert r.estado(study) == "error" and "LLMOutputError" in r.fallos[study.id]
    values, _ = await r.state(study.id)
    fallida = [t for t in values["traces"] if t.nodo == nodo]
    assert len(fallida) == 1 and fallida[0].coste_eur == 0.012
    assert values["coste_acumulado_eur"] == pytest.approx(0.012)
    assert [t.nodo for t in repo.get_traces(study.id)][-1] == nodo


async def test_the_failed_call_counts_in_the_budget(repo: SqlStudyRepo) -> None:
    llm = StudyLLM(kit_llm().handlers)
    llm.handlers["intake.v1"] = failing("intake.v1", 1.0)
    r = runner(repo, llm, budget_max=0.5)
    study = r.create("kit")
    await r.start(study, BRIEF)

    assert "BudgetExceeded" in r.fallos[study.id]
    values, _ = await r.state(study.id)
    assert values["coste_acumulado_eur"] == pytest.approx(1.0)


async def test_plan_retry_failure_keeps_the_first_paid_call(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    intentos: list[int] = []

    def handler(s: dict[str, Any]) -> Any:
        intentos.append(1)
        if len(intentos) == 1:
            return plan_from_findings(s, restricciones=[])  # incumple el brief: reintenta
        raise LLMOutputError("plan.v1", 3, "no valida", trace("?", "plan.v1", 0.02))

    llm = StudyLLM({"plan.v1": handler}, coste=0.01)
    with pytest.raises(LLMOutputError) as info:
        await nodes.plan(state, make_deps(llm, [], repo))
    costes = sorted(t.coste_eur for t in trazas_de_fallo(info.value))
    assert costes == [0.01, 0.02]


class FallbackJudge(DetectionJudge):
    """Juez con un fallback que lleva sus propias trazas (como `JevJudge` + `LLMJudge`)."""

    name = "jev"

    def __init__(self, market: Market, budget: Budget | None = None) -> None:
        super().__init__(market, budget)
        self.fallback = DetectionJudge(market, budget)

    async def aevaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        out = await super().aevaluate_many(pairs)
        self.fallback.traces.append(trace(pairs[0][0].study_id, "judge:llm", 0.003))
        return out


async def test_judge_node_keeps_the_fallback_traces(repo: SqlStudyRepo) -> None:
    state = await kit_state_until_judge(repo)
    update = await nodes.judge(state, make_deps(kit_llm(), [], repo, judge_factory=FallbackJudge))
    assert sorted(t.nodo for t in update["traces"]) == ["judge:deteccion", "judge:llm"]
    assert update["coste_acumulado_eur"] == pytest.approx(0.003)


class BrokeJudge(FallbackJudge):
    async def aevaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        await super().aevaluate_many(pairs)
        raise BudgetExceeded("tope")


async def test_judge_failure_carries_what_was_already_paid(repo: SqlStudyRepo) -> None:
    state = await kit_state_until_judge(repo)
    with pytest.raises(BudgetExceeded) as info:
        await nodes.judge(state, make_deps(kit_llm(), [], repo, judge_factory=BrokeJudge))
    assert sorted(t.nodo for t in trazas_de_fallo(info.value)) == ["judge:deteccion", "judge:llm"]


def test_judge_traces_walk_fallback_and_consensus_without_duplicates() -> None:
    a, b = trace("S", "judge:jev", 0.1), trace("S", "judge:llm", 0.2)

    class J:
        def __init__(self, traces: list[Trace], **kw: Any) -> None:
            self.traces = traces
            for k, v in kw.items():
                setattr(self, k, v)

    llm = J([b])
    jev = J([a], fallback=llm)
    consenso = J([a, b], jueces=[jev, jev])
    assert trazas_del_juez(consenso) == [a, b]

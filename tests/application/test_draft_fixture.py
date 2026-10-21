"""Contratos narrativos, fixtures explícitas y selección de motores del mercado confirmado."""

from dataclasses import replace
from typing import Any

import pytest
from pydantic import ValidationError

from posiq.adapters.budget import Budget
from posiq.adapters.llm.fixture import FixtureJudge, FixtureLLM
from posiq.application import nodes
from posiq.application.nodes.review import parse_market
from posiq.application.nodes.write import assemble_proposal
from posiq.application.schemas_draft import ProposalDraft
from posiq.domain.schemas import BriefSummary
from tests.application.fakes import FakeEngine, kit_llm, kit_settings, make_deps
from tests.application.test_nodes import analyzed_state, merge
from tests.golden.conftest import alborada_brief_summary

pytestmark = pytest.mark.anyio


def test_fixture_brief_and_trace_match_golden_without_network() -> None:
    llm = FixtureLLM(kit_settings())
    brief, trace = llm.structured(BriefSummary, "intake.v1", {"brief": "Alborada"}, study_id="s")
    assert brief == alborada_brief_summary()
    assert trace.coste_eur == 0 and trace.study_id == "s"
    with pytest.raises(ValueError, match="solo admite"):
        llm.structured(BriefSummary, "intake.v1", {"brief": "Otra marca"}, study_id="s")
    from posiq.prompts import PromptSet

    prompts, _ = llm.structured(PromptSet, "prompts.v1", {}, study_id="s")
    assert len(prompts.prompts) == 52


async def test_draft_cannot_replace_metrics_or_reference_unknown_findings(repo: Any) -> None:
    deps = make_deps(kit_llm(), [], repo)
    state = await analyzed_state(repo)
    state = merge(state, await nodes.plan(state, deps))
    draft = deps.llm.handlers["write.v1"](
        {"hallazgos": [f.model_dump() for f in state["findings"]]}
    )
    assert isinstance(draft, ProposalDraft)
    with pytest.raises(ValidationError):
        ProposalDraft.model_validate(draft.model_dump() | {"metrics": {"score": 99}})
    with pytest.raises(ValueError, match="exactamente"):
        assemble_proposal(
            draft.model_copy(update={"interpretacion_hallazgos": {"inventado": "x"}}), state
        )


async def test_real_engine_factory_receives_confirmed_ids_and_study_budget(repo: Any) -> None:
    deps = make_deps(kit_llm(), [], repo)
    state = await analyzed_state(repo)
    state["modo"] = "real"
    state["prompts"] = state["prompts"][:1]
    received = []

    def factory(ids: list[str], budget: Budget) -> list[Any]:
        received.append((ids, budget.study_id))
        return [FakeEngine(texto="Alborada", coste=0.01)]

    update = await nodes.run(state, replace(deps, engine_factory=factory))
    assert received == [([b.id for b in state["market"].marcas], state["study_id"])]
    assert len(update["runs"]) == 3
    assert sum(t.coste_eur for t in update["traces"]) == pytest.approx(0.03)


async def test_fixture_judge_is_neutral_and_false_is_not_approval(repo: Any) -> None:
    state = await analyzed_state(repo)
    market = state["market"]
    judge = FixtureJudge(market)
    run = state["runs"][0]
    brand = market.marcas[0]
    result = judge.evaluate(run, brand)
    assert result.fuerza == (1 if result.aparece else 0)
    assert result.sentimiento is None
    with pytest.raises(ValueError):
        parse_market({"aprobado": False}, state)


async def test_real_adapter_traces_are_not_charged_twice(repo: Any, monkeypatch: Any) -> None:
    from posiq.adapters.engines.base import EngineReply
    from posiq.adapters.engines.openai import OpenAIEngine

    state = await analyzed_state(repo)
    state["modo"] = "real"
    state["prompts"] = state["prompts"][:1]
    budgets = []

    def factory(ids: list[str], budget: Budget) -> list[Any]:
        budgets.append(budget)
        engine = OpenAIEngine(kit_settings(openai_api_key="mock-key"), ids, budget=budget)
        monkeypatch.setattr(
            engine,
            "_call",
            lambda _: EngineReply(
                texto="Alborada", urls=[], modelo="mock", tokens_in=1000, tokens_out=10
            ),
        )
        return [engine]

    deps = replace(make_deps(kit_llm(), [], repo), engine_factory=factory)
    update = await nodes.run(state, deps)
    assert len(update["traces"]) == 3
    assert all(t.tokens_in == 1000 and t.tokens_out == 10 for t in update["traces"])
    assert budgets[0].total_eur == pytest.approx(sum(t.coste_eur for t in update["traces"]))


def test_runner_does_not_report_review_until_graph_is_paused(repo: Any) -> None:
    from langgraph.checkpoint.memory import InMemorySaver

    from posiq.application.runner import StudyRunner

    runner = StudyRunner({"kit": make_deps(kit_llm(), [], repo)}, InMemorySaver(), repo)
    study = runner.create("kit").model_copy(update={"estado": "esperando_revision_competidores"})
    runner.en_marcha.add(study.id)
    assert runner.estado(study) == "en_curso"


def test_proposal_draft_cobertura_opcional() -> None:
    assert ProposalDraft.model_fields["cobertura_brief"].default == {}

"""Cada nodo por separado, con `LLM`, `Engine` y juez falsos (sin red)."""

import sys
from typing import Any

import pytest
from pydantic import BaseModel, SecretStr

from posiq.adapters.budget import Budget, BudgetExceeded
from posiq.adapters.engines.kit import KitEngine
from posiq.adapters.errors import MissingCredentialError
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application import nodes
from posiq.application.deps import new_study
from posiq.application.kit import load_kit
from posiq.application.nodes.market import reconcile
from posiq.application.nodes.review import parse_market, parse_plan
from posiq.application.nodes.write import LIMITACION_KIT, LIMITACION_REGLAS, PREFIJO_PENDIENTES
from posiq.application.state import StudyState, initial_state
from posiq.domain.schemas import Brand, Market, PromptInstance, Run, Trace
from tests.application.fakes import (
    KIT_DIR,
    RESTRICCIONES,
    DetectionJudge,
    FakeEngine,
    FakeGuard,
    FakeLLM,
    brief_alborada,
    kit_llm,
    kit_settings,
    make_deps,
    plan_from_findings,
    proposal_draft,
)
from tests.domain.factories import prompt

pytestmark = pytest.mark.anyio

KIT = load_kit(str(KIT_DIR))


def merge(state: StudyState, update: dict[str, Any]) -> StudyState:
    """Aplica una actualización como LangGraph: `traces` y `errores` se acumulan."""
    out: dict[str, Any] = {**state, **update}
    for key in ("traces", "errores"):
        out[key] = [*state.get(key, []), *update.get(key, [])]  # type: ignore[misc]
    return out  # type: ignore[return-value]


def start(repo: SqlStudyRepo, modo: str = "kit") -> StudyState:
    study = new_study(modo)  # type: ignore[arg-type]
    repo.save_study(study)
    return initial_state(study, "# Brief de Clínica Alborada Visión")


async def kit_state_until_judge(repo: SqlStudyRepo, n_prompts: int = 6) -> StudyState:
    """Estado tras `intake` → `market` (confirmado) → `prompts` → `run` con unos pocos prompts."""
    deps = make_deps(kit_llm(), KitEngine.all_motors(KIT_DIR), repo)
    state = start(repo)
    state = merge(state, await nodes.intake(state, deps))
    state = merge(state, await nodes.market(state, deps))
    state = merge(state, {"market": parse_market(None, state), "revision_pendiente": "none"})
    state = merge(state, {"prompts": KIT.prompts[:n_prompts]})
    return merge(state, await nodes.run(state, deps))


# --- intake y market ------------------------------------------------------------------------------


async def test_intake_structures_the_brief_and_updates_the_study(repo: SqlStudyRepo) -> None:
    llm = kit_llm()
    state = start(repo)
    update = await nodes.intake(state, make_deps(llm, [], repo))

    assert update["brief"] == brief_alborada()
    assert llm.calls == [("intake.v1", {"brief": state["brief_texto"]})]
    assert [t.nodo for t in update["traces"]] == ["intake.v1"]
    study = repo.get_study(state["study_id"])
    assert study.brief == brief_alborada() and study.brand_id == "clinica-alborada-vision"


async def test_market_in_kit_mode_uses_kit_ids_and_asks_for_review(repo: SqlStudyRepo) -> None:
    llm = kit_llm()
    deps = make_deps(llm, [], repo)
    state = start(repo)
    state = merge(state, await nodes.intake(state, deps))
    update = await nodes.market(state, deps)

    market: Market = update["market"]
    assert [b.id for b in market.marcas] == [b.id for b in KIT.brands_in_runs()]
    assert not market.confirmado_por_humano
    assert update["revision_pendiente"] == "competidores"
    candidatos = llm.calls[-1][1]["candidatos"]
    assert {c["id"] for c in candidatos} == {b.id for b in KIT.brands_in_runs()}
    study = repo.get_study(state["study_id"])
    assert study.estado == "esperando_revision_competidores"
    assert study.brand_id == "clinica-alborada-vision"


def test_reconcile_maps_aliases_and_drops_duplicates() -> None:
    candidatos = [Brand(id="lasernitida", nombre="Láser Nítida", aliases=["Nítida"], rol="foco")]
    propuesto = Market(
        marcas=[
            Brand(id="x1", nombre="nitida", rol="contexto"),
            Brand(id="x2", nombre="Láser Nítida", rol="contexto"),
            Brand(id="nueva", nombre="Clínica Nueva", rol="contexto"),
        ]
    )
    out = reconcile(propuesto, candidatos)
    assert [b.id for b in out.marcas] == ["lasernitida", "nueva"]
    assert out.marcas[0].aliases == ["Nítida"]


async def test_market_in_real_mode_has_no_candidates(repo: SqlStudyRepo) -> None:
    llm = kit_llm()
    deps = make_deps(llm, [], repo)
    state = start(repo, "real")
    state = merge(state, await nodes.intake(state, deps))
    llm.handlers["market.v1"] = lambda s: Market(
        marcas=[Brand(id="alborada", nombre="Clínica Alborada Visión", rol="foco")]
    )
    update = await nodes.market(state, deps)
    assert llm.calls[-1][1]["candidatos"] == []
    assert [b.id for b in update["market"].marcas] == ["alborada"]


# --- revisiones -----------------------------------------------------------------------------------


async def test_parse_market_confirms_and_requires_the_brief_brand(repo: SqlStudyRepo) -> None:
    deps = make_deps(kit_llm(), [], repo)
    state = start(repo)
    state = merge(state, await nodes.intake(state, deps))
    state = merge(state, await nodes.market(state, deps))

    assert parse_market({"aprobado": True}, state).confirmado_por_humano
    editado = {"marcas": [m.model_dump() for m in state["market"].marcas[:3]]}
    assert len(parse_market(editado, state).marcas) == 3
    sin_foco = {"marcas": [{"id": "otra", "nombre": "Otra", "rol": "foco"}]}
    with pytest.raises(ValueError, match="no está en el mercado"):
        parse_market(sin_foco, state)
    with pytest.raises(ValueError):
        parse_market({"marcas": "no es una lista"}, state)


# --- prompts --------------------------------------------------------------------------------------


async def test_prompts_in_kit_mode_use_the_kit_bank_without_llm(repo: SqlStudyRepo) -> None:
    llm = FakeLLM({})
    update = await nodes.prompts(start(repo), make_deps(llm, [], repo))
    assert update["prompts"] == KIT.prompts
    assert llm.calls == []


class _PromptSet(BaseModel):
    prompts: list[PromptInstance]


async def test_prompts_in_real_mode_ask_the_llm(
    repo: SqlStudyRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts_module = sys.modules["posiq.application.nodes.prompts"]
    monkeypatch.setattr(prompts_module, "prompt_set_schema", lambda: _PromptSet)
    llm = FakeLLM({"prompts.v1": lambda s: _PromptSet(prompts=[prompt("P-1"), prompt("P-2")])})
    state = start(repo, "real")
    state = merge(
        state,
        {
            "brief": brief_alborada(),
            "market": Market(marcas=[Brand(id="a", nombre="A", rol="foco")]),
        },
    )
    update = await nodes.prompts(state, make_deps(llm, [], repo))
    assert [p.id for p in update["prompts"]] == ["P-1", "P-2"]
    assert llm.names() == ["prompts.v1"]
    assert len(update["traces"]) == 1


# --- run ------------------------------------------------------------------------------------------


async def test_run_in_kit_mode_takes_every_recorded_repetition(repo: SqlStudyRepo) -> None:
    state = await kit_state_until_judge(repo, n_prompts=2)
    ids = {p.id for p in KIT.prompts[:2]}
    esperadas = [r for r in KIT.runs if r.prompt_id in ids]
    assert sorted(r.id for r in state["runs"]) == sorted(r.id for r in esperadas)
    assert {r.study_id for r in state["runs"]} == {state["study_id"]}
    assert state["coste_acumulado_eur"] == 0
    assert len(repo.get_runs(state["study_id"])) == len(esperadas)


async def test_run_in_kit_mode_skips_prompts_missing_from_the_kit(repo: SqlStudyRepo) -> None:
    state = start(repo)
    state = merge(
        state,
        {
            "market": Market(marcas=KIT.brands_in_runs()),
            "prompts": [KIT.prompts[0], prompt("NO-EXISTE")],
        },
    )
    update = await nodes.run(state, make_deps(kit_llm(), KitEngine.all_motors(KIT_DIR), repo))
    assert {r.prompt_id for r in update["runs"]} == {KIT.prompts[0].id}
    assert len(update["errores"]) == 1 and "NO-EXISTE" in update["errores"][0]


async def test_run_in_real_mode_repeats_three_times_and_traces_cost(repo: SqlStudyRepo) -> None:
    engine = FakeEngine(texto="Clínica Alborada Visión", coste=0.01)
    market = Market(marcas=[Brand(id="alborada", nombre="Clínica Alborada Visión", rol="foco")])
    state = merge(start(repo, "real"), {"market": market, "prompts": [prompt("P-1")]})
    update = await nodes.run(state, make_deps(kit_llm(), [engine], repo))

    assert sorted(engine.calls) == [("P-1", 1), ("P-1", 2), ("P-1", 3)]
    assert all(r.marcas_a_evaluar == ["alborada"] for r in update["runs"])
    assert [t.nodo for t in update["traces"]] == ["run:fake:ChatGPT"] * 3
    assert update["coste_acumulado_eur"] == pytest.approx(0.03)
    assert len(repo.get_traces(state["study_id"])) == 3


async def test_run_stops_when_the_budget_is_exhausted(repo: SqlStudyRepo) -> None:
    engine = FakeEngine(texto="", coste=1.0)
    market = Market(marcas=[Brand(id="alborada", nombre="Clínica Alborada Visión", rol="foco")])
    state = merge(start(repo, "real"), {"market": market, "prompts": [prompt("P-1")]})
    update = await nodes.run(state, make_deps(kit_llm(), [engine], repo, budget_max=1.5))
    assert len(update["runs"]) == 2  # la segunda cruza el límite y ya no se lanza la tercera
    assert update["coste_acumulado_eur"] == 2.0
    assert any("presupuesto agotado" in e for e in update["errores"])


async def test_run_without_engines_fails(repo: SqlStudyRepo) -> None:
    state = merge(start(repo, "real"), {"market": Market(marcas=[]), "prompts": [prompt()]})
    with pytest.raises(RuntimeError, match="no hay motores"):
        await nodes.run(state, make_deps(kit_llm(), [], repo))


# --- judge y analyze ------------------------------------------------------------------------------


async def test_judge_evaluates_market_brands_eligible_in_each_run(repo: SqlStudyRepo) -> None:
    state = await kit_state_until_judge(repo)
    judges: list[DetectionJudge] = []

    def factory(market: Market, budget: Budget) -> DetectionJudge:
        judge = DetectionJudge(market, budget)
        judges.append(judge)
        return judge

    deps = make_deps(kit_llm(), [], repo, judge_factory=factory)
    update = await nodes.judge(state, deps)

    market_ids = {b.id for b in state["market"].marcas}
    esperadas = sum(len(set(r.marcas_a_evaluar) & market_ids) for r in state["runs"])
    assert len(update["evaluations"]) == esperadas
    assert judges[0].budget is not None and judges[0].budget.study_id == state["study_id"]
    assert len(repo.get_evaluations(state["study_id"])) == esperadas
    assert [t.nodo for t in update["traces"]] == ["judge:deteccion"]
    assert update["juez"] == "deteccion"


async def test_judge_without_credentials_falls_back_to_rules(repo: SqlStudyRepo) -> None:
    state = await kit_state_until_judge(repo, n_prompts=1)

    class NoKeyJudge(DetectionJudge):
        async def aevaluate_many(self, pairs: Any) -> list[Any]:
            raise MissingCredentialError("DEEPSEEK_API_KEY", "LLMJudge")

    update = await nodes.judge(state, make_deps(kit_llm(), [], repo, judge_factory=NoKeyJudge))
    assert update["evaluations"] and all(e.origen == "fallback" for e in update["evaluations"])
    assert "DEEPSEEK_API_KEY" in update["errores"][0]
    assert update["juez"] == "reglas"


async def test_judge_can_be_forced_to_rules_even_with_keys(repo: SqlStudyRepo) -> None:
    state = await kit_state_until_judge(repo, n_prompts=2)

    def no_llm_judge(market: Market, budget: Budget) -> DetectionJudge:
        raise AssertionError("con JUDGE_PROVIDER=reglas no se construye el juez")

    settings = kit_settings(judge_provider="reglas", deepseek_api_key=SecretStr("k"))
    deps = make_deps(kit_llm(), [], repo, settings=settings, judge_factory=no_llm_judge)
    update = await nodes.judge(state, deps)

    assert update["evaluations"] and all(e.origen == "fallback" for e in update["evaluations"])
    assert update["juez"] == "reglas"
    assert update["errores"] == [] and update["traces"] == []


async def test_analyze_computes_metrics_findings_and_compares_with_previous(
    repo: SqlStudyRepo,
) -> None:
    deps = make_deps(kit_llm(), [], repo)
    primero = await kit_state_until_judge(repo, n_prompts=25)
    primero = merge(primero, await nodes.judge(primero, deps))
    update = await nodes.analyze(primero, deps)
    assert update["metrics"].study_id == primero["study_id"]
    assert update["metrics"].comparado_con is None and update["metrics_delta"] is None
    assert update["findings"]
    assert repo.get_findings(primero["study_id"]) == update["findings"]

    segundo = await kit_state_until_judge(repo, n_prompts=25)
    segundo = merge(segundo, await nodes.judge(segundo, deps))
    update = await nodes.analyze(segundo, deps)
    assert update["metrics"].comparado_con == primero["study_id"]
    assert update["metrics_delta"].comparado_con == primero["study_id"]
    assert update["metrics_delta"].score_delta == 0


# --- plan y write ---------------------------------------------------------------------------------


async def analyzed_state(repo: SqlStudyRepo) -> StudyState:
    deps = make_deps(kit_llm(), [], repo)
    state = await kit_state_until_judge(repo, n_prompts=25)
    state = merge(state, await nodes.judge(state, deps))
    return merge(state, await nodes.analyze(state, deps))


async def test_plan_is_validated_against_the_brief(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    llm = kit_llm()
    update = await nodes.plan(state, make_deps(llm, [], repo))

    assert llm.names() == ["plan.v1"]
    assert update["plan"].study_id == state["study_id"]
    assert update["plan_violaciones"] == [] and update["errores"] == []
    assert update["revision_pendiente"] == "plan"
    assert repo.get_plan(state["study_id"]) == update["plan"]
    assert repo.get_study(state["study_id"]).estado == "esperando_revision_plan"
    payload = llm.calls[0][1]
    assert payload["metricas"]["score_global"] == state["metrics"].score_global.model_dump(
        mode="json"
    )


async def test_plan_retries_once_with_the_violations(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    intentos: list[dict[str, Any]] = []

    def handler(s: dict[str, Any]) -> Any:
        intentos.append(s)
        return plan_from_findings(s, restricciones=[] if len(intentos) == 1 else None)

    llm = FakeLLM({"plan.v1": handler})
    update = await nodes.plan(state, make_deps(llm, [], repo))
    assert len(intentos) == 2
    assert any(RESTRICCIONES[0] in v for v in intentos[1]["violaciones"])
    assert update["plan_violaciones"] == [] and len(update["traces"]) == 2


async def test_plan_keeps_persistent_violations_for_the_human(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    llm = FakeLLM({"plan.v1": lambda s: plan_from_findings(s, restricciones=[])})
    update = await nodes.plan(state, make_deps(llm, [], repo))
    assert len(llm.calls) == 2
    assert update["plan_violaciones"]
    assert all(e.startswith("plan: ") for e in update["errores"])
    assert update["plan"] is not None


async def test_plan_simulates_its_impact_without_a_guard(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    update = await nodes.plan(state, make_deps(kit_llm(), [], repo))

    simulacion = update["simulacion"]
    assert simulacion.study_id == state["study_id"]
    assert simulacion.score_actual == state["metrics"].score_global.score
    assert [p.fase for p in simulacion.proyecciones] == [f.nombre for f in update["plan"].fases]
    assert update["calidad_plan"] is None
    assert [t.nodo for t in update["traces"]] == ["plan.v1"]


async def test_plan_quality_is_assessed_when_a_guard_is_available(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    guards: list[FakeGuard] = []

    def factory(budget: Budget) -> FakeGuard:
        guards.append(FakeGuard(budget, coste=0.01))
        return guards[-1]

    update = await nodes.plan(state, make_deps(kit_llm(), [], repo, plan_guard_factory=factory))

    assert guards[0].planes == [update["plan"]]
    assert update["calidad_plan"].nota == f"{len(update['plan'].acciones)} acciones evaluadas"
    assert [t.nodo for t in update["traces"]] == ["plan.v1", "plan_guard:fake"]
    assert update["coste_acumulado_eur"] == pytest.approx(state["coste_acumulado_eur"] + 0.01)
    assert "plan_guard:fake" in {t.nodo for t in repo.get_traces(state["study_id"])}


async def test_plan_guard_without_credentials_does_not_block(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    deps = make_deps(kit_llm(), [], repo, plan_guard_factory=lambda b: FakeGuard(b, sin_clave=True))
    update = await nodes.plan(state, deps)

    assert update["plan"] is not None and update["simulacion"] is not None
    assert update["calidad_plan"] is None
    assert any("TYPESAFE_API_KEY" in e and "sin evaluar" in e for e in update["errores"])


async def test_plan_guard_api_failure_does_not_block(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    caido = RuntimeError("HTTP 500 del proveedor")
    deps = make_deps(kit_llm(), [], repo, plan_guard_factory=lambda b: FakeGuard(b, error=caido))
    update = await nodes.plan(state, deps)

    assert update["plan"] is not None and update["calidad_plan"] is None
    assert any("plan_guard" in e and "HTTP 500" in e for e in update["errores"])


async def test_plan_guard_budget_exceeded_stops_the_study(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    agotado = BudgetExceeded("coste acumulado 5.1 € supera el máximo de 5.00 €")
    deps = make_deps(kit_llm(), [], repo, plan_guard_factory=lambda b: FakeGuard(b, error=agotado))
    with pytest.raises(BudgetExceeded):
        await nodes.plan(state, deps)


async def test_parse_plan_accepts_approval_or_an_edited_plan(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    state = merge(state, await nodes.plan(state, make_deps(kit_llm(), [], repo)))
    assert parse_plan({"aprobado": True}, state) == state["plan"]
    editado = state["plan"].model_dump() | {"presupuesto_estimado_eur": 1000.0, "study_id": "x"}
    plan = parse_plan(editado, state)
    assert plan.presupuesto_estimado_eur == 1000 and plan.study_id == state["study_id"]


async def test_write_overwrites_every_figure_with_the_computed_ones(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    state = merge(state, await nodes.plan(state, make_deps(kit_llm(), [], repo)))
    update = await nodes.write(state, make_deps(kit_llm(), [], repo))

    p = update["proposal"]
    assert p.study_id == state["study_id"]
    assert p.diagnostico.metrics == state["metrics"]
    assert p.competencia.ranking == state["metrics"].ranking
    assert p.hallazgos == state["findings"]
    assert p.plan == state["plan"]
    assert p.hoja_ruta.presupuesto_eur == state["plan"].presupuesto_estimado_eur
    assert p.contexto.marca == "Clínica Alborada Visión"
    assert p.contexto.datos_sinteticos and p.contexto.origen_datos == "kit"
    assert p.contexto.motores == ["ChatGPT", "Claude", "Gemini", "Perplexity"]
    assert p.contexto.limitaciones[0] == LIMITACION_KIT
    assert LIMITACION_REGLAS not in p.contexto.limitaciones
    assert repo.get_proposal(state["study_id"]) == p
    assert repo.get_study(state["study_id"]).estado == "completado"


async def test_write_declares_rule_based_evaluations(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    state = merge(state, await nodes.plan(state, make_deps(kit_llm(), [], repo)))
    state = merge(state, {"juez": "reglas"})
    update = await nodes.write(state, make_deps(kit_llm(), [], repo))

    assert update["proposal"].contexto.limitaciones[:2] == [LIMITACION_KIT, LIMITACION_REGLAS]

    # La demo sin claves mezcla etiquetas del kit y reglas: lo explica en sus supuestos, no aquí.
    demo = await nodes.write(
        merge(state, {"juez": "fixture-detection"}), make_deps(kit_llm(), [], repo)
    )
    assert LIMITACION_REGLAS not in demo["proposal"].contexto.limitaciones


async def test_write_fills_the_brief_coverage(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    state = merge(state, await nodes.plan(state, make_deps(kit_llm(), [], repo)))
    llm = kit_llm()
    update = await nodes.write(state, make_deps(llm, [], repo))

    enc = update["proposal"].encargo
    brief = state["brief"]
    assert enc.objetivos == brief.objetivos and enc.ciudades == brief.ciudades
    assert enc.restricciones == brief.restricciones
    assert [p.estado for p in enc.cobertura] == ["cubierto"] * len(enc.cobertura)
    # El redactor recibe los puntos literales; con todo cubierto no hay reintento.
    assert llm.names().count("write.v2") == 1
    puntos = llm.calls[-1][1]["puntos_brief"]
    assert {"id": "objetivo-1", "texto": brief.objetivos[0]}.items() <= puntos[0].items()
    assert not any(
        lim.startswith(PREFIJO_PENDIENTES) for lim in update["proposal"].contexto.limitaciones
    )
    assert len(update["traces"]) == 1


async def test_write_retries_once_and_declares_what_is_missing(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    state = merge(state, await nodes.plan(state, make_deps(kit_llm(), [], repo)))

    def sin_madrid(st: dict[str, Any]) -> BaseModel:
        draft = proposal_draft(st)
        cobertura = {k: v for k, v in draft.cobertura_brief.items() if k != "ciudad-1"}
        return draft.model_copy(update={"cobertura_brief": cobertura})

    llm = kit_llm()
    llm.handlers["write.v2"] = sin_madrid
    update = await nodes.write(state, make_deps(llm, [], repo))

    assert llm.names().count("write.v2") == 2
    reintento = llm.calls[-1][1]
    assert reintento["carencias_cobertura"][0].startswith("ciudad-1 · ciudad «Madrid»")
    assert "borrador_anterior" in reintento
    assert len(update["traces"]) == 2
    p = update["proposal"]
    [madrid] = p.encargo.pendientes
    assert madrid.id == "ciudad-1"
    [aviso] = [lim for lim in p.contexto.limitaciones if lim.startswith(PREFIJO_PENDIENTES)]
    assert "Madrid" in aviso


def test_fake_ports_satisfy_the_protocols() -> None:
    from posiq.ports import LLM, Engine

    llm: LLM = kit_llm()
    engine: Engine = FakeEngine()
    run: Run = engine.ask(prompt(), repeticion=1, study_id="s")
    _, trace = llm.structured(type(brief_alborada()), "intake.v1", {}, study_id="s")
    assert isinstance(trace, Trace) and run.study_id == "s"

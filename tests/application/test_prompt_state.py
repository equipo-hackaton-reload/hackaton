"""Las claves del `state` que cada nodo manda a un prompt son las de la cabecera de ese prompt.

Si un nodo manda `candidatos` y el prompt espera `marcas_candidatas`, el LLM lee la clave declarada
como ausente y trabaja sin esos datos (le pasó a `market`). Aquí se graban todas las llamadas a
`LLM.structured` de un estudio completo, del modo real de `prompts`, de los reintentos de `plan` y
`write` y de la capa LLM de exactitud, y se comparan con `load_prompt(...).state`:

- toda clave enviada está declarada;
- toda clave declarada se envía, salvo las que la cabecera describe como «Solo en el reintento».
"""

import sys
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from posiq.adapters.engines.kit import KitEngine
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application import nodes
from posiq.application.accuracy import extraer_afirmaciones_llm
from posiq.application.graph import serializer
from posiq.application.kit import load_kit
from posiq.application.runner import StudyRunner
from posiq.domain.accuracy import AfirmacionesLLM
from posiq.domain.schemas import Brand, Market, PromptInstance
from posiq.prompts import load_prompt
from tests.application.fakes import (
    KIT_DIR,
    FakeLLM,
    brief_alborada,
    kit_llm,
    make_deps,
    plan_from_findings,
    proposal_draft,
)
from tests.application.test_nodes import analyzed_state, merge, start
from tests.domain.factories import prompt

pytestmark = pytest.mark.anyio

OPCIONAL = "Solo en el reintento"
PROMPTS_USADOS = {"intake.v2", "market.v1", "prompts.v1", "plan.v2", "write.v2", "claims.v1"}

Llamada = tuple[str, dict[str, Any]]


def comprobar(llamadas: list[Llamada]) -> None:
    for tag, state in llamadas:
        name, version = tag.rsplit(".v", 1)
        spec = load_prompt(name, int(version))
        declaradas = set(spec.state)
        opcionales = {k for k, desc in spec.state.items() if desc.startswith(OPCIONAL)}
        enviadas = set(state)
        assert enviadas <= declaradas, f"{tag}: claves no declaradas {enviadas - declaradas}"
        faltan = declaradas - opcionales - enviadas
        assert not faltan, f"{tag}: el nodo no manda {faltan}"


async def test_estudio_completo_manda_las_claves_declaradas(repo: SqlStudyRepo) -> None:
    llm = kit_llm()
    deps = make_deps(llm, KitEngine.all_motors(KIT_DIR), repo)
    runner = StudyRunner({"kit": deps}, InMemorySaver(serde=serializer()), repo)
    study = runner.create("kit")
    await runner.start(study, "# Brief de Clínica Alborada Visión")
    await runner.resume(study.id, {"aprobado": True})
    await runner.resume(study.id, {"aprobado": True})
    assert runner.repo.get_study(study.id).estado == "completado", runner.fallos
    assert {tag for tag, _ in llm.calls} == {"intake.v2", "market.v1", "plan.v2", "write.v2"}
    comprobar(llm.calls)


class _PromptSet(BaseModel):
    prompts: list[PromptInstance]


async def test_prompts_en_modo_real_manda_las_claves_declaradas(
    repo: SqlStudyRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys.modules["posiq.application.nodes.prompts"], "prompt_set_schema", lambda: _PromptSet
    )
    llm = FakeLLM({"prompts.v1": lambda s: _PromptSet(prompts=[prompt("P-1")])})
    state = merge(
        start(repo, "real"),
        {
            "brief": brief_alborada(),
            "market": Market(marcas=[Brand(id="a", nombre="A", rol="foco")]),
        },
    )
    await nodes.prompts(state, make_deps(llm, [], repo))
    [(_, enviado)] = llm.calls
    assert enviado["banco_plantillas"], "el LLM necesita el banco de plantillas para instanciarlo"
    comprobar(llm.calls)


async def test_reintentos_de_plan_y_write_mandan_las_claves_declaradas(
    repo: SqlStudyRepo,
) -> None:
    state = await analyzed_state(repo)
    intentos: list[int] = []

    def plan_que_incumple(s: dict[str, Any]) -> BaseModel:
        intentos.append(1)
        return plan_from_findings(s, restricciones=[] if len(intentos) == 1 else None)

    def sin_cobertura(s: dict[str, Any]) -> BaseModel:
        draft = proposal_draft(s)
        return draft.model_copy(update={"cobertura_brief": {}})

    llm = FakeLLM({"plan.v2": plan_que_incumple, "write.v2": sin_cobertura})
    deps = make_deps(llm, [], repo)
    state = merge(state, await nodes.plan(state, deps))
    await nodes.write(state, deps)
    assert [tag for tag, _ in llm.calls] == ["plan.v2", "plan.v2", "write.v2", "write.v2"]
    assert {"plan_anterior", "violaciones"} <= set(llm.calls[1][1])
    assert {"borrador_anterior", "carencias_cobertura"} <= set(llm.calls[3][1])
    comprobar(llm.calls)


def test_claims_manda_las_claves_declaradas() -> None:
    kit = load_kit(str(KIT_DIR))
    brand = next(b for b in kit.brands if b.id == "clinica-alborada-vision")
    llm = FakeLLM({"claims.v1": lambda _: AfirmacionesLLM(afirmaciones=[])})
    runs = [r for r in kit.runs if "Alborada" in r.texto_respuesta][:2]
    extraer_afirmaciones_llm(llm, runs, brand, study_id="S", marcas=kit.brands)
    assert len(llm.calls) == 2
    comprobar(llm.calls)


def test_cubre_todos_los_prompts_que_usan_los_nodos() -> None:
    """Si un nodo pasa a usar otra versión, hay que grabarla también arriba."""
    for tag in PROMPTS_USADOS:
        name, version = tag.rsplit(".v", 1)
        assert load_prompt(name, int(version)).version_tag == tag

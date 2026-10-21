"""Nodo `diferencial` y re-medición comparable (mismo banco de prompts que el original)."""

import asyncio
import sys
import time
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from posiq.adapters.engines.kit import KitEngine
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application import nodes
from posiq.application.graph import PIPELINE, serializer
from posiq.application.runner import StudyRunner
from posiq.domain.schemas import Brand, Market
from posiq.domain.tracking import huella_banco
from tests.application.fakes import KIT_DIR, FakeLLM, brief_alborada, kit_llm, make_deps
from tests.application.test_nodes import KIT, analyzed_state, merge, start

pytestmark = pytest.mark.anyio

DIFERENCIAL = sys.modules["posiq.application.nodes.diferencial"]


def test_el_diferencial_va_entre_analyze_y_plan() -> None:
    orden = [name for name, _, _ in PIPELINE]
    assert orden[orden.index("analyze") + 1 : orden.index("plan")] == ["diferencial"]


async def test_rellena_todos_los_bloques_sin_coste(repo: SqlStudyRepo) -> None:
    state = await analyzed_state(repo)
    update = await nodes.diferencial(state, make_deps(FakeLLM({}), [], repo))
    for bloque in ("rigor", "competidores", "oportunidades_fuente", "exactitud", "mitigaciones"):
        assert bloque in update and update[bloque] is not None, bloque
    assert update["errores"] == []
    assert "traces" not in update  # sin LLM: nada que pagar
    rigor = update["rigor"]
    assert rigor.score_global.valor == state["metrics"].score_global.score
    assert set(rigor.hallazgos) == {f.id for f in state["findings"]}
    assert rigor.deltas == {}  # primera medición
    [exactitud] = update["exactitud"]
    assert exactitud.brand_id == state["metrics"].marca_foco_id


async def test_un_bloque_que_falla_queda_en_none_y_no_para(
    repo: SqlStudyRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    def falla(*_: Any) -> Any:
        raise ValueError("sin datos")

    monkeypatch.setattr(DIFERENCIAL, "brecha_competidores", falla)
    state = await analyzed_state(repo)
    update = await nodes.diferencial(state, make_deps(FakeLLM({}), [], repo))
    assert update["competidores"] is None
    assert update["rigor"] is not None
    assert update["errores"] == ["diferencial: competidores sin calcular: sin datos"]


async def test_el_calculo_no_bloquea_el_bucle_de_eventos(
    repo: SqlStudyRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El bootstrap tarda segundos: corre en un hilo y el bucle sigue atendiendo peticiones."""

    def lento(state: Any, catalogo: Any) -> dict[str, Any]:
        time.sleep(0.5)
        return {"errores": []}

    monkeypatch.setattr(DIFERENCIAL, "calcular", lento)
    state = await analyzed_state(repo)
    latidos = 0

    async def latido() -> None:
        nonlocal latidos
        while True:
            await asyncio.sleep(0.01)
            latidos += 1

    tarea = asyncio.create_task(latido())
    await nodes.diferencial(state, make_deps(FakeLLM({}), [], repo))
    tarea.cancel()
    assert latidos >= 10


async def test_prompts_reutiliza_el_banco_sembrado_en_modo_real(repo: SqlStudyRepo) -> None:
    llm = FakeLLM({})
    state = merge(
        start(repo, "real"),
        {
            "brief": brief_alborada(),
            "market": Market(marcas=[Brand(id="a", nombre="A", rol="foco")]),
            "prompts": KIT.prompts[:3],
        },
    )
    update = await nodes.prompts(state, make_deps(llm, [], repo))
    assert update == {}
    assert llm.calls == []


async def test_remedicion_siembra_el_banco_y_la_medicion_anterior(repo: SqlStudyRepo) -> None:
    deps = make_deps(kit_llm(), KitEngine.all_motors(KIT_DIR), repo)
    runner = StudyRunner({"kit": deps}, InMemorySaver(serde=serializer()), repo)
    original = runner.create("kit")
    await runner.start(original, "# Brief de Clínica Alborada Visión")
    for _ in range(2):
        await runner.resume(original.id, {"aprobado": True})
    antes, _ = await runner.state(original.id)

    nuevo = await runner.prepare_remeasure(original.id)
    sembrado, pendientes = await runner.state(nuevo.id)
    assert pendientes == ("prompts",)
    assert sembrado["prompts"] == antes["prompts"]
    anterior = sembrado["medicion_anterior"]
    assert anterior is not None and anterior["study_id"] == original.id
    assert anterior["metrics"] == antes["metrics"]

    await runner.continue_(nuevo)
    despues, _ = await runner.state(nuevo.id)
    assert huella_banco(despues["prompts"]) == huella_banco(antes["prompts"])
    rigor = despues["rigor"]
    assert rigor is not None and "score_global" in rigor.deltas
    assert rigor.deltas["score_global"].delta == 0

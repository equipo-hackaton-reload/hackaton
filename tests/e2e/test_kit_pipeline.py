"""Demo de Nivel 1 sin APIs: el grafo completo en modo kit con LLM y juez falsos.

Usa el checkpointer y el repositorio reales sobre un SQLite temporal, y reabre ambos entre las dos
revisiones para comprobar que un estudio pausado sobrevive a un reinicio del proceso.
"""

from pathlib import Path

import pytest

from posiq.adapters.engines.kit import KitEngine
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.graph import sqlite_checkpointer
from posiq.application.runner import StudyRunner
from posiq.domain.schemas import Proposal
from posiq.domain.simulation_schemas import SimulationResult
from tests.application.fakes import KIT_DIR, kit_llm, make_deps

pytestmark = pytest.mark.anyio

BRIEF = KIT_DIR.parents[1] / "01_Briefings" / "Brief_de_ejemplo_Clinica_Alborada.md"


def runner_for(repo: SqlStudyRepo, checkpointer: object) -> StudyRunner:
    deps = make_deps(kit_llm(), KitEngine.all_motors(KIT_DIR), repo)
    return StudyRunner({"kit": deps}, checkpointer, repo)  # type: ignore[arg-type]


async def test_kit_pipeline_end_to_end(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'posiq.db').as_posix()}"
    repo = SqlStudyRepo(url)

    async with sqlite_checkpointer(url) as checkpointer:
        runner = runner_for(repo, checkpointer)
        study = runner.create("kit")
        await runner.start(study, BRIEF.read_text(encoding="utf-8"))
        assert runner.fallos == {}

        values, pendientes = await runner.state(study.id)
        assert pendientes == ("review_competidores",)
        assert values["revision_pendiente"] == "competidores"
        assert repo.get_study(study.id).estado == "esperando_revision_competidores"

        market = values["market"].model_dump(mode="json")
        await runner.check_resume(study.id, "competidores", market)
        await runner.resume(study.id, market)
        assert runner.fallos == {}

        values, pendientes = await runner.state(study.id)
        assert pendientes == ("review_plan",)
        assert values["market"].confirmado_por_humano
        assert repo.get_study(study.id).estado == "esperando_revision_plan"

    # Reinicio: checkpointer y runner nuevos sobre la misma base.
    repo = SqlStudyRepo(url)
    async with sqlite_checkpointer(url) as checkpointer:
        runner = runner_for(repo, checkpointer)
        # La simulación sobrevive al reinicio como modelo, no como dict suelto.
        values, _ = await runner.state(study.id)
        assert isinstance(values["simulacion"], SimulationResult)
        assert values["simulacion"].study_id == study.id
        await runner.check_resume(study.id, "plan", {"aprobado": True})
        await runner.resume(study.id, {"aprobado": True})
        assert runner.fallos == {}

        values, pendientes = await runner.state(study.id)
        assert pendientes == ()

    proposal = values["proposal"]
    assert isinstance(proposal, Proposal)
    Proposal.model_validate(proposal.model_dump(mode="json", exclude_computed_fields=True))
    assert proposal.study_id == study.id
    assert values["revision_pendiente"] == "none"
    assert values["coste_acumulado_eur"] == 0
    assert values["errores"] == []

    # Todo persistido con el mismo study_id.
    assert repo.get_study(study.id).estado == "completado"
    assert repo.get_study(study.id).brand_id == proposal.diagnostico.metrics.marca_foco_id
    runs, evals = repo.get_runs(study.id), repo.get_evaluations(study.id)
    assert len(runs) == len(values["runs"]) == 624
    assert len(evals) == len(values["evaluations"]) > 0
    assert {r.study_id for r in runs} == {e.study_id for e in evals} == {study.id}
    stored = repo.get_metrics(study.id)
    assert stored is not None and stored[0] == values["metrics"]
    assert repo.get_findings(study.id) == values["findings"] == proposal.hallazgos
    assert repo.get_plan(study.id) == values["plan"] == proposal.plan
    assert repo.get_proposal(study.id) == proposal
    traces = repo.get_traces(study.id)
    assert traces == values["traces"]
    assert {t.study_id for t in traces} == {study.id}
    assert sum(t.coste_eur for t in traces) == 0
    assert [s.id for s in repo.list_studies(proposal.diagnostico.metrics.marca_foco_id)] == [
        study.id
    ]

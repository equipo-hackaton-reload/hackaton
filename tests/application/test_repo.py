from datetime import UTC, datetime, timedelta

import pytest

from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.deps import new_study
from posiq.domain.schemas import Finding, Metrics, ScoreBreakdown, Study
from tests.application.fakes import brief_alborada, plan_from_findings, trace
from tests.domain.factories import evaluation, run


def study(sid: str, brand_id: str = "alborada", dias: int = 0) -> Study:
    return new_study("kit", study_id=sid).model_copy(
        update={
            "brand_id": brand_id,
            "brief": brief_alborada(),
            "creado_en": datetime(2026, 10, 1, tzinfo=UTC) + timedelta(days=dias),
        }
    )


def finding(id: str, study_id: str) -> Finding:
    return Finding(
        id=id,
        study_id=study_id,
        titulo="Caída en comparación",
        descripcion="La marca desaparece al comparar.",
        impacto="L",
        confianza=0.8,
        cifra=0.3,
        origen_cifra="visibilidad.fase",
        evaluation_ids=["EJ-1:alborada"],
    )


def metrics(sid: str, foco: str = "alborada") -> Metrics:
    score = ScoreBreakdown(brand_id=foco, n_evaluaciones=0, score_version="1.0")
    return Metrics(
        study_id=sid,
        score_version="1.0",
        marca_foco_id=foco,
        lider_id=None,
        score_global=score,
        scores=[score],
        scores_por_motor=[],
        ranking=[foco],
        visibilidad=[],
        calidad_menciones=[],
        top_fuentes=[],
        brecha_fuentes=[],
        n_ejecuciones={"total": 0},
    )


def test_study_roundtrip_and_update(repo: SqlStudyRepo) -> None:
    s = study("s1")
    repo.save_study(s)
    repo.save_study(s.model_copy(update={"estado": "completado"}))
    assert repo.get_study("s1") == s.model_copy(update={"estado": "completado"})
    with pytest.raises(KeyError):
        repo.get_study("no-existe")


def test_evaluation_ids_are_only_unique_within_a_study(repo: SqlStudyRepo) -> None:
    for sid in ("s1", "s2"):
        repo.save_study(study(sid))
        repo.save_runs(sid, [run("EJ-1", study_id=sid)])
        repo.save_evaluations(sid, [evaluation(study_id=sid)])
    assert [e.study_id for e in repo.get_evaluations("s1")] == ["s1"]
    assert [e.study_id for e in repo.get_evaluations("s2")] == ["s2"]
    assert repo.get_evaluations("s1")[0].id == repo.get_evaluations("s2")[0].id


def test_saves_are_idempotent(repo: SqlStudyRepo) -> None:
    repo.save_study(study("s1"))
    r = run("EJ-1", study_id="s1")
    repo.save_runs("s1", [r])
    repo.save_runs("s1", [r])
    repo.save_traces("s1", [trace("s1", "a"), trace("s1", "b")])
    repo.save_traces("s1", [trace("s1", "a"), trace("s1", "b"), trace("s1", "c")])
    assert len(repo.get_runs("s1")) == 1
    assert [t.nodo for t in repo.get_traces("s1")] == ["a", "b", "c"]


def test_rejects_results_of_another_study(repo: SqlStudyRepo) -> None:
    with pytest.raises(ValueError, match="otros estudios"):
        repo.save_runs("s1", [run("EJ-1", study_id="s2")])


def test_findings_plan_and_metrics(repo: SqlStudyRepo) -> None:
    repo.save_study(study("s1"))
    repo.save_findings("s1", [finding("F1", study_id="s1"), finding("F2", study_id="s1")])
    repo.save_findings("s1", [finding("F3", study_id="s1")])
    assert [f.id for f in repo.get_findings("s1")] == ["F3"]

    state = {
        "hallazgos": [f.model_dump(mode="json") for f in repo.get_findings("s1")],
        "brief": brief_alborada().model_dump(mode="json"),
    }
    plan = plan_from_findings(state).model_copy(update={"study_id": "s1"})
    repo.save_plan("s1", plan)
    assert repo.get_plan("s1") == plan

    repo.save_metrics("s1", metrics("s1"))
    assert repo.get_metrics("s1") == (metrics("s1"), None)


def test_list_and_latest_metrics(repo: SqlStudyRepo) -> None:
    repo.save_study(study("viejo", dias=0))
    repo.save_study(study("nuevo", dias=10))
    repo.save_study(study("otra-marca", brand_id="nitida", dias=5))
    repo.save_metrics("viejo", metrics("viejo"))
    repo.save_metrics("nuevo", metrics("nuevo"))

    assert [s.id for s in repo.list_studies()] == ["nuevo", "otra-marca", "viejo"]
    assert [s.id for s in repo.list_studies("alborada")] == ["nuevo", "viejo"]

    latest = repo.latest_metrics("alborada")
    assert latest is not None and latest.study_id == "nuevo"
    antes = repo.latest_metrics("alborada", before=repo.get_study("nuevo").creado_en)
    assert antes is not None and antes.study_id == "viejo"
    assert repo.latest_metrics("alborada", before=datetime(2020, 1, 1, tzinfo=UTC)) is None
    assert repo.latest_metrics("nitida") is None

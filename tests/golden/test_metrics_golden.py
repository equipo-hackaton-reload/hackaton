"""Métricas y hallazgos sobre las 624 ejecuciones del kit (etiquetas humanas donde existen)."""

import pytest

from posiq.domain.findings import detect_findings
from posiq.domain.metrics import compute_metrics
from posiq.domain.schemas import BriefSummary, Metrics
from tests.golden.conftest import Kit


@pytest.fixture(scope="module")
def metrics(kit: Kit, alborada_brief: BriefSummary) -> Metrics:
    return compute_metrics(
        alborada_brief, kit.market, kit.prompts, kit.runs, kit.evaluations(), kit.sources
    )


def test_cobertura(kit: Kit, metrics: Metrics) -> None:
    assert len(kit.evaluations()) == 2928
    assert metrics.n_ejecuciones["total"] == 624
    assert metrics.n_ejecuciones["evaluaciones"] == 2928
    assert metrics.n_ejecuciones["espontaneo"] + metrics.n_ejecuciones["asistido"] == 624


def test_score_de_la_marca_foco(metrics: Metrics) -> None:
    s = metrics.score_global
    assert s.brand_id == "clinica-alborada-vision"
    assert s.score is not None and 0 <= s.score <= 100
    assert all(x.score is not None and 0 <= x.score <= 100 for x in metrics.scores)
    assert metrics.ranking[0] == metrics.lider_id == "grupo-hospitalario-valdecruz"


def test_espontaneo_distinto_de_asistido(metrics: Metrics) -> None:
    esp = metrics.cell("clinica-alborada-vision", "espontaneo", "global", "global")
    asi = metrics.cell("clinica-alborada-vision", "asistido", "global", "global")
    assert esp and asi and esp.tasa is not None and asi.tasa is not None
    assert esp.tasa != asi.tasa


def test_hallazgos_con_evidencia_real(
    kit: Kit, metrics: Metrics, alborada_brief: BriefSummary
) -> None:
    findings = detect_findings(metrics, alborada_brief)
    assert 3 <= len(findings) <= 7
    ids = {e.id for e in kit.evaluations()}
    for f in findings:
        assert f.evaluation_ids and set(f.evaluation_ids) <= ids
        assert f.origen_cifra
    assert any(f.id == "F-ciudad-barcelona" for f in findings)

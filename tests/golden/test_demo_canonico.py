"""Cifras canónicas de la demo de Alborada: las que van a la deck y a `docs/plan-b.md`.

La canónica sale de las etiquetas del kit (`kit.evaluations()`), la verdad de referencia del reto.
La API en modo fixture usa el juez por reglas (`evaluation_from_detection`): misma aparición,
posición y ranking, pero no clasifica el tipo de fuente ni gradúa la fuerza, así que da 25,87. Con
un decimal las dos coinciden en 25,9.
"""

import pytest

from posiq.domain.detection import detect_in_run, evaluation_from_detection
from posiq.domain.metrics import compute_metrics
from posiq.domain.schemas import BriefSummary, Evaluation, Finding, Metrics, Plan
from posiq.domain.simulation import simulate_plan
from tests.golden.conftest import STUDY_ID, Kit

FOCO = "clinica-alborada-vision"
SCORE_CANONICO = 25.93
SCORE_JUEZ_POR_REGLAS = 25.87


@pytest.fixture(scope="module")
def metrics_reglas(kit: Kit, alborada_brief: BriefSummary) -> Metrics:
    marcas = {b.id: b for b in kit.market.marcas}
    evaluations: list[Evaluation] = []
    for run in kit.runs:
        detecciones = detect_in_run(run, kit.market.marcas)
        evaluations += [
            evaluation_from_detection(run, marcas[b], detecciones.get(b))
            for b in run.marcas_a_evaluar
            if b in marcas
        ]
    return compute_metrics(
        alborada_brief,
        kit.market,
        kit.prompts,
        kit.runs,
        evaluations,
        kit.sources,
        study_id=STUDY_ID,
    )


def test_score_canonico(metrics_alborada: Metrics) -> None:
    s = metrics_alborada.score_global
    assert s.brand_id == FOCO
    assert s.n_evaluaciones == 240
    assert s.score == SCORE_CANONICO
    assert (s.aparicion, s.posicion, s.fuerza, s.calidad_fuente) == (11.62, 4.72, 3.92, 5.67)


def test_posicion_8_de_10(metrics_alborada: Metrics) -> None:
    assert len(metrics_alborada.ranking) == 10
    assert metrics_alborada.ranking.index(FOCO) + 1 == 8


def test_juez_por_reglas_solo_cambia_fuerza_y_fuente(
    metrics_alborada: Metrics, metrics_reglas: Metrics
) -> None:
    kit_s, reglas_s = metrics_alborada.score_global, metrics_reglas.score_global
    assert reglas_s.score == SCORE_JUEZ_POR_REGLAS
    assert (reglas_s.aparicion, reglas_s.posicion) == (kit_s.aparicion, kit_s.posicion)
    assert (reglas_s.fuerza, reglas_s.calidad_fuente) == (3.88, 5.65)
    assert metrics_reglas.ranking == metrics_alborada.ranking
    assert round(SCORE_JUEZ_POR_REGLAS, 1) == round(SCORE_CANONICO, 1) == 25.9


def test_proyeccion_del_plan(
    metrics_alborada: Metrics, findings_alborada: list[Finding], plan_alborada: Plan
) -> None:
    sim = simulate_plan(plan_alborada, metrics_alborada, findings_alborada)
    assert sim.score_actual == SCORE_CANONICO
    final = sim.proyecciones[-1].score
    assert (round(final.minimo, 1), round(final.esperado, 1), round(final.maximo, 1)) == (
        27.8,
        30.8,
        34.0,
    )

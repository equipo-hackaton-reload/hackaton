"""Preajustes de escenario sobre el plan de ejemplo de Alborada (ADR 0009).

Hallazgos del kit: L = F-motor-debil, F-ciudad-barcelona, F-brecha-lider; M = los otros cuatro.
Esfuerzo del plan completo: 16 puntos (S = 1, M = 2, L = 3).
"""

import pytest

from posiq.domain.scenario_schemas import EntradaEscenario, EscenarioPlan
from posiq.domain.scenarios import build_presets, build_scenario
from posiq.domain.schemas import Finding, Metrics, Plan
from posiq.domain.simulation import simulate_plan
from tests.golden.test_demo_canonico import SCORE_CANONICO

TODAS = ["A0-1", "A0-2", "A1-1", "A1-2", "A2-1", "A2-2", "A2-3", "A3-1", "A3-2"]


@pytest.fixture(scope="module")
def presets(
    alborada_study: tuple[Metrics, list[Finding], Plan],
) -> dict[str, EscenarioPlan]:
    metrics, findings, plan = alborada_study
    return {e.nombre: e for e in build_presets(plan, findings, metrics)}


def final(e: EscenarioPlan) -> tuple[float, float, float]:
    assert e.simulacion is not None and e.simulacion.score_actual == SCORE_CANONICO
    s = e.simulacion.proyecciones[-1].score
    return s.minimo, s.esperado, s.maximo


def test_minimo_viable(presets: dict[str, EscenarioPlan]) -> None:
    e = presets["minimo_viable"]
    # Cubre los 3 hallazgos L con 4 puntos: A0-2 (motor débil), A1-2 (Barcelona), A0-1 (brecha).
    assert e.mantenidas == ["A0-1", "A0-2", "A1-2"]
    assert e.esfuerzo_total == 4
    assert {a.action_id: a.motivo for a in e.aplazadas} == dict.fromkeys(
        ["A1-1", "A2-1", "A2-2", "A2-3", "A3-1", "A3-2"], "desactivada"
    )
    assert e.hallazgos_sin_cubrir == [
        "F-caida-embudo",
        "F-asistida-vs-espontanea",
        "F-recomendacion-debil",
    ]
    assert final(e) == (26.36, 27.17, 28.04)


def test_equilibrado(presets: dict[str, EscenarioPlan]) -> None:
    e = presets["equilibrado"]
    # Cubre los 7 hallazgos (todos L o M) con 7 puntos; A1-1 arrastra su dependencia A0-2.
    assert e.mantenidas == ["A0-2", "A1-1", "A1-2", "A2-3"]
    assert e.esfuerzo_total == 7
    assert {a.action_id: a.motivo for a in e.aplazadas} == dict.fromkeys(
        ["A0-1", "A2-1", "A2-2", "A3-1", "A3-2"], "desactivada"
    )
    assert e.hallazgos_sin_cubrir == []
    assert final(e) == (26.83, 28.2, 29.78)


def test_completo_reproduce_la_simulacion_canonica(
    presets: dict[str, EscenarioPlan], alborada_study: tuple[Metrics, list[Finding], Plan]
) -> None:
    metrics, findings, plan = alborada_study
    e = presets["completo"]
    assert e.mantenidas == TODAS and e.aplazadas == []
    assert e.esfuerzo_total == 16 and e.hallazgos_sin_cubrir == []
    assert e.coste_declarado_eur is None and e.intervalo is None
    assert e.simulacion == simulate_plan(plan, metrics, findings)
    assert final(e) == (27.77, 30.77, 33.95)
    assert round(final(e)[1], 1) == 30.8


def test_los_preajustes_crecen_en_esfuerzo_y_score(presets: dict[str, EscenarioPlan]) -> None:
    orden = [presets[n] for n in ("minimo_viable", "equilibrado", "completo")]
    assert [e.esfuerzo_total for e in orden] == sorted(e.esfuerzo_total for e in orden)
    assert [final(e)[1] for e in orden] == sorted(final(e)[1] for e in orden)


def test_desactivar_a0_2_aplaza_en_cascada(
    alborada_study: tuple[Metrics, list[Finding], Plan],
) -> None:
    metrics, findings, plan = alborada_study
    activas = [a for a in TODAS if a != "A0-2"]
    e = build_scenario(plan, findings, metrics, EntradaEscenario(acciones_activas=activas))
    assert {a.action_id: a.motivo for a in e.aplazadas} == {
        "A0-2": "desactivada",
        "A1-1": "dependencia",
        "A2-1": "dependencia",
    }
    assert e.hallazgos_sin_cubrir == ["F-caida-embudo", "F-fuente-lider", "F-recomendacion-debil"]

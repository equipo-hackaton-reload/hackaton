"""Escenarios del plan: motivos de aplazamiento, dependencias, presupuesto y preajustes."""

import random

import pytest

from posiq.domain.scenario_schemas import EntradaEscenario, EscenarioPlan
from posiq.domain.scenarios import (
    build_preset,
    build_presets,
    build_scenario,
    minimal_cover,
)
from posiq.domain.schemas import Action, Finding, Phase, Plan
from posiq.domain.simulation import simulate_plan
from tests.domain.factories import action
from tests.domain.test_simulation import metrics


def finding(id: str, impacto: str = "M") -> Finding:
    return Finding.model_validate(
        {
            "id": id,
            "study_id": "S-1",
            "titulo": id,
            "descripcion": id,
            "impacto": impacto,
            "confianza": 1.0,
            "cifra": 0.1,
            "origen_cifra": "test",
            "evaluation_ids": ["EJ-1:alborada"],
        }
    )


def plan(*fases: list[Action]) -> Plan:
    return Plan(
        study_id="S-1",
        objetivos=[],
        fases=[
            Phase(nombre=f"Fase {i}", semanas=4, objetivo="x", acciones=list(acciones))
            for i, acciones in enumerate(fases)
        ],
        presupuesto_estimado_eur=0,
        respeta_restricciones=True,
    )


FINDINGS = [finding("F1", "L"), finding("F2", "M"), finding("F3", "S")]


def run(p: Plan, **entrada: object) -> EscenarioPlan:
    return build_scenario(p, FINDINGS, metrics(), EntradaEscenario.model_validate(entrada))


def motivos(e: EscenarioPlan) -> dict[str, str]:
    return {a.action_id: a.motivo for a in e.aplazadas}


# --- Entrada vacía y simulación ---------------------------------------------------------------


def test_sin_restricciones_mantiene_todo_y_reproduce_la_simulacion() -> None:
    p = plan(
        [action("A", ["F1"], esfuerzo="M"), action("B", ["F2"], dependencias=["A"])],
        [action("C", ["F3"], esfuerzo="L")],
    )
    e = run(p)
    assert e.nombre == "personalizado"
    assert e.mantenidas == ["A", "B", "C"] and e.aplazadas == []
    assert e.esfuerzo_total == 2 + 1 + 3
    assert e.hallazgos_sin_cubrir == []
    assert e.coste_declarado_eur is None and e.intervalo is None
    assert e.simulacion == simulate_plan(p, metrics(), FINDINGS)


def test_la_simulacion_usa_solo_las_mantenidas_y_conserva_las_fases() -> None:
    p = plan([action("A", ["F1"])], [action("B", ["F2"])])
    e = run(p, acciones_activas=["A"])
    assert e.simulacion is not None
    assert [x.fase for x in e.simulacion.proyecciones] == ["Fase 0", "Fase 1"]
    assert e.simulacion.proyecciones[-1].acciones == ["A"]
    assert e.simulacion == simulate_plan(plan([action("A", ["F1"])], []), metrics(), FINDINGS)


def test_ids_desconocidos_lanzan_error() -> None:
    p = plan([action("A", ["F1"])])
    with pytest.raises(ValueError, match="no están en el plan"):
        run(p, acciones_activas=["A", "Z"])
    with pytest.raises(ValueError, match="no están en el plan"):
        run(p, costes_declarados={"Z": 100})


# --- Dependencias -----------------------------------------------------------------------------


def test_dependencias_en_cascada() -> None:
    p = plan(
        [action("A", ["F1"]), action("B", ["F2"], dependencias=["A"])],
        [action("C", ["F3"], dependencias=["B"]), action("D", ["F3"])],
    )
    e = run(p, acciones_activas=["B", "C", "D"])
    assert e.mantenidas == ["D"]
    assert motivos(e) == {"A": "desactivada", "B": "dependencia", "C": "dependencia"}
    detalles = {a.action_id: a.detalle for a in e.aplazadas}
    assert "A (aplazada: desactivada)" in detalles["B"]
    assert "B (aplazada: dependencia)" in detalles["C"]
    assert e.hallazgos_sin_cubrir == ["F1", "F2"]


def test_dependencia_posterior_en_el_plan_se_decide_antes() -> None:
    # B depende de C, que va después en el plan: el orden topológico decide C primero.
    p = plan([action("B", ["F1"], dependencias=["C"])], [action("C", ["F2"])])
    assert run(p).mantenidas == ["B", "C"]
    e = run(p, capacidad=1)
    assert e.mantenidas == ["C"]
    assert motivos(e) == {"B": "capacidad"}


def test_ciclo_de_dependencias_se_aplaza() -> None:
    p = plan(
        [action("A", ["F1"], dependencias=["B"]), action("B", ["F2"], dependencias=["A"])],
        [action("C", ["F3"], dependencias=["A"]), action("D", ["F3"])],
    )
    e = run(p)
    assert e.mantenidas == ["D"]
    assert motivos(e) == {"A": "dependencia", "B": "dependencia", "C": "dependencia"}
    assert "ciclo" in e.aplazadas[0].detalle


def test_dependencias_fuera_del_plan_se_ignoran() -> None:
    p = plan([action("A", ["F1"], dependencias=["NO-EXISTE"])])
    assert run(p).mantenidas == ["A"]


# --- Presupuesto ------------------------------------------------------------------------------


def test_presupuesto_solo_con_costes_declarados() -> None:
    p = plan([action("A", ["F1"]), action("B", ["F2"]), action("C", ["F3"])])
    e = run(p, presupuesto_eur=1000, costes_declarados={"A": 800, "B": 500})
    # C no tiene coste declarado: se mantiene y no consume presupuesto.
    assert e.mantenidas == ["A", "C"]
    assert motivos(e) == {"B": "fuera_de_presupuesto"}
    assert e.aplazadas[0].detalle == "coste declarado 500 €; quedan 200 € de 1.000 €"
    assert e.coste_declarado_eur == 800


def test_sin_costes_declarados_el_presupuesto_no_aplaza_nada() -> None:
    p = plan([action("A", ["F1"], esfuerzo="L"), action("B", ["F2"])])
    e = run(p, presupuesto_eur=0)
    assert e.mantenidas == ["A", "B"] and e.coste_declarado_eur is None


def test_coste_declarado_sin_presupuesto_solo_se_suma() -> None:
    p = plan([action("A", ["F1"]), action("B", ["F2"])])
    e = run(p, costes_declarados={"B": 1500.5})
    assert e.mantenidas == ["A", "B"] and e.coste_declarado_eur == 1500.5


def test_coste_de_una_aplazada_no_cuenta() -> None:
    p = plan([action("A", ["F1"]), action("B", ["F2"])])
    e = run(p, acciones_activas=["A"], costes_declarados={"A": 100, "B": 900})
    assert e.coste_declarado_eur == 100


def test_presupuesto_justo_con_decimales_cabe() -> None:
    p = plan([action("A", ["F1"]), action("B", ["F2"])])
    e = run(p, presupuesto_eur=0.3, costes_declarados={"A": 0.1, "B": 0.2})
    assert e.mantenidas == ["A", "B"]


def test_ids_repetidos_en_el_plan_lanzan_error() -> None:
    with pytest.raises(ValueError, match="repetidos"):
        run(plan([action("A", ["F1"])], [action("A", ["F2"])]))


# --- Capacidad y prioridad --------------------------------------------------------------------


def test_capacidad_voraz_en_orden_del_plan() -> None:
    p = plan(
        [action("A", ["F1"], esfuerzo="M"), action("B", ["F2"], esfuerzo="L")],
        [action("C", ["F3"], esfuerzo="S")],
    )
    e = run(p, capacidad=3)
    # B (3 puntos) no cabe tras A (2); C (1) sí cabe después.
    assert e.mantenidas == ["A", "C"] and e.esfuerzo_total == 3
    assert motivos(e) == {"B": "capacidad"}
    assert e.aplazadas[0].detalle == "esfuerzo L (3 puntos); quedan 1 de 3 puntos"


def test_fuera_de_prioridad() -> None:
    p = plan([action("A", ["F1"], palanca="contenido"), action("B", ["F2"], palanca="tecnico")])
    e = run(p, prioridad=["contenido"])
    assert e.mantenidas == ["A"] and motivos(e) == {"B": "fuera_de_prioridad"}
    assert "«tecnico»" in e.aplazadas[0].detalle


@pytest.mark.parametrize(
    ("activas", "motivo"),
    [(["A"], "desactivada"), (["B"], "dependencia")],
)
def test_precedencia_desactivada_y_dependencia(activas: list[str], motivo: str) -> None:
    # B depende de A, su palanca no es prioritaria, cuesta más que el presupuesto y no cabe.
    p = plan(
        [
            action("A", ["F1"], palanca="tecnico"),
            action("B", ["F2"], palanca="tecnico", esfuerzo="L", dependencias=["A"]),
        ]
    )
    e = run(
        p,
        acciones_activas=activas,
        prioridad=["contenido"],
        presupuesto_eur=0,
        costes_declarados={"B": 10},
        capacidad=0,
    )
    assert motivos(e)["B"] == motivo


def test_precedencia_prioridad_presupuesto_capacidad() -> None:
    p = plan([action("B", ["F1"], palanca="tecnico", esfuerzo="L")])
    todo: dict[str, object] = {
        "prioridad": ["contenido"],
        "presupuesto_eur": 0,
        "costes_declarados": {"B": 10},
        "capacidad": 0,
    }
    assert motivos(run(p, **todo))["B"] == "fuera_de_prioridad"
    todo.pop("prioridad")
    assert motivos(run(p, **todo))["B"] == "fuera_de_presupuesto"
    todo.pop("presupuesto_eur")
    assert motivos(run(p, **todo))["B"] == "capacidad"
    todo.pop("capacidad")
    assert run(p, **todo).mantenidas == ["B"]


# --- Preajustes -------------------------------------------------------------------------------


def preset_plan() -> tuple[Plan, list[Finding]]:
    findings = [finding("L1", "L"), finding("L2", "L"), finding("M1", "M"), finding("S1", "S")]
    p = plan(
        [
            action("BASE", ["L1"], esfuerzo="M"),
            action("BARATA", ["L2"], esfuerzo="S", dependencias=["BASE"]),
        ],
        [
            action("GRANDE", ["L1", "L2", "M1"], esfuerzo="L"),
            action("M", ["M1"], esfuerzo="S"),
            action("S", ["S1"], esfuerzo="S"),
        ],
    )
    return p, findings


def test_minimal_cover_incluye_dependencias_y_minimiza_esfuerzo() -> None:
    p, _ = preset_plan()
    # BASE + BARATA = 3 puntos empata con GRANDE (3); gana la de menos acciones.
    assert minimal_cover(p, ["L1", "L2"]) == ["GRANDE"]
    # BARATA sola no basta: arrastra a BASE.
    sin_grande = plan(p.fases[0].acciones)
    assert minimal_cover(sin_grande, ["L2"]) == ["BASE", "BARATA"]
    assert minimal_cover(p, ["L1", "L2", "M1", "S1"]) == ["GRANDE", "S"]
    assert minimal_cover(p, []) == []
    assert minimal_cover(p, ["NO-CUBRIBLE"]) == []


def test_minimal_cover_desempata_por_orden_del_plan() -> None:
    p = plan([action("X", ["F1"]), action("Y", ["F1"])])
    assert minimal_cover(p, ["F1"]) == ["X"]


def test_minimal_cover_evita_acciones_en_ciclo() -> None:
    p = plan(
        [action("A", ["F1"], dependencias=["B"]), action("B", ["F2"], dependencias=["A"])],
        [action("C", ["F1"], esfuerzo="L")],
    )
    assert minimal_cover(p, ["F1", "F2"]) == ["C"]


def test_minimal_cover_la_medicion_no_cubre_pero_entra_como_dependencia() -> None:
    p = plan(
        [action("MED", ["F1", "F2"], palanca="medicion")],
        [
            action("X", ["F2"], esfuerzo="M", dependencias=["MED"]),
            action("Y", ["F2"], esfuerzo="L"),
        ],
    )
    # F1 solo lo enlaza la medición: se ignora. F2 lo cubre X con su dependencia MED (2 + 1 = 3)
    # o Y (3): empatan en esfuerzo y gana Y por tener menos acciones.
    assert minimal_cover(p, ["F1", "F2"]) == ["Y"]
    sin_y = plan(p.fases[0].acciones, [p.fases[1].acciones[0]])
    assert minimal_cover(sin_y, ["F1", "F2"]) == ["MED", "X"]
    assert minimal_cover(sin_y, ["F1"]) == []


def test_preajuste_la_medicion_no_cuenta_como_cobertura() -> None:
    findings = [finding("F1", "L"), finding("F2", "L")]
    p = plan(
        [action("MED", ["F1", "F2"], palanca="medicion")],
        [action("X", ["F2"], dependencias=["MED"])],
    )
    e = build_preset("minimo_viable", p, findings, metrics())
    # MED se mantiene porque X depende de ella, pero F1 sigue sin cubrir.
    assert e.mantenidas == ["MED", "X"] and e.hallazgos_sin_cubrir == ["F1"]
    completo = build_preset("completo", p, findings, metrics())
    assert completo.hallazgos_sin_cubrir == ["F1"]
    # Con entrada del consultor rige la cobertura del contrato: la medición sí cubre.
    assert build_scenario(p, findings, metrics(), EntradaEscenario()).hallazgos_sin_cubrir == []


def test_preajustes() -> None:
    p, findings = preset_plan()
    minimo, equilibrado, completo = build_presets(p, findings, metrics())
    assert [e.nombre for e in (minimo, equilibrado, completo)] == [
        "minimo_viable",
        "equilibrado",
        "completo",
    ]
    assert minimo.mantenidas == ["GRANDE"] and minimo.esfuerzo_total == 3
    assert minimo.hallazgos_sin_cubrir == ["S1"]
    assert {a.motivo for a in minimo.aplazadas} == {"desactivada"}
    assert "mínimo viable" in minimo.aplazadas[0].detalle
    assert equilibrado.mantenidas == ["GRANDE"] and equilibrado.hallazgos_sin_cubrir == ["S1"]
    assert completo.mantenidas == ["BASE", "BARATA", "GRANDE", "M", "S"]
    assert completo.aplazadas == [] and completo.entrada == EntradaEscenario()
    assert completo.simulacion == simulate_plan(p, metrics(), findings)


def test_minimo_viable_sin_hallazgos_l_usa_el_siguiente_nivel() -> None:
    findings = [finding("M1", "M"), finding("S1", "S")]
    p = plan([action("A", ["M1"]), action("B", ["S1"])])
    e = build_preset("minimo_viable", p, findings, metrics())
    assert e.mantenidas == ["A"] and e.hallazgos_sin_cubrir == ["S1"]
    assert "impacto M" in e.aplazadas[0].detalle


def test_preajustes_deterministas() -> None:
    p, findings = preset_plan()
    primera = build_presets(p, findings, metrics())
    for semilla in range(5):
        barajados = findings[:]
        random.Random(semilla).shuffle(barajados)
        otra = build_presets(p, barajados, metrics())
        for a, b in zip(primera, otra, strict=True):
            assert (a.mantenidas, a.aplazadas, a.esfuerzo_total) == (
                b.mantenidas,
                b.aplazadas,
                b.esfuerzo_total,
            )
            assert sorted(a.hallazgos_sin_cubrir) == sorted(b.hallazgos_sin_cubrir)
    assert build_presets(p, findings, metrics()) == primera

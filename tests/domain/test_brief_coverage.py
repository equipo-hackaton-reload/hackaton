from posiq.domain.brief_coverage import (
    carencias,
    evaluar_cobertura,
    puntos_del_brief,
    texto_presupuesto,
)
from posiq.domain.schemas import Finding, Phase, Plan
from tests.domain.factories import action, brief

RESTRICCION = "No prometer resultados"


def _finding(id: str) -> Finding:
    return Finding(
        id=id,
        study_id="S-1",
        titulo="t",
        descripcion="d",
        impacto="M",
        confianza=0.6,
        cifra=0.1,
        origen_cifra="visibilidad",
        evaluation_ids=["EJ-1:alborada"],
    )


def _plan(
    revisadas: tuple[list[str], ...] = ([RESTRICCION], [RESTRICCION]),
    presupuesto: float = 20000,
    respeta: bool = True,
) -> Plan:
    acciones = [
        action(id=f"A{i}", finding_ids=["F1"], restricciones_revisadas=r)
        for i, r in enumerate(revisadas, start=1)
    ]
    return Plan(
        study_id="S-1",
        objetivos=[],
        fases=[Phase(nombre="Fase 0", semanas=4, objetivo="o", acciones=acciones)],
        presupuesto_estimado_eur=presupuesto,
        respeta_restricciones=respeta,
    )


def _todo_enlazado() -> dict[str, list[str]]:
    return {p.id: ["A1"] for p in puntos_del_brief(brief()) if p.tipo not in ("restriccion",)}


def test_puntos_literales_con_ids_estables() -> None:
    puntos = puntos_del_brief(brief())
    assert [p.id for p in puntos] == [
        "objetivo-1",
        "restriccion-1",
        "servicio-1",
        "servicio-2",
        "ciudad-1",
        "ciudad-2",
        "publico-1",
        "competidor-1",
        "competidor-2",
        "presupuesto",
    ]
    assert {p.estado for p in puntos} == {"pendiente"}
    assert puntos[2].texto == "Cirugía refractiva"
    assert puntos[-1].texto == "18.000–27.000 € al año"


def test_sin_presupuesto_no_hay_punto() -> None:
    assert "presupuesto" not in {p.id for p in puntos_del_brief(brief(presupuesto_anual_eur=None))}


def test_texto_presupuesto() -> None:
    assert texto_presupuesto((20000, 20000)) == "20.000 € al año"


def test_encargo_copia_el_brief_tal_cual() -> None:
    b = brief()
    encargo = evaluar_cobertura(b, _plan(), [_finding("F1")])
    assert encargo.objetivos == b.objetivos
    assert encargo.restricciones == b.restricciones
    assert encargo.servicios_prioritarios == b.servicios_prioritarios
    assert encargo.ciudades == b.ciudades
    assert encargo.publicos == b.publicos
    assert encargo.competidores_declarados == b.competidores_declarados
    assert encargo.presupuesto_anual_eur == (18000, 27000)


def test_sin_enlaces_solo_restricciones_y_presupuesto_cubiertos() -> None:
    encargo = evaluar_cobertura(brief(), _plan(), [_finding("F1")])
    cubiertos = {p.id for p in encargo.cobertura if p.estado == "cubierto"}
    assert cubiertos == {"restriccion-1", "presupuesto"}
    assert len(carencias(encargo)) == 8
    assert "ciudad-1 · ciudad «Madrid»" in carencias(encargo)[3]


def test_enlaces_a_acciones_y_hallazgos() -> None:
    enlaces = _todo_enlazado() | {"ciudad-2": ["F1", "A2", "A2"], "objetivo-1": ["F1"]}
    encargo = evaluar_cobertura(brief(), _plan(), [_finding("F1")], enlaces)
    assert carencias(encargo) == []
    barcelona = next(p for p in encargo.cobertura if p.id == "ciudad-2")
    assert (barcelona.accion_ids, barcelona.hallazgo_ids) == (["A2"], ["F1"])


def test_ids_inexistentes_se_descartan() -> None:
    enlaces = _todo_enlazado() | {"ciudad-1": ["A9", "F9"]}
    encargo = evaluar_cobertura(brief(), _plan(), [_finding("F1")], enlaces)
    [madrid] = encargo.pendientes
    assert madrid.id == "ciudad-1" and madrid.accion_ids == [] and madrid.hallazgo_ids == []
    assert "A9, F9" in madrid.motivo
    # Un id inexistente junto a uno válido no impide la cobertura.
    enlaces["ciudad-1"] = ["A9", "A1"]
    madrid = evaluar_cobertura(brief(), _plan(), [], enlaces).cobertura[4]
    assert madrid.estado == "cubierto" and madrid.accion_ids == ["A1"]
    assert "A9" in madrid.motivo


def test_enlaces_a_puntos_desconocidos_se_ignoran() -> None:
    encargo = evaluar_cobertura(brief(), _plan(), [], _todo_enlazado() | {"ciudad-9": ["A1"]})
    assert carencias(encargo) == []


def test_restriccion_exige_todas_las_acciones() -> None:
    plan = _plan(revisadas=([RESTRICCION], []))
    # Los enlaces del redactor no cuentan en las restricciones: la prueba es el plan.
    encargo = evaluar_cobertura(brief(), plan, [], _todo_enlazado() | {"restriccion-1": ["A1"]})
    [punto] = encargo.pendientes
    assert punto.id == "restriccion-1"
    assert punto.accion_ids == ["A1"]
    assert "A2" in punto.motivo


def test_restriccion_con_plan_que_no_respeta_o_vacio() -> None:
    no_respeta = evaluar_cobertura(brief(), _plan(respeta=False), [], _todo_enlazado())
    assert [p.id for p in no_respeta.pendientes] == ["restriccion-1"]
    vacio = Plan(
        study_id="S-1",
        objetivos=[],
        fases=[],
        presupuesto_estimado_eur=0,
        respeta_restricciones=True,
    )
    encargo = evaluar_cobertura(brief(), vacio, [])
    assert next(p for p in encargo.cobertura if p.id == "restriccion-1").estado == "pendiente"


def test_presupuesto() -> None:
    dentro = evaluar_cobertura(brief(), _plan(presupuesto=27000), [], _todo_enlazado())
    assert dentro.cobertura[-1].estado == "cubierto"
    assert dentro.cobertura[-1].motivo == "Plan de 27.000 €, dentro del máximo de 27.000 €."
    fuera = evaluar_cobertura(brief(), _plan(presupuesto=30000), [], _todo_enlazado())
    assert [p.id for p in fuera.pendientes] == ["presupuesto"]
    assert "supera el máximo de 27.000 €" in carencias(fuera)[0]

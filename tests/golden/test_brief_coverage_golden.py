"""Trazabilidad del brief de Alborada (kit) frente al plan de ejemplo y los hallazgos del kit."""

from posiq.domain.brief_coverage import carencias, evaluar_cobertura, puntos_del_brief
from posiq.domain.schemas import Finding, Metrics, Plan
from tests.golden.conftest import alborada_brief_summary

# Lo que un redactor razonable enlazaría para Alborada (acciones del plan de ejemplo y hallazgos).
ENLACES_ALBORADA = {
    "objetivo-1": ["A1-2", "A2-2", "F-ciudad-barcelona", "F-brecha-lider"],
    "objetivo-2": ["A1-1", "A3-2"],
    "servicio-1": ["A1-1", "A2-2", "A3-2"],
    "servicio-2": ["A1-1", "A2-3"],
    "ciudad-1": ["A0-1", "A2-1"],
    "ciudad-2": ["A1-2", "A2-2", "F-ciudad-barcelona"],
    "publico-1": ["A1-1", "A3-2"],
    "publico-2": ["A1-1"],
    "publico-3": ["A2-3"],
    "publico-4": ["A1-1"],
    "competidor-1": ["F-brecha-lider"],
    "competidor-2": ["F-brecha-lider"],
    "competidor-3": ["F-brecha-lider", "F-fuente-lider"],
}


def test_puntos_del_brief_de_alborada() -> None:
    puntos = puntos_del_brief(alborada_brief_summary())
    assert len(puntos) == 16
    assert {p.id for p in puntos} == {
        *ENLACES_ALBORADA,
        "restriccion-1",
        "restriccion-2",
        "presupuesto",
    }
    textos = {p.id: p.texto for p in puntos}
    assert textos["objetivo-2"] == "+25 % de primeras visitas de cirugía refractiva en 12 meses"
    assert textos["restriccion-2"] == "Sin comparativas denigratorias"
    assert textos["competidor-3"] == "Grupo Hospitalario Valdecruz"
    assert textos["presupuesto"] == "18.000–27.000 € al año"


def test_plan_de_ejemplo_sin_enlaces(alborada_study: tuple[Metrics, list[Finding], Plan]) -> None:
    _, findings, plan = alborada_study
    encargo = evaluar_cobertura(alborada_brief_summary(), plan, findings)
    cubiertos = {p.id for p in encargo.cobertura if p.estado == "cubierto"}
    # Sin enlaces del redactor, solo lo que el código comprueba contra el plan entero.
    assert cubiertos == {"restriccion-1", "restriccion-2", "presupuesto"}
    assert len(carencias(encargo)) == 13
    presupuesto = encargo.cobertura[-1]
    assert presupuesto.motivo == "Plan de 22.000 €, dentro del máximo de 27.000 €."
    restriccion = next(p for p in encargo.cobertura if p.id == "restriccion-1")
    assert restriccion.accion_ids == [a.id for a in plan.acciones] and len(plan.acciones) == 9


def test_plan_de_ejemplo_enlazado_cubre_todo(
    alborada_study: tuple[Metrics, list[Finding], Plan],
) -> None:
    _, findings, plan = alborada_study
    encargo = evaluar_cobertura(alborada_brief_summary(), plan, findings, ENLACES_ALBORADA)
    print()
    for p in encargo.cobertura:
        print(f"{p.id:14} {p.estado:9} {p.accion_ids + p.hallazgo_ids} {p.motivo}")
    assert carencias(encargo) == []
    objetivo = encargo.cobertura[0]
    assert objetivo.accion_ids == ["A1-2", "A2-2"]
    assert objetivo.hallazgo_ids == ["F-ciudad-barcelona", "F-brecha-lider"]

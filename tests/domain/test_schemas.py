import pytest
from pydantic import ValidationError

from posiq.domain.schemas import (
    Finding,
    Market,
    Phase,
    Plan,
    PromptTemplate,
    peso_posicion,
    validate_plan_against_brief,
)
from tests.domain.factories import action, brand, brief, evaluation


def test_action_sin_finding_ids_falla() -> None:
    with pytest.raises(ValidationError):
        action(finding_ids=[])


def test_finding_sin_evaluation_ids_falla() -> None:
    with pytest.raises(ValidationError):
        Finding(
            id="F1",
            study_id="S-1",
            titulo="t",
            descripcion="d",
            impacto="L",
            confianza=0.8,
            cifra=0.1,
            origen_cifra="visibilidad",
            evaluation_ids=[],
        )


def test_modelos_inmutables_y_sin_campos_extra() -> None:
    b = brand()
    with pytest.raises(ValidationError):
        b.nombre = "otra"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        brand(campo_inventado=1)


def test_categoria_fuera_del_kit_falla() -> None:
    with pytest.raises(ValidationError):
        evaluation(tipo_mencion="Recomendación")
    with pytest.raises(ValidationError):
        evaluation(fuerza=4)


def test_evaluacion_coherente_con_aparicion() -> None:
    with pytest.raises(ValidationError):
        evaluation(aparece=False, posicion=2)
    with pytest.raises(ValidationError):
        evaluation(aparece=True, posicion=None)
    with pytest.raises(ValidationError):
        evaluation(aparece=True, fuerza=0)
    with pytest.raises(ValidationError):
        evaluation(aparece=False, sentimiento="neutro")
    assert evaluation(aparece=True, fuerza=-1, sentimiento="negativo").fuerza == -1


def test_peso_posicion() -> None:
    assert [peso_posicion(p) for p in (None, 1, 2, 3, 4, 9)] == [0, 3, 2, 2, 1, 1]


def test_desconocimiento() -> None:
    e = evaluation(tipo_mencion="Pasiva", fuerza=1, tipo_fuente="Sin fuente")
    assert e.por_desconocimiento
    assert not evaluation().por_desconocimiento


def test_tipo_derivado_de_instanciacion() -> None:
    def tpl(inst: str) -> PromptTemplate:
        return PromptTemplate.model_validate(
            {
                "id": "X",
                "familia": "Localización",
                "fase_embudo": "descubrimiento",
                "instanciacion": inst,
                "texto": "t",
                "prioridad": "P1",
            }
        )

    assert [tpl(i).tipo for i in ("generico", "ciudad", "marca", "par")] == [
        "espontaneo",
        "espontaneo",
        "asistido",
        "asistido",
    ]


def test_market_ids_unicos() -> None:
    with pytest.raises(ValidationError):
        Market(marcas=[brand(), brand()])


def test_brief_presupuesto_ordenado() -> None:
    with pytest.raises(ValidationError):
        brief(presupuesto_anual_eur=(30000, 10000))


def _plan(presupuesto: float, revisadas: list[str], respeta: bool = True) -> Plan:
    fase = Phase(
        nombre="Fase 0",
        semanas=4,
        objetivo="Fundamentos",
        acciones=[action(restricciones_revisadas=revisadas)],
    )
    return Plan(
        study_id="S-1",
        objetivos=[],
        fases=[fase],
        presupuesto_estimado_eur=presupuesto,
        respeta_restricciones=respeta,
    )


def test_validate_plan_cumple() -> None:
    assert validate_plan_against_brief(_plan(20000, ["No prometer resultados"]), brief()) == []


def test_validate_plan_violaciones() -> None:
    violaciones = validate_plan_against_brief(_plan(30000, [], respeta=False), brief())
    assert len(violaciones) == 3
    assert "supera el máximo" in violaciones[0]
    assert "ignora la restricción" in violaciones[1]


def test_validate_plan_sin_presupuesto_en_brief() -> None:
    plan = _plan(10**6, ["No prometer resultados"])
    assert validate_plan_against_brief(plan, brief(presupuesto_anual_eur=None)) == []


def _proposal(finding_ids: list[str]) -> dict[str, object]:
    from datetime import datetime

    from tests.domain.test_findings import metrics

    finding = {
        "titulo": "t",
        "descripcion": "d",
        "impacto": "M",
        "confianza": 0.6,
        "cifra": 0.1,
        "origen_cifra": "visibilidad",
        "evaluation_ids": ["EJ-1:alborada"],
        "study_id": "S-1",
    }
    return {
        "study_id": "S-1",
        "resumen_ejecutivo": "Resumen",
        "contexto": {
            "marca": "Clínica Alborada Visión",
            "sector": "Oftalmología",
            "motores": ["ChatGPT"],
            "fecha": datetime(2026, 10, 20),
            "origen_datos": "kit",
            "datos_sinteticos": True,
            "limitaciones": ["Datos sintéticos"],
        },
        "diagnostico": {"texto": "d", "metrics": metrics()},
        "competencia": {"texto": "c", "ranking": ["lider", "alborada"]},
        "hallazgos": [finding | {"id": f"F{i}"} for i in range(1, 4)],
        "estrategia": {"texto": "e", "objetivos": [], "prioridades": []},
        "plan": _plan(20000, ["No prometer resultados"]).model_copy(
            update={
                "fases": [
                    Phase(
                        nombre="Fase 0",
                        semanas=4,
                        objetivo="o",
                        acciones=[action(finding_ids=finding_ids)],
                    )
                ]
            }
        ),
        "medicion": {"kpis": ["visibilidad espontánea"], "metodologia": "m", "cadencia": "mensual"},
        "riesgos": [{"riesgo": "r", "mitigacion": "m"}],
        "hoja_ruta": {
            "hitos": [],
            "responsabilidades": {},
            "presupuesto_eur": 20000,
            "seguimiento": "s",
        },
    }


def test_proposal_acciones_enlazadas_a_hallazgos() -> None:
    from posiq.domain.schemas import Proposal

    assert Proposal.model_validate(_proposal(["F1"])).hallazgos[0].id == "F1"
    with pytest.raises(ValidationError, match="hallazgos inexistentes"):
        Proposal.model_validate(_proposal(["F9"]))
    sin_limitaciones = _proposal(["F1"])
    sin_limitaciones["contexto"] = sin_limitaciones["contexto"] | {"limitaciones": []}  # type: ignore[operator]
    with pytest.raises(ValidationError):
        Proposal.model_validate(sin_limitaciones)


def test_proposal_de_un_solo_estudio() -> None:
    from posiq.domain.schemas import Proposal

    base = Proposal.model_validate(_proposal(["F1"]))
    hallazgo_ajeno = base.hallazgos[0].model_copy(update={"study_id": "S-2"})
    casos = {
        "hallazgos de otro estudio": {"hallazgos": [hallazgo_ajeno, *base.hallazgos[1:]]},
        "el plan": {"plan": base.plan.model_copy(update={"study_id": "S-2"})},
        "las métricas": {
            "diagnostico": base.diagnostico.model_copy(
                update={"metrics": base.diagnostico.metrics.model_copy(update={"study_id": "S-2"})}
            )
        },
    }
    for mensaje, cambio in casos.items():
        with pytest.raises(ValidationError, match=mensaje):
            Proposal.model_validate(base.model_dump() | cambio)


def test_study() -> None:
    from datetime import datetime

    from posiq.domain.schemas import Study

    study = Study(
        id="S-1",
        brand_id="clinica-alborada-vision",
        brief=brief(),
        modo="kit",
        creado_en=datetime(2026, 10, 20),
        version_metodologia="reload-geo-2026",
        score_version="1.0",
    )
    assert study.estado == "en_curso"
    with pytest.raises(ValidationError):
        Study.model_validate(study.model_dump() | {"modo": "sintetico"})
    with pytest.raises(ValidationError):
        Study.model_validate(study.model_dump() | {"estado": "pausado"})

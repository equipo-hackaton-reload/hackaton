from typing import Any

import pytest

from posiq.domain.schemas import (
    Finding,
    MentionQuality,
    Metrics,
    Phase,
    Plan,
    VisibilityCell,
)
from posiq.domain.scoring import AppearanceProfile, score_from_profile
from posiq.domain.simulation import ADVERTENCIA, TOPE_SEGMENTO, simulate_plan
from tests.domain.factories import action

FOCO = "alborada"


def cell(dimension: str, valor: str, n: int, tasa: float) -> VisibilityCell:
    return VisibilityCell.model_validate(
        {
            "brand_id": FOCO,
            "tipo": "espontaneo",
            "dimension": dimension,
            "valor": valor,
            "n": n,
            "apariciones": round(n * tasa),
            "tasa": tasa if n else None,
        }
    )


def metrics(tasa: float = 0.4, fuerza: float = 1.5, with_data: bool = True) -> Metrics:
    profile = AppearanceProfile(tasa=tasa, peso_medio=2.0, fuerza_media=fuerza, calidad_media=0.6)
    score = score_from_profile(FOCO, 100 if with_data else 0, profile)
    cells = (
        [
            cell("global", "global", 100, tasa),
            cell("fase", "descubrimiento", 60, min(1.0, tasa * 1.25)),
            cell("fase", "decision", 40, tasa * 0.625),
            cell("motor", "ChatGPT", 50, tasa * 0.5),
            cell("motor", "Gemini", 50, tasa * 1.5 if tasa <= 0.66 else 1.0),
            cell("ciudad", "Barcelona", 10, tasa / 4),
        ]
        if with_data
        else [cell("global", "global", 0, 0.0)]
    )
    return Metrics(
        study_id="S-1",
        score_version="1.0",
        marca_foco_id=FOCO,
        lider_id=None,
        score_global=score if with_data else score.model_copy(update={"score": None}),
        scores=[score],
        scores_por_motor=[],
        ranking=[FOCO],
        visibilidad=cells,
        calidad_menciones=[
            MentionQuality(brand_id=FOCO, tipo="espontaneo", apariciones=40, fuerza_media=fuerza)
        ],
        top_fuentes=[],
        brecha_fuentes=[],
        n_ejecuciones={},
    )


FINDINGS = [
    Finding(
        id=f"F{i}",
        study_id="S-1",
        titulo="t",
        descripcion="d",
        fase_embudo="decision" if i == 2 else None,
        impacto="M",
        confianza=0.8,
        cifra=0.1,
        origen_cifra="x",
        evaluation_ids=["EJ-1:alborada"],
    )
    for i in (1, 2)
]


def plan(*fases: list[Any]) -> Plan:
    return Plan(
        study_id="S-1",
        objetivos=[],
        fases=[
            Phase(nombre=f"Fase {i}", semanas=4, objetivo="o", acciones=acciones)
            for i, acciones in enumerate(fases)
        ],
        presupuesto_estimado_eur=0,
        respeta_restricciones=True,
    )


def contenido(id: str = "A1", impacto: str = "M", **kw: Any) -> Any:
    return action(id=id, finding_ids=["F1"], palanca="contenido", impacto=impacto, **kw)


def test_plan_vacio_no_cambia_nada() -> None:
    m = metrics()
    assert simulate_plan(plan(), m, FINDINGS).proyecciones == []
    (p,) = simulate_plan(plan([]), m, FINDINGS).proyecciones
    assert p.score.minimo == p.score.esperado == p.score.maximo == m.score_global.score
    assert p.tasa_espontanea.esperado == pytest.approx(0.4)


def test_una_accion_sube_la_proyeccion() -> None:
    m = metrics()
    r = simulate_plan(plan([contenido()]), m, FINDINGS)
    (p,) = r.proyecciones
    assert m.score_global.score is not None
    assert m.score_global.score < p.score.minimo < p.score.esperado < p.score.maximo
    # Sin fase ni motores apunta a toda la población: +4 puntos de tasa esperados.
    assert p.tasa_espontanea.esperado == pytest.approx(0.44)
    assert r.advertencia == ADVERTENCIA and r.supuestos


def test_rendimientos_decrecientes() -> None:
    m = metrics()
    una = simulate_plan(plan([contenido()]), m, FINDINGS).proyecciones[0].tasa_espontanea.esperado
    dos = simulate_plan(plan([contenido("A1"), contenido("A2")]), m, FINDINGS)
    delta_uno, delta_dos = una - 0.4, dos.proyecciones[0].tasa_espontanea.esperado - 0.4
    assert delta_uno < delta_dos < 2 * delta_uno
    assert delta_dos == pytest.approx(delta_uno * 1.6)


def test_tope_por_segmento_y_nunca_mas_de_100() -> None:
    acciones = [
        action(id=f"A{i}", finding_ids=["F1"], palanca="autoridad_terceros", impacto="L")
        for i in range(20)
    ]
    r = simulate_plan(plan(acciones), metrics(), FINDINGS)
    assert all(s.delta.maximo <= TOPE_SEGMENTO + 1e-9 for s in r.segmentos)
    alta = simulate_plan(plan(acciones), metrics(tasa=0.9, fuerza=3.0), FINDINGS)
    (p,) = alta.proyecciones
    assert p.score.maximo <= 100 and p.tasa_espontanea.maximo <= 1


def test_reproducible() -> None:
    m = metrics()
    p = plan([contenido()], [contenido("A2", fase_embudo="decision", motores_objetivo=["ChatGPT"])])
    assert simulate_plan(p, m, FINDINGS) == simulate_plan(p, m, FINDINGS)


def test_fases_acumuladas() -> None:
    p = plan([contenido("A1")], [], [contenido("A2", impacto="L")])
    proy = simulate_plan(p, metrics(), FINDINGS).proyecciones
    assert [x.acciones for x in proy] == [["A1"], ["A1"], ["A1", "A2"]]
    esperados = [x.score.esperado for x in proy]
    assert esperados[0] == esperados[1] < esperados[2]


def test_acciones_sin_efecto() -> None:
    p = plan(
        [
            action(id="M", finding_ids=["F1"], palanca="medicion"),
            action(id="X", finding_ids=["F-otro-estudio"], palanca="contenido"),
            contenido("Y", motores_objetivo=["Claude"]),
        ]
    )
    r = simulate_plan(p, metrics(), FINDINGS)
    assert {a.action_id: a.motivo[:8] for a in r.acciones_sin_efecto} == {
        "M": "la palan",
        "X": "no enlaz",
        "Y": "no apunt",
    }
    assert r.proyecciones[0].score.esperado == metrics().score_global.score


def test_alcance_por_fase_de_hallazgo_y_ciudad() -> None:
    m = metrics()
    por_hallazgo = action(id="A", finding_ids=["F2"], palanca="contenido")
    r = simulate_plan(plan([por_hallazgo]), m, FINDINGS)
    assert {s.segmento.split(" · ")[0] for s in r.segmentos} == {"decision"}
    ciudad = contenido("B", descripcion="Guía local de cirugía refractiva en BARCELONA")
    r = simulate_plan(plan([ciudad]), m, FINDINGS)
    (seg,) = r.segmentos
    assert (seg.segmento, seg.dimension, seg.n) == ("ciudad · Barcelona", "ciudad", 10)
    # Una ciudad pesa poco en el total: 10 de 100 evaluaciones.
    assert r.proyecciones[0].tasa_espontanea.esperado == pytest.approx(0.404)


def test_sin_datos() -> None:
    r = simulate_plan(plan([contenido()]), metrics(with_data=False), FINDINGS)
    assert r.score_actual is None and r.proyecciones == [] and r.tasa_espontanea_actual is None


def test_marca_que_hoy_no_aparece() -> None:
    r = simulate_plan(plan([contenido()]), metrics(tasa=0.0), FINDINGS)
    (p,) = r.proyecciones
    assert p.score.esperado > 0

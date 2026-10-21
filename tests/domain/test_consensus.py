"""Consenso del juez (`domain/consensus.py`): voto por mayoría, empates y confianza."""

import pytest

from posiq.domain.consensus import consenso
from posiq.domain.schemas import Evaluation
from tests.domain.factories import evaluation


def ev(aparece: bool = True, **kw: object) -> Evaluation:
    if not aparece:
        kw = {"posicion": None, "fuerza": 0} | kw
    return evaluation(aparece=aparece, **kw)


def test_unanimidad() -> None:
    c = consenso([ev(fuerza=2), ev(fuerza=2), ev(fuerza=2)])
    assert c.n == 3 and c.acuerdo == 1.0 and not c.empates
    assert c.evaluacion.fuerza == 2
    assert c.evaluacion.confianza == 1.0 and not c.evaluacion.necesita_revision


def test_mayoria_y_confianza_es_el_menor_acuerdo() -> None:
    c = consenso([ev(fuerza=3), ev(fuerza=2), ev(fuerza=3)])
    assert c.evaluacion.fuerza == 3
    assert c.acuerdo_por_campo == {
        "aparece": 1.0,
        "posicion": 1.0,
        "fuerza": pytest.approx(2 / 3),
        "tipo_fuente": 1.0,
    }
    assert c.acuerdo == pytest.approx(2 / 3)
    assert c.evaluacion.confianza == pytest.approx(2 / 3)
    assert c.evaluacion.necesita_revision  # 2/3 < 0,75


def test_quien_pierde_en_aparicion_no_vota_el_resto() -> None:
    c = consenso([ev(fuerza=3), ev(False), ev(fuerza=1, posicion=4), ev(fuerza=1, posicion=4)])
    assert c.evaluacion.aparece
    assert (c.evaluacion.fuerza, c.evaluacion.posicion) == (1, 4)
    assert c.acuerdo_por_campo["aparece"] == 0.75
    assert c.acuerdo_por_campo["fuerza"] == 0.5


def test_mayoria_de_no_aparece_da_una_evaluacion_coherente() -> None:
    c = consenso([ev(False), ev(tipo_mencion="Recomendación activa"), ev(False)])
    e = c.evaluacion
    assert not e.aparece and e.posicion is None and e.fuerza == 0 and e.tipo_mencion is None


def test_empate_en_aparicion_es_conservador() -> None:
    c = consenso([ev(True), ev(False)])
    assert not c.evaluacion.aparece
    assert "aparece" in c.empates
    assert c.acuerdo == 0.5 and c.evaluacion.necesita_revision


def test_empates_en_campos_del_score_bajan_el_score() -> None:
    c = consenso(
        [
            ev(posicion=1, fuerza=3, tipo_fuente="Medio"),
            ev(posicion=3, fuerza=-1, tipo_fuente="Sin fuente"),
        ]
    )
    e = c.evaluacion
    assert (e.posicion, e.fuerza, e.tipo_fuente) == (3, -1, "Sin fuente")
    assert {"posicion", "fuerza", "tipo_fuente"} <= set(c.empates)


def test_tipo_fuente_sin_resolver_gana_a_sin_fuente_en_empate() -> None:
    c = consenso([ev(tipo_fuente="Sin fuente"), ev(tipo_fuente=None)])
    assert c.evaluacion.tipo_fuente is None


def test_empate_fuera_del_score_gana_la_primera() -> None:
    c = consenso([ev(sentimiento="neutro"), ev(sentimiento="positivo")])
    assert c.evaluacion.sentimiento == "neutro"
    assert "sentimiento" in c.empates
    assert c.acuerdo == 1.0  # el sentimiento no entra en el score


def test_origen_por_mayoria() -> None:
    c = consenso([ev(origen="jev"), ev(origen="fallback"), ev(origen="fallback")])
    assert c.evaluacion.origen == "fallback"


def test_una_sola_evaluacion() -> None:
    e = ev(fuerza=2, confianza=0.6)
    c = consenso([e])
    assert c.evaluacion.fuerza == 2 and c.acuerdo == 1.0


def test_umbral_de_revision_configurable() -> None:
    votos = [ev(fuerza=3), ev(fuerza=2), ev(fuerza=3)]
    assert not consenso(votos, umbral_revision=0.6).evaluacion.necesita_revision


def test_evaluaciones_de_respuestas_distintas_son_un_error() -> None:
    with pytest.raises(ValueError, match="distintas"):
        consenso([ev(run_id="EJ-1"), ev(run_id="EJ-2")])
    with pytest.raises(ValueError):
        consenso([])

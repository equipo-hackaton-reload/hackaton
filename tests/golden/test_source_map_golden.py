"""Mapa de fuentes del kit (oftalmología) y oportunidades de Alborada (ADR 0010).

Cifras fijadas con `kit.evaluations()` (etiquetas del kit donde existen), las mismas que dan la
cifra canónica 25,93.
"""

import pytest

from posiq.domain.findings import detect_findings
from posiq.domain.schemas import BriefSummary, Finding, Metrics
from posiq.domain.source_map import (
    WEBS_PROPIAS,
    DatosEstudio,
    MapaFuentes,
    cuota_por_tipo,
    hallazgo_web_propia,
    mapa_fuentes,
    oportunidades_fuente,
    punto_de_partida,
)
from tests.golden.conftest import Kit

FOCO = "clinica-alborada-vision"
SECTOR = "Sanidad privada · Oftalmología"


@pytest.fixture(scope="module")
def estudio(kit: Kit) -> DatosEstudio:
    return DatosEstudio(kit.market, kit.prompts, kit.runs, kit.evaluations())


@pytest.fixture(scope="module")
def mapa(kit: Kit, estudio: DatosEstudio) -> MapaFuentes:
    return mapa_fuentes(SECTOR, [estudio], kit.sources)


def test_mapa_del_sector(mapa: MapaFuentes) -> None:
    assert (mapa.n_estudios, mapa.n_marcas, mapa.n_citas) == (1, 10, 1631)
    # 15 dominios ganados + la entrada agregada de las 10 webs propias.
    assert len(mapa.fuentes) == 16
    assert all(f.n_marcas >= 2 for f in mapa.fuentes)
    assert not any(f.dominio.endswith(".example") and f.tipo == "Web propia" for f in mapa.fuentes)


def test_top_5_fuentes_del_sector(mapa: MapaFuentes) -> None:
    top = [(f.dominio, f.tipo, f.citas, f.cuota_citas) for f in mapa.fuentes[:5]]
    assert top == [
        (WEBS_PROPIAS, "Web propia", 185, 0.1134),
        ("directoriomedico.example", "Directorio / comparador", 141, 0.0865),
        ("diariosalud.example", "Medio", 139, 0.0852),
        ("comparaclinicas.example", "Directorio / comparador", 136, 0.0834),
        ("saludactual.example", "Medio", 129, 0.0791),
    ]
    assert cuota_por_tipo(mapa) == {
        "Medio": 0.2342,
        "Ranking / institución": 0.2194,
        "Directorio / comparador": 0.1699,
        "Plataforma de reseñas": 0.1649,
        "Web propia": 0.1134,
        "Red social / foro": 0.0981,
    }


def test_web_propia_de_alborada(kit: Kit, estudio: DatosEstudio) -> None:
    f = hallazgo_web_propia(estudio, FOCO, kit.sources)
    assert f is not None
    assert (f.cifra, round(f.cifra * 100, 1)) == (0.0585, 5.9)
    assert "33 de las 564 citas" in f.descripcion
    assert "las webs propias en conjunto, el 12,4 %" in f.descripcion
    assert "3,3 %" in f.descripcion  # media de los competidores
    assert f.impacto == "S"
    assert len(f.evaluation_ids) == 201
    assert all(i.endswith(f":{FOCO}") for i in f.evaluation_ids)


def test_top_3_oportunidades_de_alborada(
    kit: Kit, mapa: MapaFuentes, estudio: DatosEstudio
) -> None:
    ops = oportunidades_fuente(mapa, estudio, FOCO, kit.sources)
    resumen = [
        (o.dominio, o.presencia_marca, o.presencia_competidores, o.valor, o.puntuacion)
        for o in ops[:3]
    ]
    assert resumen == [
        ("wikipedia.org", 0.1183, 0.1723, 0.0031, "Media"),
        ("comparaclinicas.example", 0.2151, 0.2195, 0.0004, "Baja"),
        ("rankingclinicas.example", 0.1398, 0.143, 0.0002, "Baja"),
    ]
    ids_validos = {e.id for e in estudio.evaluations}
    for o in ops:
        assert o.evaluation_ids and set(o.evaluation_ids) <= ids_validos
    tipos = oportunidades_fuente(mapa, estudio, FOCO, kit.sources, nivel="tipo")
    assert [(o.tipo, o.valor, o.puntuacion) for o in tipos] == [
        ("Directorio / comparador", 0.0032, "Media"),
        ("Ranking / institución", 0.0031, "Media"),
    ]


def test_punto_de_partida_con_el_brief(mapa: MapaFuentes, alborada_brief: BriefSummary) -> None:
    p = punto_de_partida(mapa, alborada_brief)
    assert [f.dominio for f in p.prioritarias] == [
        "comparaclinicas.example",
        "directoriomedico.example",
        "diariosalud.example",
        "saludactual.example",
        "colegiooftalmologos.example",
    ]
    assert {f.base for f in p.prioritarias} == {"ciudad:Madrid+Barcelona"}
    assert p.cuota_webs_propias == 0.1134
    assert set(p.por_motor) == {"ChatGPT", "Claude", "Gemini", "Perplexity"}


def test_no_cambia_los_hallazgos_ni_la_cifra_canonica(
    metrics_alborada: Metrics, alborada_brief: BriefSummary, findings_alborada: list[Finding]
) -> None:
    assert metrics_alborada.score_global.score == 25.93
    assert len(detect_findings(metrics_alborada, alborada_brief)) == 7
    assert "F-web-propia" not in {f.id for f in findings_alborada}

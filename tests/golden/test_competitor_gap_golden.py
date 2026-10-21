"""Competidores declarados por Alborada frente a los que pone la IA en el kit (ADR 0012).

Cifras con `kit.evaluations()` (etiquetas del kit donde existen), las de la cifra canónica 25,93.
"""

from posiq.domain.competitor_gap import brecha_competidores
from posiq.domain.schemas import BriefSummary, Metrics
from tests.golden.conftest import Kit


def test_alborada_declarados_frente_a_la_ia(
    kit: Kit, alborada_brief: BriefSummary, metrics_alborada: Metrics
) -> None:
    r = brecha_competidores(alborada_brief, kit.market, metrics_alborada)
    assert (r.puesto_foco, r.n_marcas, r.score_foco) == (8, 10, 25.93)
    assert r.no_resueltos == []
    assert [(c.brand_id, c.puesto, c.score) for c in r.declarados] == [
        ("grupo-hospitalario-valdecruz", 1, 66.46),
        ("instituto-oftalmico-tramuntana", 2, 47.24),
        ("laser-nitida", 4, 37.0),
    ]
    assert [(c.brand_id, c.puesto, c.ventaja_puntos) for c in r.no_declarados_por_delante] == [
        ("oftalmos-centro", 3, 13.11),
        ("clinica-del-ojo-cervantes", 5, 1.71),
        ("instituto-ocular-santa-eulalia", 6, 1.16),
        ("vistalia-oftalmologia", 7, 0.38),
    ]
    assert r.sorpresas == ["oftalmos-centro"]
    assert r.declarados_poco_mencionados == []
    (f,) = r.hallazgos
    assert f.id == "F-competidor-no-declarado"
    assert (f.cifra, f.unidad, f.impacto, f.confianza) == (13.11, "puntos", "L", 0.8)
    assert len(f.evaluation_ids) == 240
    assert {e.split(":")[-1] for e in f.evaluation_ids} == {"oftalmos-centro"}
    assert "Oftalmos Centro, 3.ª con 39,0 puntos (+13,1)" in f.descripcion

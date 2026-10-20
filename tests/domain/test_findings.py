from typing import Any

from posiq.domain.findings import MAX_FINDINGS, confidence_for, detect_findings
from posiq.domain.schemas import (
    MentionQuality,
    Metrics,
    ScoreBreakdown,
    SourceGap,
    VisibilityCell,
)
from tests.domain.factories import brief

FOCO, LIDER = "alborada", "lider"


def cell(tipo: str, dimension: str, valor: str, tasa: float | None, n: int = 40) -> VisibilityCell:
    return VisibilityCell.model_validate(
        {
            "brand_id": FOCO,
            "tipo": tipo,
            "dimension": dimension,
            "valor": valor,
            "n": n if tasa is not None else 0,
            "apariciones": round((tasa or 0) * n),
            "tasa": tasa,
            "evaluation_ids": [f"EJ-{dimension}-{valor}-{i}:{FOCO}" for i in range(2)]
            if tasa is not None
            else [],
        }
    )


def score(brand_id: str, value: float | None) -> ScoreBreakdown:
    return ScoreBreakdown(
        brand_id=brand_id,
        n_evaluaciones=80 if value is not None else 0,
        score=value,
        score_version="1.0",
    )


def quality(tipo: str = "espontaneo", **kw: Any) -> MentionQuality:
    return MentionQuality.model_validate({"brand_id": FOCO, "tipo": tipo, "apariciones": 0} | kw)


def metrics(
    cells: list[VisibilityCell] | None = None,
    scores: tuple[float | None, float | None] = (60, 60),
    gaps: list[SourceGap] | None = None,
    qualities: list[MentionQuality] | None = None,
    lider: str | None = LIDER,
) -> Metrics:
    s = [score(FOCO, scores[0]), score(LIDER, scores[1])]
    return Metrics(
        study_id="S-1",
        score_version="1.0",
        marca_foco_id=FOCO,
        lider_id=lider,
        score_global=s[0],
        scores=s,
        scores_por_motor=[],
        ranking=[LIDER, FOCO],
        visibilidad=cells or [],
        calidad_menciones=qualities or [],
        top_fuentes=[],
        brecha_fuentes=gaps or [],
        n_ejecuciones={},
    )


def ids(m: Metrics) -> list[str]:
    return [f.id for f in detect_findings(m, brief())]


def test_sin_senales_no_hay_hallazgos() -> None:
    assert ids(metrics()) == []
    assert confidence_for(5) == 0.45 and confidence_for(20) == 0.65 and confidence_for(60) == 0.8


def test_caida_embudo() -> None:
    fases = [
        cell("espontaneo", "fase", "descubrimiento", 0.6),
        cell("espontaneo", "fase", "comparacion", None),
        cell("espontaneo", "fase", "validacion", 0.5),
        cell("espontaneo", "fase", "decision", 0.2),
    ]
    (f,) = detect_findings(metrics(fases), brief())
    assert f.id == "F-caida-embudo" and f.fase_embudo == "decision" and f.impacto == "L"
    assert f.cifra == 0.4 and f.evaluation_ids[0].startswith("EJ-fase-decision")
    assert f.study_id == "S-1"
    plana = [
        cell("espontaneo", "fase", "descubrimiento", 0.5),
        cell("espontaneo", "fase", "decision", 0.45),
    ]
    assert ids(metrics(plana)) == []


def test_motor_debil() -> None:
    motores = [
        cell("espontaneo", "motor", "Perplexity", 0.7),
        cell("espontaneo", "motor", "Gemini", 0.6),
        cell("espontaneo", "motor", "Claude", 0.1),
        cell("espontaneo", "motor", "ChatGPT", 0.3),
    ]
    (f,) = detect_findings(metrics(motores), brief())
    assert f.id == "F-motor-debil" and f.cifra == 0.1 and "ChatGPT" in f.descripcion
    assert ids(metrics([cell("espontaneo", "motor", "Gemini", 0.5)])) == []
    parejos = [
        cell("espontaneo", "motor", "Gemini", 0.5),
        cell("espontaneo", "motor", "Claude", 0.4),
    ]
    assert ids(metrics(parejos)) == []


def test_fuente_lider() -> None:
    gap = SourceGap(
        dominio="rankingclinicas.example",
        tipo="Ranking / institución",
        con_lider=10,
        con_marca=2,
        brecha=8,
        lider_sin_marca=6,
        evaluation_ids=["EJ-1:alborada"],
    )
    (f,) = detect_findings(metrics(gaps=[gap]), brief())
    assert f.id == "F-fuente-lider" and f.impacto == "L" and f.evaluation_ids == ["EJ-1:alborada"]
    poco = gap.model_copy(update={"lider_sin_marca": 1})
    assert ids(metrics(gaps=[poco])) == []
    assert ids(metrics(gaps=[gap], lider=None)) == []


def test_ciudad_baja() -> None:
    cells = [
        cell("espontaneo", "global", "global", 0.4),
        cell("espontaneo", "ciudad", "Madrid", 0.5),
        cell("espontaneo", "ciudad", "Barcelona", 0.05),
    ]
    (f,) = detect_findings(metrics(cells), brief())
    assert f.id == "F-ciudad-barcelona" and f.impacto == "L"
    sin_datos = [cell("espontaneo", "ciudad", "Barcelona", None)]
    assert ids(metrics(sin_datos)) == []


def test_brecha_lider() -> None:
    cells = [cell("espontaneo", "global", "global", 0.4)]
    (f,) = detect_findings(metrics(cells, scores=(20, 60)), brief())
    assert f.id == "F-brecha-lider" and f.cifra == 40 and f.impacto == "L"
    assert ids(metrics(cells, scores=(55, 60))) == []
    assert ids(metrics(cells, scores=(None, 60))) == []


def test_asistida_vs_espontanea() -> None:
    cells = [
        cell("espontaneo", "global", "global", 0.3),
        cell("asistido", "global", "global", 0.95),
    ]
    assert ids(metrics(cells)) == ["F-asistida-vs-espontanea"]


def test_recomendacion_debil_y_negativas() -> None:
    cells = [cell("espontaneo", "global", "global", 0.4)]
    debil = quality(apariciones=10, fuerza_media=1.1)
    negativas = quality(
        "asistido",
        negativas=2,
        por_desconocimiento=1,
        negativas_ids=["a", "b"],
        desconocimiento_ids=["c"],
    )
    found = detect_findings(metrics(cells, qualities=[debil, negativas]), brief())
    assert [f.id for f in found] == ["F-recomendacion-debil", "F-menciones-negativas"]
    assert found[1].evaluation_ids == ["a", "b", "c"]
    assert ids(metrics(cells, qualities=[quality(apariciones=2, fuerza_media=1.0)])) == []


def test_orden_por_impacto_y_maximo() -> None:
    cells = [
        cell("espontaneo", "global", "global", 0.4),
        cell("asistido", "global", "global", 1.0),
        cell("espontaneo", "fase", "descubrimiento", 0.6),
        cell("espontaneo", "fase", "decision", 0.48),
        cell("espontaneo", "motor", "Gemini", 0.8),
        cell("espontaneo", "motor", "Claude", 0.1),
        cell("espontaneo", "ciudad", "Madrid", 0.05),
        cell("espontaneo", "ciudad", "Barcelona", 0.06),
    ]
    qualities = [
        quality(apariciones=10, fuerza_media=1.0),
        quality("asistido", negativas=1, negativas_ids=["x"]),
    ]
    found = detect_findings(metrics(cells, scores=(10, 60), qualities=qualities), brief())
    assert len(found) == MAX_FINDINGS
    order = {"L": 0, "M": 1, "S": 2}
    assert [order[f.impacto] for f in found] == sorted(order[f.impacto] for f in found)

"""Competidores declarados en el brief frente a los que pone la IA (ADR 0012)."""

from posiq.domain.competitor_gap import (
    MIN_VENTAJA_PUNTOS,
    brecha_competidores,
    resolver_competidor,
)
from posiq.domain.schemas import Market, Metrics, ScoreBreakdown, VisibilityCell
from tests.domain.factories import brand, brief

FOCO = "alborada"


def market() -> Market:
    return Market(
        marcas=[
            brand(FOCO, "Clínica Alborada Visión", aliases=["Alborada"]),
            brand("tramuntana", "Instituto Oftálmico Tramuntana", aliases=["Tramuntana"]),
            brand("nitida", "Láser Nítida", aliases=["Nítida"]),
            brand("valdecruz", "Grupo Hospitalario Valdecruz", aliases=["Valdecruz"], rol="lider"),
            brand("oftalmos", "Oftalmos Centro", aliases=["Oftalmos"], rol="contexto"),
            brand("cervantes", "Clínica del Ojo Cervantes", aliases=["Cervantes"], rol="contexto"),
        ]
    )


def _cell(brand_id: str, tasa: float, n: int = 40) -> VisibilityCell:
    return VisibilityCell(
        brand_id=brand_id,
        tipo="espontaneo",
        dimension="global",
        valor="global",
        n=n,
        apariciones=round(tasa * n),
        tasa=tasa,
        evaluation_ids=[f"EJ-{i}:{brand_id}" for i in range(n)],
    )


def metrics(datos: dict[str, tuple[float, float]]) -> Metrics:
    """`datos`: brand_id → (score, tasa espontánea global)."""
    scores = [
        ScoreBreakdown(brand_id=b, n_evaluaciones=40, score=s, score_version="1.0")
        for b, (s, _) in datos.items()
    ]
    ranking = [b for b, _ in sorted(datos.items(), key=lambda kv: -kv[1][0])]
    return Metrics(
        study_id="S-1",
        score_version="1.0",
        marca_foco_id=FOCO,
        lider_id="valdecruz",
        score_global=next(s for s in scores if s.brand_id == FOCO),
        scores=scores,
        scores_por_motor=[],
        ranking=ranking,
        visibilidad=[_cell(b, t) for b, (_, t) in datos.items()],
        calidad_menciones=[],
        top_fuentes=[],
        brecha_fuentes=[],
        n_ejecuciones={},
    )


BASE = {
    "valdecruz": (66.0, 0.9),
    "tramuntana": (47.0, 0.7),
    "oftalmos": (39.0, 0.6),
    "nitida": (37.0, 0.55),
    "cervantes": (28.0, 0.45),
    FOCO: (26.0, 0.4),
}


def _id(nombre: str, m: Market) -> str | None:
    b = resolver_competidor(nombre, m)
    return b.id if b else None


def test_resuelve_por_nombre_alias_y_parcial() -> None:
    m = market()
    assert _id("LASER NITIDA", m) == "nitida"
    assert _id("Valdecruz", m) == "valdecruz"
    assert _id("Grupo Valdecruz", m) == "valdecruz"
    assert _id("tramuntana", m) == "tramuntana"
    assert _id("Clínica Inexistente", m) is None
    assert _id("   ", m) is None


def test_ambiguo_no_se_resuelve() -> None:
    m = Market(marcas=[brand("a", "Visión Norte"), brand("b", "Visión Sur")])
    assert _id("Visión", m) is None


def test_no_declarado_por_delante_relevante() -> None:
    r = brecha_competidores(
        brief(competidores_declarados=["Tramuntana", "Láser Nítida", "Valdecruz"]),
        market(),
        metrics(BASE),
    )
    assert [c.brand_id for c in r.declarados] == ["valdecruz", "tramuntana", "nitida"]
    assert [c.brand_id for c in r.no_declarados_por_delante] == ["oftalmos", "cervantes"]
    # Cervantes va por delante solo 2 puntos: no llega al umbral.
    assert r.sorpresas == ["oftalmos"]
    assert r.umbral_ventaja_puntos == MIN_VENTAJA_PUNTOS
    (f,) = r.hallazgos
    assert f.id == "F-competidor-no-declarado"
    assert (f.cifra, f.unidad, f.impacto) == (13.0, "puntos", "L")
    assert "Oftalmos Centro" in f.titulo
    assert "39,0 puntos (+13,0)" in f.descripcion
    assert f.evaluation_ids and all(i.endswith(":oftalmos") for i in f.evaluation_ids)


def test_impacto_m_por_debajo_de_10_puntos() -> None:
    datos = BASE | {"oftalmos": (33.0, 0.5)}
    declarados = ["Tramuntana", "Nítida", "Valdecruz"]
    r = brecha_competidores(brief(competidores_declarados=declarados), market(), metrics(datos))
    assert r.hallazgos[0].impacto == "M"


def test_declarado_poco_mencionado_y_no_resuelto() -> None:
    datos = BASE | {"nitida": (5.0, 0.05)}
    declarados = [
        "Tramuntana",
        "Láser Nítida",
        "Valdecruz",
        "Oftalmos",
        "Cervantes",
        "Clínica Fantasma",
        "Clínica Alborada Visión",
    ]
    r = brecha_competidores(brief(competidores_declarados=declarados), market(), metrics(datos))
    assert r.no_resueltos == ["Clínica Fantasma"]
    assert FOCO not in {c.brand_id for c in r.declarados}
    assert r.no_declarados_por_delante == []
    assert r.umbral_tasa == 0.2  # max(10 %, 50 % de 40 %)
    assert r.declarados_poco_mencionados == ["nitida"]
    (f,) = r.hallazgos
    assert (f.id, f.cifra, f.unidad, f.impacto) == (
        "F-declarado-poco-visible",
        0.05,
        "fraccion",
        "S",
    )
    assert "Láser Nítida, en el 5 % de 40 respuestas" in f.descripcion


def test_sin_diferencia_no_hay_hallazgos() -> None:
    declarados = ["Valdecruz", "Tramuntana", "Oftalmos", "Nítida", "Cervantes"]
    r = brecha_competidores(brief(competidores_declarados=declarados), market(), metrics(BASE))
    assert r.hallazgos == []
    assert (r.puesto_foco, r.n_marcas) == (6, 6)


def test_foco_lider_no_tiene_nadie_por_delante() -> None:
    datos = BASE | {FOCO: (80.0, 0.95)}
    r = brecha_competidores(brief(competidores_declarados=[]), market(), metrics(datos))
    assert r.puesto_foco == 1
    assert r.no_declarados_por_delante == []
    assert r.hallazgos == []

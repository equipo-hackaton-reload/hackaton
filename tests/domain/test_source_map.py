"""Mapa de fuentes del sector, oportunidades por marca y hallazgo de web propia (ADR 0010)."""

import random

import pytest

from posiq.domain.schemas import Brand, Evaluation, Market, Run, Source
from posiq.domain.source_map import (
    MIN_APARICIONES_COMPETIDOR,
    UMBRAL_ALTA,
    UMBRAL_MEDIA,
    WEBS_PROPIAS,
    DatosEstudio,
    cuota_por_tipo,
    hallazgo_web_propia,
    mapa_fuentes,
    oportunidades_fuente,
    punto_de_partida,
    puntuacion,
)
from tests.domain.factories import brand, brief, evaluation, prompt, run, source

CATALOGO = [
    source("a.example", "Web propia"),
    source("b.example", "Web propia"),
    source("medio.example", "Medio"),
    source("ranking.example", "Ranking / institución"),
    source("dir.example", "Directorio / comparador"),
]
MARCAS = [
    brand("a", "Alfa", dominio="a.example"),
    brand("b", "Beta", dominio="b.example"),
    brand("c", "Gamma", dominio="c.example"),
]


def _run(id: str, dominios: list[str], study: str = "S-1", **kw: object) -> Run:
    return run(
        id,
        marcas=["a", "b", "c"],
        study_id=study,
        fuentes=[Source(dominio=d) for d in dominios],
        **kw,
    )


def _evals(run_id: str, aparecen: set[str], study: str = "S-1") -> list[Evaluation]:
    return [
        evaluation(b, run_id, aparece=b in aparecen, study_id=study, id=f"{run_id}:{b}")
        for b in ("a", "b", "c")
    ]


def _estudio(
    filas: list[tuple[str, list[str], set[str]]],
    study: str = "S-1",
    marcas: list[Brand] = MARCAS,
    **kw: object,
) -> DatosEstudio:
    runs = [_run(id, doms, study, **kw) for id, doms, _ in filas]
    evals = [e for id, _, aparecen in filas for e in _evals(id, aparecen, study)]
    return DatosEstudio(Market(marcas=marcas), [prompt("P-1")], runs, evals)


# --- Mapa y anonimización -------------------------------------------------------------------------


def test_solo_entran_fuentes_citadas_con_al_menos_dos_marcas() -> None:
    estudio = _estudio(
        [
            ("R1", ["solo.example", "medio.example"], {"a"}),
            ("R2", ["solo.example", "medio.example"], {"a"}),
            ("R3", ["medio.example"], {"b"}),
            ("R4", ["huerfana.example"], set()),
        ]
    )
    mapa = mapa_fuentes("Oftalmología", [estudio], CATALOGO)
    assert [f.dominio for f in mapa.fuentes] == ["medio.example"]
    medio = mapa.fuentes[0]
    assert (medio.citas, medio.n_marcas, medio.n_estudios) == (3, 2, 1)
    # Las cuotas son sobre TODAS las citas (6), también las de fuentes que no entran.
    assert mapa.n_citas == 6
    assert medio.cuota_citas == 0.5
    assert mapa.n_marcas == 2


def test_las_webs_propias_se_agregan_y_no_se_listan_dominios_de_marca() -> None:
    estudio = _estudio(
        [
            ("R1", ["a.example", "medio.example"], {"a"}),
            ("R2", ["b.example", "medio.example"], {"b"}),
            # c.example no está en el catálogo, pero es el dominio de Gamma (y con www.).
            ("R3", ["www.c.example"], {"c"}),
        ]
    )
    mapa = mapa_fuentes("Oftalmología", [estudio], CATALOGO)
    dominios = {f.dominio for f in mapa.fuentes}
    assert dominios == {WEBS_PROPIAS, "medio.example"}
    propias = next(f for f in mapa.fuentes if f.dominio == WEBS_PROPIAS)
    assert (propias.tipo, propias.propiedad, propias.citas, propias.n_marcas) == (
        "Web propia",
        "propio",
        3,
        3,
    )
    volcado = mapa.model_dump_json()
    for marca in MARCAS:
        assert marca.id not in {f.dominio for f in mapa.fuentes}
        assert str(marca.dominio) not in volcado


def test_webs_propias_citadas_con_una_sola_marca_no_entran() -> None:
    estudio = _estudio(
        [
            ("R1", ["a.example", "medio.example"], {"a"}),
            ("R2", ["a.example", "medio.example"], {"a", "b"}),
        ]
    )
    # a.example sale con a y b en R2: el agregado sí entra.
    assert WEBS_PROPIAS in {f.dominio for f in mapa_fuentes("x", [estudio], CATALOGO).fuentes}
    solo_a = _estudio(
        [("R1", ["a.example", "medio.example"], {"a"}), ("R2", ["medio.example"], {"b"})]
    )
    assert {f.dominio for f in mapa_fuentes("x", [solo_a], CATALOGO).fuentes} == {"medio.example"}


def test_propio_y_ganado() -> None:
    estudio = _estudio(
        [
            ("R1", ["a.example", "nueva.example", "ranking.example"], {"a", "b"}),
        ]
    )
    mapa = mapa_fuentes("x", [estudio], CATALOGO)
    por_dominio = {f.dominio: f for f in mapa.fuentes}
    assert por_dominio[WEBS_PROPIAS].propiedad == "propio"
    assert por_dominio["ranking.example"].propiedad == "ganado"
    assert por_dominio["ranking.example"].tipo == "Ranking / institución"
    # Fuera del catálogo y sin ser dominio de marca: ganado, tipo desconocido.
    assert (por_dominio["nueva.example"].tipo, por_dominio["nueva.example"].propiedad) == (
        None,
        "ganado",
    )


def test_cuotas_por_motor_y_por_segmento() -> None:
    runs = [
        _run("R1", ["medio.example", "dir.example"], motor="ChatGPT", prompt_id="P-esp"),
        _run("R2", ["medio.example"], motor="Gemini", prompt_id="P-ciudad"),
        _run("R3", ["dir.example"], motor="Gemini", prompt_id="P-asis"),
    ]
    prompts = [
        prompt("P-esp"),
        prompt("P-ciudad", instanciacion="ciudad", ciudad="Madrid", fase_embudo="decision"),
        prompt("P-asis", instanciacion="marca"),
    ]
    evals = [e for r in runs for e in _evals(r.id, {"a", "b"})]
    mapa = mapa_fuentes("x", [DatosEstudio(Market(marcas=MARCAS), prompts, runs, evals)], CATALOGO)
    medio = next(f for f in mapa.fuentes if f.dominio == "medio.example")
    assert medio.cuota_citas == 0.5
    assert medio.por_motor == {"ChatGPT": 0.5, "Gemini": 0.5}
    assert medio.por_segmento == {
        "ciudad:Madrid": 1.0,
        "fase:decision": 1.0,
        "fase:descubrimiento": 0.3333,
        "tipo:espontaneo": 0.6667,
    }
    assert cuota_por_tipo(mapa) == {"Directorio / comparador": 0.5, "Medio": 0.5}


def test_varios_estudios() -> None:
    e1 = _estudio([("R1", ["medio.example"], {"a"})], study="S-1")
    e2 = _estudio([("R1", ["medio.example", "dir.example"], {"b"})], study="S-2")
    mapa = mapa_fuentes("x", [e1, e2], CATALOGO)
    assert [(f.dominio, f.n_estudios, f.n_marcas) for f in mapa.fuentes] == [
        ("medio.example", 2, 2)
    ]
    assert (mapa.n_estudios, mapa.n_citas) == (2, 3)
    with pytest.raises(ValueError, match="repetidos"):
        mapa_fuentes("x", [e1, e1], CATALOGO)


def test_no_se_puede_bajar_el_umbral_de_anonimizacion() -> None:
    estudio = _estudio([("R1", ["medio.example"], {"a"})])
    with pytest.raises(ValueError, match="min_marcas"):
        mapa_fuentes("x", [estudio], CATALOGO, min_marcas=1)
    with pytest.raises(ValueError, match="al menos un estudio"):
        mapa_fuentes("x", [], CATALOGO)


# --- Oportunidades --------------------------------------------------------------------------------


def test_umbrales_de_puntuacion() -> None:
    assert (UMBRAL_ALTA, UMBRAL_MEDIA) == (0.005, 0.002)
    assert puntuacion(0.005) == "Alta"
    assert puntuacion(0.0049) == "Media"
    assert puntuacion(0.002) == "Media"
    assert puntuacion(0.0019) == "Baja"
    assert puntuacion(0.0) == "Baja"


def _escenario_oportunidad() -> DatosEstudio:
    """Alfa aparece en R0-R4 (siempre con dir, con medio solo en R0); Beta y Gamma, en R5-R9."""
    n = MIN_APARICIONES_COMPETIDOR
    filas: list[tuple[str, list[str], set[str]]] = []
    for i in range(n):
        filas.append((f"R{i}", ["dir.example", *(["medio.example"] if i == 0 else [])], {"a"}))
    for i in range(n):
        filas.append((f"R{n + i}", ["medio.example", "dir.example"], {"b", "c"}))
    return _estudio(filas)


def test_oportunidad_por_dominio() -> None:
    estudio = _escenario_oportunidad()
    mapa = mapa_fuentes("x", [estudio], CATALOGO)
    ops = oportunidades_fuente(mapa, estudio, "a", CATALOGO)
    assert [o.dominio for o in ops] == ["medio.example"]
    o = ops[0]
    assert (o.presencia_marca, o.presencia_competidores, o.gap) == (0.2, 1.0, 0.8)
    assert o.cuota_sector == 0.375  # 6 de 16 citas
    assert o.valor == 0.3
    assert o.puntuacion == "Alta"
    # Evidencias: apariciones de Beta y Gamma donde se cita medio y Alfa no aparece, y la ausencia
    # de Alfa en esas mismas respuestas.
    assert o.evaluation_ids == sorted(f"R{i}:{b}" for i in range(5, 10) for b in ("a", "b", "c"))
    # Beta ya está por encima de la media de sus competidores en todo.
    assert oportunidades_fuente(mapa, estudio, "b", CATALOGO) == []


def test_oportunidad_por_tipo_y_sin_competidores() -> None:
    estudio = _escenario_oportunidad()
    mapa = mapa_fuentes("x", [estudio], CATALOGO)
    tipos = oportunidades_fuente(mapa, estudio, "a", CATALOGO, nivel="tipo")
    assert [(o.tipo, o.dominio) for o in tipos] == [("Medio", None)]
    pocas = _estudio([("R1", ["medio.example"], {"b", "c"}), ("R2", ["dir.example"], {"a"})])
    assert oportunidades_fuente(mapa_fuentes("x", [pocas]), pocas, "a") == []
    with pytest.raises(ValueError, match="no está en el mercado"):
        oportunidades_fuente(mapa, estudio, "zeta", CATALOGO)


def test_oportunidad_de_web_propia_mira_la_web_de_cada_marca() -> None:
    n = MIN_APARICIONES_COMPETIDOR
    filas: list[tuple[str, list[str], set[str]]] = []
    for i in range(n):
        filas.append((f"R{i}", ["medio.example", "b.example"], {"a"}))  # cita la web de Beta
    for i in range(n):
        filas.append((f"R{n + i}", ["b.example", "c.example", "medio.example"], {"b", "c"}))
    estudio = _estudio(filas)
    mapa = mapa_fuentes("x", [estudio], CATALOGO)
    propia = next(
        o for o in oportunidades_fuente(mapa, estudio, "a", CATALOGO) if o.tipo == "Web propia"
    )
    assert (propia.dominio, propia.tipo, propia.presencia_marca) == (
        "a.example",
        "Web propia",
        0.0,
    )
    assert propia.presencia_competidores == 1.0


def test_determinismo() -> None:
    estudio = _escenario_oportunidad()
    barajado = DatosEstudio(
        estudio.market,
        estudio.prompts,
        random.Random(7).sample(list(estudio.runs), len(estudio.runs)),
        random.Random(7).sample(list(estudio.evaluations), len(estudio.evaluations)),
    )
    m1 = mapa_fuentes("x", [estudio], CATALOGO)
    m2 = mapa_fuentes("x", [barajado], list(reversed(CATALOGO)))
    assert m1 == m2
    assert oportunidades_fuente(m1, estudio, "a", CATALOGO) == oportunidades_fuente(
        m2, barajado, "a", CATALOGO
    )
    assert hallazgo_web_propia(estudio, "a") == hallazgo_web_propia(barajado, "a")


# --- Hallazgo de web propia -----------------------------------------------------------------------


def test_hallazgo_web_propia() -> None:
    estudio = _estudio(
        [
            ("R1", ["a.example", "medio.example", "b.example", "dir.example"], {"a"}),
            ("R2", ["b.example", "medio.example"], {"b"}),
            ("R3", ["c.example", "medio.example", "dir.example", "ranking.example"], {"c"}),
        ]
    )
    f = hallazgo_web_propia(estudio, "a", CATALOGO)
    assert f is not None
    assert (f.id, f.cifra, f.unidad, f.evaluation_ids) == (
        "F-web-propia",
        0.25,
        "fraccion",
        ["R1:a"],
    )
    # Competidores: Beta 1/2 y Gamma 1/4 → media 37,5 %; 25 % no llega: impacto M.
    assert f.impacto == "M"
    assert "25,0 %" in f.descripcion and "50,0 %" in f.descripcion and "37,5 %" in f.descripcion
    assert hallazgo_web_propia(estudio, "zeta") is None
    sin_dominio = _estudio([("R1", ["medio.example"], {"a"})], marcas=[brand("a", "Alfa")])
    assert hallazgo_web_propia(sin_dominio, "a") is None


# --- Punto de partida -----------------------------------------------------------------------------


def test_punto_de_partida_sin_brief_solo_fuentes_ganadas() -> None:
    estudio = _escenario_oportunidad()
    mapa = mapa_fuentes("x", [estudio], CATALOGO)
    p = punto_de_partida(mapa, top_n=1)
    assert [f.dominio for f in p.prioritarias] == ["dir.example"]
    assert all(f.propiedad == "ganado" for f in p.prioritarias)
    assert set(p.por_tipo) == {"Directorio / comparador", "Medio"}
    assert list(p.por_motor) == ["ChatGPT"]
    assert p.avisos == []


def test_punto_de_partida_filtra_por_ciudades_del_brief() -> None:
    runs = [
        _run("R1", ["medio.example", "a.example"], prompt_id="P-mad"),
        _run("R2", ["dir.example", "b.example"], prompt_id="P-gen"),
    ]
    prompts = [
        prompt("P-mad", instanciacion="ciudad", ciudad="Madrid"),
        prompt("P-gen"),
    ]
    evals = [e for r in runs for e in _evals(r.id, {"a", "b"})]
    mapa = mapa_fuentes("x", [DatosEstudio(Market(marcas=MARCAS), prompts, runs, evals)], CATALOGO)
    p = punto_de_partida(mapa, brief(ciudades=["Madrid", "Valencia"]))
    assert [(f.dominio, f.base) for f in p.prioritarias] == [("medio.example", "ciudad:Madrid")]
    assert p.cuota_webs_propias == 0.5
    assert any("Valencia" in a for a in p.avisos)
    assert any("servicio" in a for a in p.avisos)

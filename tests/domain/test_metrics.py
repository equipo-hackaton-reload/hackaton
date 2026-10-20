import pytest

from posiq.domain.metrics import compute_metrics, resolve_brand
from posiq.domain.schemas import Market
from tests.domain.factories import brand, brief, evaluation, prompt, run, source

FOCO = brand(aliases=["Alborada"])
LIDER = brand(id="lider", nombre="Grupo Valdecruz", rol="lider")
OTRA = brand(id="otra", nombre="Oftalmos Centro", rol="contexto")
MARKET = Market(marcas=[FOCO, LIDER, OTRA])
ALL = ["alborada", "lider", "otra"]
PROMPTS = [
    prompt("P-gen"),
    prompt("P-mad", instanciacion="ciudad", ciudad="Madrid", familia="Localización"),
    prompt("P-dec", fase_embudo="decision", familia="Decisión final"),
    prompt("P-asi", instanciacion="marca", fase_embudo="validacion", marca_nombrada="alborada"),
]
RANKING = source()
MEDIO = source("medio.example", "Medio")
RUNS = [
    run("R1", prompt_id="P-gen", marcas=ALL, fuentes=[RANKING, MEDIO]),
    run("R2", prompt_id="P-gen", marcas=ALL, motor="Gemini", fuentes=[RANKING]),
    run("R3", prompt_id="P-mad", marcas=ALL, fuentes=[RANKING]),
    run("R4", prompt_id="P-dec", marcas=ALL),
    run("R5", prompt_id="P-asi", marcas=["alborada"]),
]


def ev(run_id: str, brand_id: str, aparece: bool, **kw: object):  # type: ignore[no-untyped-def]
    return evaluation(brand_id=brand_id, run_id=run_id, aparece=aparece, **kw)


EVALS = [
    ev("R1", "alborada", True, posicion=2, fuerza=2),
    ev("R1", "lider", True),
    ev("R1", "otra", False),
    ev("R2", "alborada", False),
    ev("R2", "lider", True),
    ev("R2", "otra", True, posicion=2, fuerza=-1, sentimiento="negativo"),
    ev("R3", "alborada", False),
    ev("R3", "lider", True),
    ev("R3", "otra", False),
    ev("R4", "alborada", True, fuerza=1, tipo_mencion="Pasiva", tipo_fuente="Sin fuente"),
    ev("R4", "lider", False),
    ev("R4", "otra", False),
    ev("R5", "alborada", True),
    ev("R5", "otra", True),  # no elegible: R5 solo evalúa alborada
]


@pytest.fixture(scope="module")
def metrics():  # type: ignore[no-untyped-def]
    return compute_metrics(brief(), MARKET, PROMPTS, RUNS, EVALS, [RANKING, MEDIO])


def test_foco_lider_y_ranking(metrics) -> None:  # type: ignore[no-untyped-def]
    assert (metrics.marca_foco_id, metrics.lider_id) == ("alborada", "lider")
    assert metrics.ranking[0] == "lider"
    assert metrics.score_global.brand_id == "alborada"
    assert metrics.score_of("nadie") is None


def test_espontaneo_y_asistido_separados(metrics) -> None:  # type: ignore[no-untyped-def]
    esp = metrics.cell("alborada", "espontaneo", "global", "global")
    asi = metrics.cell("alborada", "asistido", "global", "global")
    assert (esp.n, esp.apariciones, esp.tasa) == (4, 2, 0.5)
    assert (asi.n, asi.tasa) == (1, 1.0)
    assert metrics.n_ejecuciones == {"total": 5, "espontaneo": 4, "asistido": 1, "evaluaciones": 13}


def test_no_elegibles_fuera(metrics) -> None:  # type: ignore[no-untyped-def]
    assert metrics.cell("otra", "asistido", "global", "global").n == 0


def test_segmentos_sin_datos(metrics) -> None:  # type: ignore[no-untyped-def]
    barcelona = metrics.cell("alborada", "espontaneo", "ciudad", "Barcelona")
    assert barcelona.n == 0 and barcelona.tasa is None
    madrid = metrics.cell("alborada", "espontaneo", "ciudad", "Madrid")
    assert (madrid.n, madrid.tasa) == (1, 0.0)
    fases = [c.valor for c in metrics.cells("alborada", "espontaneo", "fase")]
    assert fases == ["descubrimiento", "comparacion", "validacion", "decision"]
    assert metrics.cell("alborada", "espontaneo", "fase", "comparacion").tasa is None
    assert metrics.cell("alborada", "espontaneo", "motor", "Gemini").evaluation_ids == [
        "R2:alborada"
    ]


def test_calidad_de_menciones(metrics) -> None:  # type: ignore[no-untyped-def]
    q = {(m.brand_id, m.tipo): m for m in metrics.calidad_menciones}
    foco = q[("alborada", "espontaneo")]
    assert foco.apariciones == 2 and foco.por_desconocimiento == 1
    assert foco.desconocimiento_ids == ["R4:alborada"]
    assert q[("otra", "espontaneo")].negativas_ids == ["R2:otra"]


def test_fuentes_y_brecha(metrics) -> None:  # type: ignore[no-untyped-def]
    top_lider = [(s.dominio, s.apariciones) for s in metrics.top_fuentes if s.brand_id == "lider"]
    assert top_lider == [("rankingclinicas.example", 3), ("medio.example", 1)]
    (gap,) = metrics.brecha_fuentes
    assert (gap.dominio, gap.con_lider, gap.con_marca, gap.brecha) == (
        "rankingclinicas.example",
        3,
        1,
        2,
    )
    assert gap.evaluation_ids == ["R2:alborada", "R3:alborada"]


def test_sin_lider_no_hay_brecha() -> None:
    market = Market(marcas=[FOCO, OTRA])
    m = compute_metrics(brief(), market, PROMPTS, RUNS, EVALS, [RANKING])
    assert m.lider_id is None and m.brecha_fuentes == []


def test_marca_del_brief_por_alias_o_ausente() -> None:
    assert resolve_brand("alborada", MARKET).id == "alborada"
    with pytest.raises(ValueError, match="no está en el mercado"):
        resolve_brand("Clínica Inventada", MARKET)


def test_sin_evaluaciones() -> None:
    m = compute_metrics(brief(), MARKET, PROMPTS, RUNS, [], [])
    assert m.score_global.score is None
    assert m.ranking == ["alborada", "lider", "otra"]
    assert all(c.tasa is None for c in m.visibilidad)

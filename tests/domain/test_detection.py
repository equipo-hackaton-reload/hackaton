from posiq.domain.detection import (
    brand_mentions,
    detect_brands,
    detect_in_run,
    evaluation_from_detection,
)
from tests.domain.factories import brand, run, source

ALBORADA = brand(aliases=["Alborada Visión", "Alborada"])
NITIDA = brand(id="nitida", nombre="Láser Nítida", aliases=["Nítida"])
IOT = brand(id="iot", nombre="Instituto Oftálmico Tramuntana", aliases=["IOT", "Tramuntana"])
BRANDS = [ALBORADA, NITIDA, IOT]


def ids(text: str) -> list[str]:
    return [d.brand_id for d in detect_brands(text, BRANDS)]


def test_alias_y_acentos() -> None:
    assert ids("Te recomiendo ALBORADA vision") == ["alborada"]
    assert ids("laser nitida tiene buen precio") == ["nitida"]
    assert ids("Nítida, sin más") == ["nitida"]


def test_posicion_por_primera_aparicion() -> None:
    dets = detect_brands("Primero Tramuntana, luego Nítida y después Tramuntana otra vez.", BRANDS)
    assert [(d.brand_id, d.posicion) for d in dets] == [("iot", 1), ("nitida", 2)]
    assert dets[0].menciones == 2


def test_alias_solapados_cuentan_una_vez() -> None:
    dets = detect_brands("Clínica Alborada Visión es buena.", BRANDS)
    assert len(dets) == 1 and dets[0].menciones == 1
    assert dets[0].span == (0, len("Clínica Alborada Visión"))


def test_span_en_texto_original() -> None:
    text = "Opción: «Alborada»."
    (det,) = detect_brands(text, BRANDS)
    assert text[det.span[0] : det.span[1]] == "Alborada"


def test_falsos_positivos_por_limite_de_palabra() -> None:
    assert ids("Las alboradas de Madrid son bonitas") == []
    assert ids("Tramuntanas y nitidamente") == []


def test_alias_corto_exige_limite_estricto() -> None:
    assert ids("Pregunté al IOT por su tecnología") == ["iot"]
    assert ids("Ver iot-clinicas.example o el código IOT2") == []
    assert ids("contacto@iot") == []


def test_texto_sin_marcas() -> None:
    assert detect_brands("", BRANDS) == []
    assert detect_brands("Nada que ver", []) == []


def test_detect_in_run_respeta_marcas_a_evaluar() -> None:
    r = run(texto="Nítida y Alborada", marcas=["alborada"])
    assert list(detect_in_run(r, BRANDS)) == ["alborada"]
    assert detect_in_run(r, BRANDS)["alborada"].posicion == 1


def test_evaluation_from_detection() -> None:
    r = run(texto="Alborada")
    det = detect_in_run(r, BRANDS)["alborada"]
    e = evaluation_from_detection(r, ALBORADA, det)
    assert (e.aparece, e.posicion, e.fuerza, e.tipo_fuente, e.origen) == (
        True,
        1,
        1,
        "Sin fuente",
        "fallback",
    )
    con_fuentes = run(texto="Alborada", fuentes=[source()])
    assert evaluation_from_detection(con_fuentes, ALBORADA, det).tipo_fuente is None
    ausente = evaluation_from_detection(r, ALBORADA, None)
    assert (ausente.aparece, ausente.posicion, ausente.fuerza) == (False, None, 0)


def test_brand_mentions_devuelve_todas_las_menciones_en_el_texto_original() -> None:
    alb = brand("alb", aliases=["Alborada"])
    texto = "Clínica Alborada Visión y luego Alborada."
    assert brand_mentions(texto, [alb]) == [(0, 23, "alb"), (32, 40, "alb")]
    assert texto[32:40] == "Alborada"

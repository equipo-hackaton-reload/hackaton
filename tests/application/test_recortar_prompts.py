"""`REAL_MAX_PROMPTS`: recorte determinista del banco del modo real."""

from posiq.application.nodes.prompts import recortar
from posiq.domain.schemas import PromptInstance


def p(pid: str, plantilla: str, prioridad: str = "P1") -> PromptInstance:
    return PromptInstance(
        id=pid,
        template_id=plantilla,
        familia="Localización",
        fase_embudo="descubrimiento",
        instanciacion="ciudad",
        ciudad="Madrid",
        texto="¿Qué me recomiendas?",
        prioridad=prioridad,  # type: ignore[arg-type]
    )


BANCO = [p("a1", "A"), p("a2", "A"), p("b1", "B", "P2"), p("c1", "C"), p("c2", "C")]


def test_sin_tope_devuelve_todo() -> None:
    assert recortar(BANCO, 0) == BANCO
    assert recortar(BANCO, 10) == BANCO


def test_uno_por_plantilla_p1_antes_que_p2_y_orden_original() -> None:
    assert [x.id for x in recortar(BANCO, 2)] == ["a1", "c1"]
    assert [x.id for x in recortar(BANCO, 3)] == ["a1", "b1", "c1"]
    assert [x.id for x in recortar(BANCO, 4)] == ["a1", "a2", "b1", "c1"]

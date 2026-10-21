"""Exactitud de marca de Alborada sobre los datos REALES del kit (sin respuestas sintéticas).

Si el kit no tiene errores sobre la marca, el resultado es «0 inexactitudes»: no se fabrican. Los
casos de error viven solo en `tests/domain/test_accuracy.py`, con respuestas sintéticas.
"""

import pytest

from posiq.domain.accuracy import evaluar_exactitud, expresiones_a_revisar, recuento
from posiq.domain.accuracy_schemas import AccionMitigacion, HallazgoExactitud
from posiq.domain.schemas import BriefSummary
from tests.golden.conftest import STUDY_ID, Kit

ALBORADA = "clinica-alborada-vision"


@pytest.fixture(scope="module")
def exactitud(
    kit: Kit, alborada_brief: BriefSummary
) -> tuple[HallazgoExactitud, list[AccionMitigacion]]:
    brand = next(b for b in kit.brands if b.id == ALBORADA)
    return evaluar_exactitud(STUDY_ID, brand, alborada_brief, kit.runs, marcas=kit.brands)


def test_alborada_cero_inexactitudes(
    exactitud: tuple[HallazgoExactitud, list[AccionMitigacion]],
) -> None:
    hallazgo, acciones = exactitud
    assert len(hallazgo.afirmaciones) == 276
    assert hallazgo.n_inexactitudes == 0 and acciones == []
    assert (
        hallazgo.n_correctas,
        hallazgo.n_incorrectas,
        hallazgo.n_no_verificables,
        hallazgo.n_riesgo_regulatorio,
    ) == (62, 0, 193, 21)
    assert len(hallazgo.evaluation_ids) == 193


def test_alborada_por_tipo_y_estado(
    exactitud: tuple[HallazgoExactitud, list[AccionMitigacion]],
) -> None:
    hallazgo, _ = exactitud
    no_cero = {t: {e: n for e, n in d.items() if n} for t, d in recuento(hallazgo).items()}
    assert no_cero == {
        "servicio": {"correcta": 62, "no_verificable": 131, "riesgo_regulatorio": 2},
        "sede": {},
        "profesional": {"no_verificable": 62},
        "precio": {},
        "resultado_clinico": {},
        "otro": {"riesgo_regulatorio": 19},
    }
    assert expresiones_a_revisar(hallazgo) == {"la opción más recomendada / recomendable": 21}


def test_alborada_fragmentos_literales_del_kit(
    kit: Kit, exactitud: tuple[HallazgoExactitud, list[AccionMitigacion]]
) -> None:
    hallazgo, _ = exactitud
    respuestas = {r.id: r.texto_respuesta for r in kit.runs}
    for a in hallazgo.afirmaciones:
        assert a.texto in respuestas[a.run_id]
        assert a.evaluation_id == f"{a.run_id}:{ALBORADA}" and a.origen == "reglas"

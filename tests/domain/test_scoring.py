import pytest

from posiq.domain.schemas import Evaluation
from posiq.domain.scoring import (
    QUALITY_BY_TYPE,
    SCORE_VERSION,
    WEIGHTS,
    appearance_quality,
    score_citacion,
)
from tests.domain.factories import evaluation, prompt, run, source

PROMPTS = [prompt("P-esp"), prompt("P-asi", instanciacion="marca")]


def _runs(n: int, prompt_id: str = "P-esp", **kw: object) -> list:  # type: ignore[type-arg]
    return [run(id=f"EJ-{i}", prompt_id=prompt_id, **kw) for i in range(n)]


def _evals(n: int, **kw: object) -> list[Evaluation]:
    return [evaluation(run_id=f"EJ-{i}", **kw) for i in range(n)]


def test_pesos_suman_100() -> None:
    assert sum(WEIGHTS.values()) == 100
    assert SCORE_VERSION == "1.0"


def test_score_maximo_100() -> None:
    s = score_citacion(
        _evals(4, tipo_fuente="Ranking / institución"), _runs(4), PROMPTS, "alborada"
    )
    assert (s.aparicion, s.posicion, s.fuerza, s.calidad_fuente, s.score) == (30, 20, 30, 20, 100)
    assert s.n_evaluaciones == 4


def test_score_minimo_0() -> None:
    s = score_citacion(_evals(4, aparece=False), _runs(4), PROMPTS, "alborada")
    assert s.score == 0 and s.n_evaluaciones == 4


def test_sin_datos_no_es_cero() -> None:
    s = score_citacion([], [], PROMPTS, "alborada")
    assert s.score is None and s.n_evaluaciones == 0


def test_solo_cuentan_prompts_espontaneos() -> None:
    s = score_citacion(_evals(3), _runs(3, prompt_id="P-asi"), PROMPTS, "alborada")
    assert s.n_evaluaciones == 0 and s.score is None


def test_ignora_marcas_no_elegibles_y_filtra_motor() -> None:
    runs = _runs(2, marcas=["otra"])
    assert score_citacion(_evals(2), runs, PROMPTS, "alborada").n_evaluaciones == 0
    runs = [run(id="EJ-0", prompt_id="P-esp"), run(id="EJ-1", prompt_id="P-esp", motor="Gemini")]
    s = score_citacion(_evals(2), runs, PROMPTS, "alborada", motor="Gemini")
    assert s.n_evaluaciones == 1 and s.motor == "Gemini"


def test_componentes_intermedios() -> None:
    # 2 de 4 aparecen: posiciones 1 y 4, fuerzas 3 y 1, fuentes Medio y Sin fuente.
    evals = [
        evaluation(run_id="EJ-0", posicion=1, fuerza=3, tipo_fuente="Medio"),
        evaluation(run_id="EJ-1", posicion=4, fuerza=1, tipo_fuente="Sin fuente"),
        evaluation(run_id="EJ-2", aparece=False),
        evaluation(run_id="EJ-3", aparece=False),
    ]
    s = score_citacion(evals, _runs(4), PROMPTS, "alborada")
    assert s.aparicion == 15
    assert s.posicion == pytest.approx(20 * (3 + 1) / 4 / 3, abs=0.01)
    assert s.fuerza == pytest.approx(30 * (4 / 4) / 3, abs=0.01)
    assert s.calidad_fuente == pytest.approx(20 * 0.5 * (0.9 + 0.2) / 2, abs=0.01)


def test_fuerza_negativa_no_resta() -> None:
    s = score_citacion(_evals(2, fuerza=-1, sentimiento="negativo"), _runs(2), PROMPTS, "alborada")
    assert s.fuerza == 0


def test_calidad_sin_tipo_resuelto_usa_fuentes_de_la_ejecucion() -> None:
    e = evaluation()
    assert appearance_quality(e, run(fuentes=[source(), source("x.example", "Medio")])) == 0.95
    assert appearance_quality(e, run()) == QUALITY_BY_TYPE["Sin fuente"]
    assert appearance_quality(evaluation(tipo_fuente="Web propia"), run()) == 0.7

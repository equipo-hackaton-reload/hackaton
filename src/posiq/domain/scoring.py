"""Score de Citación (0-100) de la metodología GEO del kit (§7), solo sobre prompts espontáneos.

Población: evaluaciones de la marca en ejecuciones cuyo prompt es espontáneo (`generico` o
`ciudad`) y en las que la marca está en `marcas_a_evaluar`. Sea N su número y A las que tienen
`aparece`. Con N = 0 no hay score (sin datos), nunca 0.

    tasa            = A / N
    aparicion       = 30 × tasa
    posicion        = 20 × media(peso_posicion) / 3
                      peso: 1.ª = 3 · 2.ª-3.ª = 2 · 4.ª o más = 1 · no aparece = 0 (media sobre N)
    fuerza          = 30 × max(0, media(fuerza)) / 3
                      fuerza del kit −1..3 con 0 si no aparece (media sobre N; si la media es
                      negativa, el componente vale 0)
    calidad_fuente  = 20 × tasa × media(calidad de cada aparición)
                      calidad de una aparición = QUALITY_BY_TYPE[tipo_fuente] si está resuelto;
                      si no, la media de `calidad` del catálogo de las fuentes citadas en la
                      ejecución; si la ejecución no citó fuentes, la de «Sin fuente» (0,2)
    score           = aparicion + posicion + fuerza + calidad_fuente   (redondeado a 2 decimales)
"""

from statistics import fmean
from typing import Final

from posiq.domain.schemas import (
    ESPONTANEAS,
    Evaluation,
    Motor,
    PromptInstance,
    Run,
    ScoreBreakdown,
    TipoFuente,
)

SCORE_VERSION: Final = "1.0"

WEIGHTS: Final[dict[str, int]] = {
    "aparicion": 30,
    "posicion": 20,
    "fuerza": 30,
    "calidad_fuente": 20,
}
MAX_PESO_POSICION: Final = 3
MAX_FUERZA: Final = 3

QUALITY_BY_TYPE: Final[dict[TipoFuente, float]] = {
    "Ranking / institución": 1.0,
    "Medio": 0.9,
    "Web propia": 0.7,
    "Directorio / comparador": 0.6,
    "Plataforma de reseñas": 0.6,
    "Red social / foro": 0.4,
    "Sin fuente": 0.2,
}


def appearance_quality(evaluation: Evaluation, run: Run) -> float:
    """Calidad de la fuente que apoya una aparición (ver docstring del módulo)."""
    if evaluation.tipo_fuente is not None:
        return QUALITY_BY_TYPE[evaluation.tipo_fuente]
    calidades = [s.calidad for s in run.fuentes if s.calidad is not None]
    return fmean(calidades) if calidades else QUALITY_BY_TYPE["Sin fuente"]


def spontaneous_population(
    evaluations: list[Evaluation],
    runs: list[Run],
    prompts: list[PromptInstance],
    brand_id: str,
    motor: Motor | None = None,
) -> list[tuple[Evaluation, Run]]:
    """Evaluaciones elegibles de la marca en ejecuciones espontáneas (y del motor, si se da)."""
    runs_by_id = {r.id: r for r in runs}
    espontaneos = {p.id for p in prompts if p.instanciacion in ESPONTANEAS}
    population: list[tuple[Evaluation, Run]] = []
    for e in evaluations:
        run = runs_by_id.get(e.run_id)
        if (
            e.brand_id == brand_id
            and run is not None
            and run.prompt_id in espontaneos
            and brand_id in run.marcas_a_evaluar
            and (motor is None or run.motor == motor)
        ):
            population.append((e, run))
    return population


def score_citacion(
    evaluations: list[Evaluation],
    runs: list[Run],
    prompts: list[PromptInstance],
    brand_id: str,
    motor: Motor | None = None,
) -> ScoreBreakdown:
    """Score de Citación de `brand_id` sobre prompts espontáneos (fórmula en el módulo)."""
    population = spontaneous_population(evaluations, runs, prompts, brand_id, motor)
    n = len(population)
    if n == 0:
        return ScoreBreakdown(
            brand_id=brand_id, motor=motor, n_evaluaciones=0, score_version=SCORE_VERSION
        )

    evals = [e for e, _ in population]
    tasa = sum(e.aparece for e in evals) / n
    aparicion = WEIGHTS["aparicion"] * tasa
    posicion = WEIGHTS["posicion"] * fmean(e.peso_posicion for e in evals) / MAX_PESO_POSICION
    fuerza = WEIGHTS["fuerza"] * max(0.0, fmean(e.fuerza for e in evals)) / MAX_FUERZA
    calidades = [appearance_quality(e, r) for e, r in population if e.aparece]
    calidad_fuente = WEIGHTS["calidad_fuente"] * tasa * fmean(calidades) if calidades else 0.0

    return ScoreBreakdown(
        brand_id=brand_id,
        motor=motor,
        n_evaluaciones=n,
        aparicion=round(aparicion, 2),
        posicion=round(posicion, 2),
        fuerza=round(fuerza, 2),
        calidad_fuente=round(calidad_fuente, 2),
        score=round(aparicion + posicion + fuerza + calidad_fuente, 2),
        score_version=SCORE_VERSION,
    )

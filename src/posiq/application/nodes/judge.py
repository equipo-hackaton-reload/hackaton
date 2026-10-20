"""Nodo `judge`: evalúa cada marca del mercado confirmado en cada ejecución que la pide evaluar.

El juez se construye aquí (`judge_factory`) porque necesita el mercado confirmado y el presupuesto
del estudio. `aevaluate_many` limita la concurrencia con su semáforo. Si falta la clave del juez,
se usa la detección por reglas del dominio (`evaluation_from_detection`) y se anota en `errores`.
"""

from typing import Any

from posiq.adapters.errors import MissingCredentialError
from posiq.application.deps import Deps, cost_update, db, persist_traces, study_budget
from posiq.application.state import StudyState
from posiq.domain.detection import detect_in_run, evaluation_from_detection
from posiq.domain.schemas import Brand, Evaluation, Run


def judge_pairs(runs: list[Run], marcas: list[Brand]) -> list[tuple[Run, Brand]]:
    return [(r, b) for r in runs for b in marcas if b.id in r.marcas_a_evaluar]


def _por_reglas(pairs: list[tuple[Run, Brand]], marcas: list[Brand]) -> list[Evaluation]:
    detecciones = {r.id: detect_in_run(r, marcas) for r in {r.id: r for r, _ in pairs}.values()}
    return [evaluation_from_detection(r, b, detecciones[r.id].get(b.id)) for r, b in pairs]


async def judge(state: StudyState, deps: Deps) -> dict[str, Any]:
    marcas = state["market"].marcas
    pairs = judge_pairs(state["runs"], marcas)
    juez = deps.judge_factory(state["market"], study_budget(deps, state))
    errores: list[str] = []
    try:
        evaluations = await juez.aevaluate_many(pairs)
    except MissingCredentialError as exc:
        evaluations = _por_reglas(pairs, marcas)
        errores.append(f"judge: {exc} Evaluaciones solo por reglas (aparición y posición).")

    await db(deps.repo.save_evaluations, state["study_id"], evaluations)
    nuevas = list(juez.traces)
    await persist_traces(deps, state, nuevas)
    return {"evaluations": evaluations, "errores": errores, **cost_update(state, nuevas)}

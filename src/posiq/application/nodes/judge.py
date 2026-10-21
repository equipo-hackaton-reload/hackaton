"""Nodo `judge`: evalúa cada marca del mercado confirmado en cada ejecución que la pide evaluar.

El juez se construye aquí (`judge_factory`) porque necesita el mercado confirmado y el presupuesto
del estudio. `aevaluate_many` limita la concurrencia con su semáforo. Se evalúa solo por reglas
del dominio (`evaluation_from_detection`: aparición y posición) en dos casos:
- `JUDGE_PROVIDER=reglas`: elección explícita para ahorrar las llamadas del juez; no es un error.
- Falta la clave del juez: se anota en `errores`.
En los dos, `juez` queda en `"reglas"` y la propuesta lo declara entre sus limitaciones.
"""

from typing import Any

from posiq.adapters.errors import MissingCredentialError
from posiq.application.deps import (
    Deps,
    adjuntar_trazas,
    cost_update,
    db,
    persist_traces,
    study_budget,
)
from posiq.application.state import StudyState
from posiq.domain.detection import detect_in_run, evaluation_from_detection
from posiq.domain.schemas import Brand, Evaluation, Run, Trace

JUEZ_REGLAS = "reglas"


def trazas_del_juez(juez: object) -> list[Trace]:
    """Trazas del juez y de los que usa por dentro (su `fallback`, los `jueces` de un consenso).

    El fallback de DeepSeek lleva sus propias trazas: sin esto, sus llamadas se pagaban y
    contaban en el presupuesto del nodo, pero no quedaban en el estudio.
    """
    trazas: list[Trace] = []
    vistas: set[int] = set()
    visitados: set[int] = set()

    def visita(j: object | None) -> None:
        if j is None or id(j) in visitados:
            return
        visitados.add(id(j))
        for t in getattr(j, "traces", []):
            if id(t) not in vistas:
                vistas.add(id(t))
                trazas.append(t)
        visita(getattr(j, "fallback", None))
        for interno in getattr(j, "jueces", []):
            visita(interno)

    visita(juez)
    return trazas


def judge_pairs(runs: list[Run], marcas: list[Brand]) -> list[tuple[Run, Brand]]:
    return [(r, b) for r in runs for b in marcas if b.id in r.marcas_a_evaluar]


def _por_reglas(pairs: list[tuple[Run, Brand]], marcas: list[Brand]) -> list[Evaluation]:
    detecciones = {r.id: detect_in_run(r, marcas) for r in {r.id: r for r, _ in pairs}.values()}
    return [evaluation_from_detection(r, b, detecciones[r.id].get(b.id)) for r, b in pairs]


async def judge(state: StudyState, deps: Deps) -> dict[str, Any]:
    marcas = state["market"].marcas
    pairs = judge_pairs(state["runs"], marcas)
    errores: list[str] = []
    nuevas: list[Trace] = []
    if deps.settings.judge_provider == "reglas":
        evaluations, nombre = _por_reglas(pairs, marcas), JUEZ_REGLAS
    else:
        juez = deps.judge_factory(state["market"], study_budget(deps, state))
        nombre = juez.name
        try:
            evaluations = await juez.aevaluate_many(pairs)
        except MissingCredentialError as exc:
            evaluations, nombre = _por_reglas(pairs, marcas), JUEZ_REGLAS
            errores.append(f"judge: {exc} Evaluaciones solo por reglas (aparición y posición).")
        except BaseException as exc:  # lo ya pagado (Jev y fallback) cuenta aunque el nodo falle
            adjuntar_trazas(exc, trazas_del_juez(juez))
            raise
        nuevas = trazas_del_juez(juez)

    await db(deps.repo.save_evaluations, state["study_id"], evaluations)
    await persist_traces(deps, state, nuevas)
    return {
        "evaluations": evaluations,
        "juez": nombre,
        "errores": errores,
        **cost_update(state, nuevas),
    }

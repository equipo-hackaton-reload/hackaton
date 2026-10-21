"""Nodo `plan`: plan de acción a partir de los hallazgos, validado contra el brief.

El LLM recibe las cifras ya calculadas (resumen de métricas y hallazgos). Si el plan incumple el
brief (`validate_plan_against_brief`) o enlaza hallazgos que no existen, se reintenta una vez con
las violaciones en el `state`; si persisten, el plan se queda y las violaciones van a `errores`
para que la persona las vea en la revisión.

Junto al plan van dos ayudas para la revisión (`plan_checks`), que no bloquean nada:
- `simulacion`: impacto proyectado sobre el Score de Citación (`domain.simulation`, código puro).
- `calidad_plan`: juicio de PlanGuard por acción. Si no hay claves de juez o la API falla, queda en
  None y se anota; solo `BudgetExceeded` para el estudio.
"""

import logging
from typing import Any

from posiq.adapters.budget import BudgetExceeded
from posiq.adapters.errors import MissingCredentialError
from posiq.application.deps import (
    Deps,
    cost_update,
    db,
    dump,
    persist_traces,
    structured,
    study_budget,
)
from posiq.application.state import StudyState
from posiq.domain.schemas import (
    BriefSummary,
    Finding,
    Metrics,
    Plan,
    Trace,
    validate_plan_against_brief,
)
from posiq.domain.simulation import simulate_plan

log = logging.getLogger(__name__)


def metrics_summary(metrics: Metrics) -> dict[str, Any]:
    """Lo que un prompt necesita de las métricas: scores, ranking y visibilidad de la marca foco."""
    foco = metrics.marca_foco_id
    return {
        "marca_foco_id": foco,
        "lider_id": metrics.lider_id,
        "comparado_con": metrics.comparado_con,
        "score_global": dump(metrics.score_global),
        "scores": dump(metrics.scores),
        "ranking": metrics.ranking,
        "n_ejecuciones": metrics.n_ejecuciones,
        "visibilidad_foco": dump([c for c in metrics.visibilidad if c.brand_id == foco]),
        "brecha_fuentes": dump(metrics.brecha_fuentes),
    }


def plan_violations(plan: Plan, brief: BriefSummary, findings: list[Finding]) -> list[str]:
    violaciones = validate_plan_against_brief(plan, brief)
    ids = {f.id for f in findings}
    for accion in plan.acciones:
        sueltos = sorted(set(accion.finding_ids) - ids)
        if sueltos:
            violaciones.append(f"acción {accion.id} enlaza hallazgos inexistentes: {sueltos}")
    return violaciones


def own_plan(plan: Plan, study_id: str) -> Plan:
    return plan if plan.study_id == study_id else plan.model_copy(update={"study_id": study_id})


async def plan_checks(state: StudyState, deps: Deps, plan: Plan) -> dict[str, Any]:
    """Simulación del impacto y calidad del plan, con las trazas nuevas de PlanGuard.

    `state["traces"]` debe incluir ya las trazas de este nodo, para que el presupuesto las cuente.
    Devuelve `simulacion`, `calidad_plan`, `traces` (solo las nuevas) y `errores`.
    """
    simulacion = simulate_plan(plan, state["metrics"], state["findings"])
    if deps.plan_guard_factory is None:
        return {"simulacion": simulacion, "calidad_plan": None, "traces": [], "errores": []}

    budget = study_budget(deps, state)
    antes = len(budget.traces)
    guard = deps.plan_guard_factory(budget)
    errores: list[str] = []
    try:
        calidad = await guard.aassess(plan, state["findings"], state["brief"])
    except BudgetExceeded:
        raise  # el presupuesto sí para el estudio
    except MissingCredentialError as exc:
        calidad = None
        errores.append(f"plan_guard: {exc} Calidad del plan sin evaluar.")
    except Exception as exc:  # PlanGuard orienta la revisión: un fallo de la API no la bloquea
        log.warning("plan_guard falló en el estudio %s", state["study_id"], exc_info=True)
        calidad = None
        errores.append(f"plan_guard: {type(exc).__name__}: {exc}. Calidad del plan sin evaluar.")
    nuevas: list[Trace] = budget.traces[antes:]
    return {"simulacion": simulacion, "calidad_plan": calidad, "traces": nuevas, "errores": errores}


async def plan(state: StudyState, deps: Deps) -> dict[str, Any]:
    sid = state["study_id"]
    brief, findings = state["brief"], state["findings"]
    payload: dict[str, Any] = {
        "brief": dump(brief),
        "hallazgos": dump(findings),
        "metricas": metrics_summary(state["metrics"]),
        "diferencia_anterior": dump(state.get("metrics_delta")),
        "market": dump(state["market"]),
    }
    propuesto, trace = await structured(deps, state, Plan, "plan.v1", payload)
    propuesto = own_plan(propuesto, sid)
    traces = [trace]
    violaciones = plan_violations(propuesto, brief, findings)
    if violaciones:
        retry_state: StudyState = {**state, "traces": [*state.get("traces", []), trace]}
        propuesto, trace = await structured(
            deps,
            retry_state,
            Plan,
            "plan.v1",
            {**payload, "plan_anterior": dump(propuesto), "violaciones": violaciones},
        )
        propuesto = own_plan(propuesto, sid)
        traces.append(trace)
        violaciones = plan_violations(propuesto, brief, findings)

    checks = await plan_checks(
        {**state, "traces": [*state.get("traces", []), *traces]}, deps, propuesto
    )
    traces.extend(checks["traces"])

    await db(deps.repo.save_plan, sid, propuesto)
    study = await db(deps.repo.get_study, sid)
    await db(deps.repo.save_study, study.model_copy(update={"estado": "esperando_revision_plan"}))
    await persist_traces(deps, state, traces)
    return {
        "plan": propuesto,
        "plan_violaciones": violaciones,
        "simulacion": checks["simulacion"],
        "calidad_plan": checks["calidad_plan"],
        "revision_pendiente": "plan",
        "errores": [f"plan: {v}" for v in violaciones] + checks["errores"],
        **cost_update(state, traces),
    }

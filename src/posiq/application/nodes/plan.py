"""Nodo `plan`: plan de acción a partir de los hallazgos, validado contra el brief.

El LLM recibe las cifras ya calculadas (resumen de métricas y hallazgos). Si el plan incumple el
brief (`validate_plan_against_brief`) o enlaza hallazgos que no existen, se reintenta una vez con
las violaciones en el `state`; si persisten, el plan se queda y las violaciones van a `errores`
para que la persona las vea en la revisión.
"""

from typing import Any

from posiq.application.deps import Deps, cost_update, db, dump, persist_traces, structured
from posiq.application.state import StudyState
from posiq.domain.schemas import BriefSummary, Finding, Metrics, Plan, validate_plan_against_brief


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

    await db(deps.repo.save_plan, sid, propuesto)
    study = await db(deps.repo.get_study, sid)
    await db(deps.repo.save_study, study.model_copy(update={"estado": "esperando_revision_plan"}))
    await persist_traces(deps, state, traces)
    return {
        "plan": propuesto,
        "plan_violaciones": violaciones,
        "revision_pendiente": "plan",
        "errores": [f"plan: {v}" for v in violaciones],
        **cost_update(state, traces),
    }

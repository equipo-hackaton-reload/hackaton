"""Nodo `write`: redacta la propuesta (las 10 secciones del entregable).

El LLM redacta los textos; las cifras y los datos estructurados se sobrescriben después con lo que
calculó el código: métricas, ranking, hallazgos, plan aprobado, objetivos, presupuesto y contexto
(motores, origen de los datos y si son sintéticos). Así ninguna cifra de la propuesta sale del LLM.
"""

from datetime import UTC, datetime
from typing import Any

from posiq.application.deps import Deps, cost_update, db, dump, persist_traces, structured
from posiq.application.nodes.plan import metrics_summary
from posiq.application.state import StudyState
from posiq.domain.schemas import Proposal

LIMITACION_KIT = (
    "Datos sintéticos del kit del reto (ejecuciones grabadas), no mediciones reales de los motores."
)


def contexto(state: StudyState) -> dict[str, Any]:
    kit = state["modo"] == "kit"
    return {
        "marca": state["brief"].marca,
        "sector": state["brief"].sector,
        "motores": sorted({r.motor for r in state["runs"]}),
        "origen_datos": "kit" if kit else "api",
        "datos_sinteticos": kit,
    }


def enforce_figures(proposal: Proposal, state: StudyState) -> Proposal:
    """La propuesta del LLM con los datos calculados por el código en su sitio."""
    plan, metrics = state["plan"], state["metrics"]
    data = proposal.model_dump(mode="json")
    ctx = contexto(state)
    limitaciones = list(data["contexto"].get("limitaciones") or [])
    if ctx["datos_sinteticos"] and LIMITACION_KIT not in limitaciones:
        limitaciones.insert(0, LIMITACION_KIT)
    data["study_id"] = state["study_id"]
    data["contexto"] = {
        **ctx,
        "fecha": datetime.now(UTC).isoformat(),
        "limitaciones": limitaciones or ["Sin limitaciones declaradas."],
    }
    data["diagnostico"]["metrics"] = dump(metrics)
    data["competencia"]["ranking"] = metrics.ranking
    data["hallazgos"] = dump(state["findings"])
    data["plan"] = dump(plan)
    data["estrategia"]["objetivos"] = dump(plan.objetivos)
    data["hoja_ruta"]["presupuesto_eur"] = plan.presupuesto_estimado_eur
    return Proposal.model_validate(data)


async def write(state: StudyState, deps: Deps) -> dict[str, Any]:
    sid = state["study_id"]
    payload = {
        "brief": dump(state["brief"]),
        "market": dump(state["market"]),
        "contexto": contexto(state),
        "metricas": metrics_summary(state["metrics"]),
        "diferencia_anterior": dump(state.get("metrics_delta")),
        "hallazgos": dump(state["findings"]),
        "plan": dump(state["plan"]),
        "errores": state.get("errores", []),
    }
    borrador, trace = await structured(deps, state, Proposal, "write.v1", payload)
    proposal = enforce_figures(borrador, state)

    await db(deps.repo.save_proposal, sid, proposal)
    study = await db(deps.repo.get_study, sid)
    await db(deps.repo.save_study, study.model_copy(update={"estado": "completado"}))
    await persist_traces(deps, state, [trace])
    return {"proposal": proposal, "revision_pendiente": "none", **cost_update(state, [trace])}

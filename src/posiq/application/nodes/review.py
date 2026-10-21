"""Nodos de revisión humana: el grafo se detiene con `interrupt()` hasta `Command(resume=...)`.

Al reanudar, LangGraph vuelve a ejecutar el nodo desde el principio y `interrupt()` devuelve el
valor del resume, así que antes de `interrupt()` no hay efectos.

- `competidores`: el resume es un `Market` (editado o el mismo) o `None`/`{"aprobado": true}` para
  aceptar el propuesto. Queda `confirmado_por_humano=True`.
- `plan`: el resume es un `Plan` editado o `None`/`{"aprobado": true}` para aprobar el propuesto. Un
  plan editado se vuelve a validar contra el brief (las violaciones van a `errores`) y se recalculan
  su simulación, sus escenarios y su calidad.

`parse_*` validan el payload y los usa también la API, para rechazar un resume inválido antes de
reanudar el grafo.
"""

from typing import Any

from langgraph.types import interrupt

from posiq.application.deps import Deps, cost_update, db, dump, persist_traces
from posiq.application.nodes.market import focus_brand_id
from posiq.application.nodes.plan import own_plan, plan_checks, plan_violations
from posiq.application.state import StudyState
from posiq.domain.metrics import resolve_brand
from posiq.domain.schemas import Market, Plan


def _aprobado(payload: Any) -> bool:
    return payload is None or (
        isinstance(payload, dict) and set(payload) == {"aprobado"} and payload["aprobado"] is True
    )


def parse_market(payload: Any, state: StudyState) -> Market:
    """Mercado confirmado. `ValueError` si no valida o no incluye la marca del brief."""
    if not _aprobado(payload) and not isinstance(payload, dict):
        raise ValueError("el resume de competidores espera un Market")
    market = (
        state["market"]
        if _aprobado(payload)
        else Market.model_validate({**payload, "confirmado_por_humano": True})
    )
    resolve_brand(state["brief"].marca, market)
    return market.model_copy(update={"confirmado_por_humano": True})


def parse_plan(payload: Any, state: StudyState) -> Plan:
    if _aprobado(payload):
        return state["plan"]
    if not isinstance(payload, dict):
        raise ValueError('el resume del plan espera un Plan o {"aprobado": true}')
    return own_plan(Plan.model_validate(payload), state["study_id"])


async def review_competidores(state: StudyState, deps: Deps) -> dict[str, Any]:
    payload = interrupt({"revision": "competidores", "market": dump(state["market"])})
    market = parse_market(payload, state)
    study = await db(deps.repo.get_study, state["study_id"])
    await db(
        deps.repo.save_study,
        study.model_copy(
            update={"brand_id": focus_brand_id(state["brief"].marca, market), "estado": "en_curso"}
        ),
    )
    return {"market": market, "revision_pendiente": "none"}


async def review_plan(state: StudyState, deps: Deps) -> dict[str, Any]:
    payload = interrupt(
        {
            "revision": "plan",
            "plan": dump(state["plan"]),
            "violaciones": state.get("plan_violaciones", []),
        }
    )
    plan = parse_plan(payload, state)
    update: dict[str, Any] = {"plan": plan, "revision_pendiente": "none"}
    if not _aprobado(payload):
        violaciones = plan_violations(plan, state["brief"], state["findings"])
        # Simulación, escenarios y calidad describían el plan propuesto: se recalculan.
        checks = await plan_checks(state, deps, plan)
        update["plan_violaciones"] = violaciones
        update["simulacion"] = checks["simulacion"]
        update["escenarios"] = checks["escenarios"]
        update["calidad_plan"] = checks["calidad_plan"]
        update["errores"] = [f"plan editado: {v}" for v in violaciones] + checks["errores"]
        update.update(cost_update(state, checks["traces"]))
        await persist_traces(deps, state, checks["traces"])
    await db(deps.repo.save_plan, state["study_id"], plan)
    study = await db(deps.repo.get_study, state["study_id"])
    await db(deps.repo.save_study, study.model_copy(update={"estado": "en_curso"}))
    return update

"""Nodo `intake`: el texto del brief a una `BriefSummary` estructurada."""

from typing import Any

from posiq.application.deps import Deps, cost_update, db, persist_traces, structured
from posiq.application.state import StudyState
from posiq.domain.schemas import BriefSummary
from posiq.domain.text import slugify

# v2 extrae además el posicionamiento y los atributos deseados (vacíos si el brief no los trae).
PROMPT = "intake.v2"


async def intake(state: StudyState, deps: Deps) -> dict[str, Any]:
    brief, trace = await structured(
        deps, state, BriefSummary, PROMPT, {"brief": state["brief_texto"]}
    )
    study = await db(deps.repo.get_study, state["study_id"])
    # brand_id provisional: `market` lo sustituye por el id de la marca en el mercado.
    await db(
        deps.repo.save_study,
        study.model_copy(update={"brief": brief, "brand_id": slugify(brief.marca)}),
    )
    await persist_traces(deps, state, [trace])
    return {"brief": brief, **cost_update(state, [trace])}

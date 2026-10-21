"""Nodo `prompts`: el banco de prompts del estudio, ya instanciado.

En modo kit es el banco del kit instanciado tal como se ejecutó (`kit_loader`), sin llamar al LLM:
la demo base no depende de ninguna API. En modo real lo genera el LLM (`PromptSet`, Zona E) a partir
del banco de plantillas del kit. Si el estado ya trae prompts (una re-medición), se reutilizan.
"""

import importlib
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from posiq.application.deps import Deps, cost_update, dump, persist_traces, structured
from posiq.application.kit import load_kit
from posiq.application.state import StudyState
from posiq.domain.schemas import PromptInstance


def prompt_set_schema() -> type[BaseModel]:
    """`posiq.prompts.PromptSet` (Zona E). Se importa al usarlo: el modo kit no lo necesita."""
    return cast(type[BaseModel], importlib.import_module("posiq.prompts").PromptSet)


async def prompts(state: StudyState, deps: Deps) -> dict[str, Any]:
    if state.get("prompts"):
        # Re-medición: el banco del estudio original (sembrado por `prepare_remeasure`). Volver a
        # generarlo cambiaría la huella del banco y las mediciones no serían comparables.
        return {}
    kit = load_kit(str(Path(deps.settings.kit_dir).resolve()))
    if state["modo"] == "kit":
        return {"prompts": list(kit.prompts)}

    prompt_set, trace = await structured(
        deps,
        state,
        prompt_set_schema(),
        "prompts.v1",
        {
            "brief_summary": dump(state["brief"]),
            "market": dump(state["market"]),
            "banco_plantillas": dump(kit.templates),
        },
    )
    instancias: list[PromptInstance] = list(prompt_set.prompts)  # type: ignore[attr-defined]
    await persist_traces(deps, state, [trace])
    return {"prompts": instancias, **cost_update(state, [trace])}

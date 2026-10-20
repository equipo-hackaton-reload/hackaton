"""Nodo `market`: propone el mercado (foco, líder y competidores) para la revisión humana.

En modo kit los candidatos son las marcas del kit que las ejecuciones piden evaluar, y cada marca
que el LLM proponga y coincida por nombre o alias con un candidato toma el id del kit: así casa con
`Run.marcas_a_evaluar`. En modo real no hay candidatos.
"""

from pathlib import Path
from typing import Any

from posiq.application.deps import Deps, cost_update, db, dump, persist_traces, structured
from posiq.application.kit import load_kit
from posiq.application.state import StudyState
from posiq.domain.metrics import resolve_brand
from posiq.domain.schemas import Brand, Market
from posiq.domain.text import fold, slugify


def _names(brand: Brand) -> set[str]:
    return {fold(n) for n in [brand.nombre, brand.id, *brand.aliases] if n.strip()}


def reconcile(market: Market, candidatos: list[Brand]) -> Market:
    """Ids del kit para las marcas que coinciden con un candidato; descarta las repetidas."""
    marcas: list[Brand] = []
    vistos: set[str] = set()
    for brand in market.marcas:
        match = next((c for c in candidatos if _names(c) & _names(brand)), None)
        if match is not None:
            brand = brand.model_copy(
                update={
                    "id": match.id,
                    "aliases": sorted(set(brand.aliases) | set(match.aliases)),
                    "dominio": brand.dominio or match.dominio,
                }
            )
        if brand.id not in vistos:
            vistos.add(brand.id)
            marcas.append(brand)
    return Market(marcas=marcas, confirmado_por_humano=False)


def focus_brand_id(brief_marca: str, market: Market) -> str:
    try:
        return resolve_brand(brief_marca, market).id
    except ValueError:
        return slugify(brief_marca)


async def market(state: StudyState, deps: Deps) -> dict[str, Any]:
    brief = state["brief"]
    candidatos = (
        load_kit(str(Path(deps.settings.kit_dir).resolve())).brands_in_runs()
        if state["modo"] == "kit"
        else []
    )
    propuesto, trace = await structured(
        deps, state, Market, "market.v1", {"brief": dump(brief), "candidatos": dump(candidatos)}
    )
    mercado = reconcile(propuesto, candidatos)

    study = await db(deps.repo.get_study, state["study_id"])
    await db(
        deps.repo.save_study,
        study.model_copy(
            update={
                "brand_id": focus_brand_id(brief.marca, mercado),
                "estado": "esperando_revision_competidores",
            }
        ),
    )
    await persist_traces(deps, state, [trace])
    return {"market": mercado, "revision_pendiente": "competidores", **cost_update(state, [trace])}

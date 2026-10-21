"""Nodo `write`: redacta la propuesta (las 10 secciones del entregable).

El LLM devuelve solo ProposalDraft. El código compone métricas, ranking, hallazgos, plan aprobado,
objetivos, presupuesto, hitos y contexto desde el estado verificado del estudio.
"""

from datetime import UTC, datetime
from typing import Any

from posiq.adapters.llm.fixture import FixtureJudge
from posiq.application.deps import Deps, cost_update, db, dump, persist_traces, structured
from posiq.application.nodes.judge import JUEZ_REGLAS
from posiq.application.nodes.plan import metrics_summary
from posiq.application.schemas_draft import ProposalDraft
from posiq.application.state import StudyState
from posiq.domain.schemas import (
    Competencia,
    Contexto,
    Diagnostico,
    Estrategia,
    Hito,
    HojaRuta,
    Medicion,
    Proposal,
)

LIMITACION_KIT = (
    "Datos sintéticos del kit del reto (ejecuciones grabadas), no mediciones reales de los motores."
)
LIMITACION_REGLAS = (
    "Menciones evaluadas solo por reglas (aparición y posición), sin juez LLM: el tipo de mención, "
    "el sentimiento y la fuerza de la recomendación no se han juzgado."
)
# Jueces que solo detectan por reglas: el del nodo `judge` y el de la demo sin claves.
JUECES_POR_REGLAS = frozenset({JUEZ_REGLAS, FixtureJudge.name})


def contexto(state: StudyState) -> dict[str, Any]:
    kit = state["modo"] == "kit"
    return {
        "marca": state["brief"].marca,
        "sector": state["brief"].sector,
        "motores": sorted({r.motor for r in state["runs"]}),
        "origen_datos": "kit" if kit else "api",
        "datos_sinteticos": kit,
    }


def assemble_proposal(draft: ProposalDraft, state: StudyState) -> Proposal:
    """Compone la propuesta sin pedir al LLM que replique contratos o calcule cifras."""
    plan, metrics = state["plan"], state["metrics"]
    findings = state["findings"]
    if set(draft.interpretacion_hallazgos) != {f.id for f in findings}:
        raise ValueError(
            "el borrador debe interpretar exactamente los ids de hallazgos del estudio"
        )
    limitaciones = list(draft.supuestos)
    if state.get("juez") in JUECES_POR_REGLAS:
        limitaciones.insert(0, LIMITACION_REGLAS)
    if state["modo"] == "kit":
        limitaciones.insert(0, LIMITACION_KIT)
    hitos = []
    semana = 0
    responsabilidades: dict[str, list[str]] = {}
    for fase in plan.fases:
        semana += fase.semanas
        hitos.append(Hito(semana=semana, descripcion=f"Fin de {fase.nombre}"))
        for accion in fase.acciones:
            responsabilidades.setdefault(accion.responsable, []).append(accion.id)
    interpretaciones = "\n".join(
        f"{f.titulo}: {draft.interpretacion_hallazgos[f.id]}" for f in findings
    )
    return Proposal(
        study_id=state["study_id"],
        resumen_ejecutivo=draft.resumen_ejecutivo,
        contexto=Contexto(
            **contexto(state),
            fecha=datetime.now(UTC),
            limitaciones=[*limitaciones, draft.contexto_alcance],
        ),
        diagnostico=Diagnostico(texto=draft.diagnostico + "\n" + interpretaciones, metrics=metrics),
        competencia=Competencia(texto=draft.competencia, ranking=metrics.ranking),
        hallazgos=findings,
        estrategia=Estrategia(
            texto=draft.estrategia, objetivos=plan.objetivos, prioridades=draft.prioridades
        ),
        plan=plan,
        medicion=Medicion(
            kpis=[o.kpi for o in plan.objetivos] or ["Score de Citación"],
            metodologia="Mismo banco, motores y repeticiones; separar espontánea y asistida.",
            cadencia="Trimestral",
        ),
        riesgos=draft.riesgos,
        hoja_ruta=HojaRuta(
            hitos=hitos,
            responsabilidades=responsabilidades,
            presupuesto_eur=plan.presupuesto_estimado_eur,
            seguimiento=draft.hoja_ruta,
        ),
        marcas={b.id: b.nombre for b in state["market"].marcas},
    )


async def write(state: StudyState, deps: Deps) -> dict[str, Any]:
    sid = state["study_id"]
    payload = {
        "brief": dump(state["brief"]),
        "market": dump(state["market"]),
        "contexto": contexto(state),
        "metricas": metrics_summary(state["metrics"]),
        "metrics": dump(state["metrics"]),
        "diferencia_anterior": dump(state.get("metrics_delta")),
        "hallazgos": dump(state["findings"]),
        "plan": dump(state["plan"]),
        "errores": state.get("errores", []),
    }
    borrador, trace = await structured(deps, state, ProposalDraft, "write.v1", payload)
    proposal = assemble_proposal(borrador, state)

    await db(deps.repo.save_proposal, sid, proposal)
    study = await db(deps.repo.get_study, sid)
    await db(deps.repo.save_study, study.model_copy(update={"estado": "completado"}))
    await persist_traces(deps, state, [trace])
    return {"proposal": proposal, "revision_pendiente": "none", **cost_update(state, [trace])}

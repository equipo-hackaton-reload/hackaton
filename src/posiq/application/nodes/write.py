"""Nodo `write`: redacta la propuesta (las 10 secciones del entregable).

El LLM devuelve solo ProposalDraft. El código compone métricas, ranking, hallazgos, plan aprobado,
objetivos, presupuesto, hitos y contexto desde el estado verificado del estudio.

Trazabilidad brief → propuesta (ADR 0013): el redactor enlaza cada punto del brief con las acciones
o hallazgos que lo tratan (`cobertura_brief`); `domain.brief_coverage` construye el encargo literal
y decide qué está cubierto. Si falta algún punto que el redactor pueda enlazar, se reintenta una vez
con las carencias; lo que siga pendiente se declara en `contexto.limitaciones`.
"""

from datetime import UTC, datetime
from typing import Any

from posiq.application.deps import (
    Deps,
    cost_update,
    db,
    dump,
    persist_traces,
    structured,
    trazas_si_falla,
)
from posiq.application.nodes.judge import JUEZ_REGLAS
from posiq.application.nodes.plan import metrics_summary
from posiq.application.schemas_draft import ProposalDraft
from posiq.application.state import StudyState
from posiq.domain.brief_coverage import carencias, evaluar_cobertura, puntos_del_brief
from posiq.domain.schemas import (
    Competencia,
    Contexto,
    Diagnostico,
    Encargo,
    Estrategia,
    Hito,
    HojaRuta,
    Medicion,
    Proposal,
)

PROMPT = "write.v2"
LIMITACION_KIT = (
    "Datos sintéticos del kit del reto (ejecuciones grabadas), no mediciones reales de los motores."
)
# Solo cuando el nodo `judge` evaluó por reglas (por elección o sin clave). La demo sin claves
# (`FixtureJudge`) mezcla etiquetas humanas del kit y reglas, y lo explica en sus propios supuestos.
LIMITACION_REGLAS = (
    "Menciones evaluadas solo por reglas (aparición y posición), sin juez LLM: el tipo de mención, "
    "el sentimiento y la fuerza de la recomendación no se han juzgado."
)


# Restricciones y presupuesto se comprueban contra el plan aprobado: el redactor no puede cubrirlos.
NO_ENLAZABLES = ("restriccion", "presupuesto")
PREFIJO_PENDIENTES = "Puntos del brief sin tratar en esta propuesta: "


def encargo(draft: ProposalDraft, state: StudyState) -> Encargo:
    """Encargo literal del brief con la cobertura que valida el dominio."""
    return evaluar_cobertura(
        state["brief"], state["plan"], state["findings"], draft.cobertura_brief
    )


def carencias_enlazables(enc: Encargo) -> list[str]:
    """Carencias que el redactor puede resolver enlazando ids (no restricciones ni presupuesto)."""
    return carencias(
        enc.model_copy(
            update={"cobertura": [p for p in enc.cobertura if p.tipo not in NO_ENLAZABLES]}
        )
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


def assemble_proposal(draft: ProposalDraft, state: StudyState) -> Proposal:
    """Compone la propuesta sin pedir al LLM que replique contratos o calcule cifras."""
    plan, metrics = state["plan"], state["metrics"]
    findings = state["findings"]
    if set(draft.interpretacion_hallazgos) != {f.id for f in findings}:
        raise ValueError(
            "el borrador debe interpretar exactamente los ids de hallazgos del estudio"
        )
    limitaciones = list(draft.supuestos)
    enc = encargo(draft, state)
    if pendientes := carencias(enc):
        limitaciones.append(PREFIJO_PENDIENTES + "; ".join(pendientes))
    if state.get("juez") == JUEZ_REGLAS:
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
        encargo=enc,
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
        "puntos_brief": dump(puntos_del_brief(state["brief"])),
    }
    borrador, trace = await structured(deps, state, ProposalDraft, PROMPT, payload)
    traces = [trace]
    if faltan := carencias_enlazables(encargo(borrador, state)):
        retry_state: StudyState = {**state, "traces": [*state.get("traces", []), trace]}
        with trazas_si_falla(traces):  # el primer borrador ya se pagó
            borrador, trace = await structured(
                deps,
                retry_state,
                ProposalDraft,
                PROMPT,
                {**payload, "borrador_anterior": dump(borrador), "carencias_cobertura": faltan},
            )
        traces.append(trace)
    proposal = assemble_proposal(borrador, state)

    await db(deps.repo.save_proposal, sid, proposal)
    study = await db(deps.repo.get_study, sid)
    await db(deps.repo.save_study, study.model_copy(update={"estado": "completado"}))
    await persist_traces(deps, state, traces)
    return {"proposal": proposal, "revision_pendiente": "none", **cost_update(state, traces)}

"""Escenarios guardados de un estudio: crear uno del consultor y elegir el que usa la propuesta.

Las cifras (acciones mantenidas y aplazadas, esfuerzo, coste declarado, simulación) las calcula
`domain/scenarios.py` (ADR 0009). Los tres preajustes los crea el nodo `plan`
(`nodes.diferencial.escenarios_del_plan`) con `completo` elegido; aquí solo se añaden escenarios del
consultor, se elige uno y se recorta el plan de la propuesta a sus acciones.
"""

from collections.abc import Sequence

from posiq.application.diferencial import EscenarioGuardado
from posiq.domain.scenario_schemas import EntradaEscenario, EscenarioPlan
from posiq.domain.scenarios import build_scenario
from posiq.domain.schemas import Finding, Metrics, Plan

PREFIJO_PERSONALIZADO = "P"


def personalizado(
    guardados: Sequence[EscenarioGuardado],
    plan: Plan,
    findings: list[Finding],
    metrics: Metrics,
    entrada: EntradaEscenario,
) -> EscenarioGuardado:
    """Escenario del consultor con id `P1`, `P2`… `ValueError` si la entrada no casa con el plan."""
    escenario = build_scenario(plan, findings, metrics, entrada)
    n = sum(1 for g in guardados if g.id.startswith(PREFIJO_PERSONALIZADO)) + 1
    return EscenarioGuardado(id=f"{PREFIJO_PERSONALIZADO}{n}", escenario=escenario)


def elegir(guardados: Sequence[EscenarioGuardado], escenario_id: str) -> list[EscenarioGuardado]:
    """Los mismos escenarios con solo `escenario_id` elegido. `KeyError` si no existe."""
    if escenario_id not in {g.id for g in guardados}:
        raise KeyError(escenario_id)
    return [g.model_copy(update={"elegido": g.id == escenario_id}) for g in guardados]


def recorte(guardados: Sequence[EscenarioGuardado] | None) -> EscenarioGuardado | None:
    """El escenario elegido si recorta el plan; None con el `completo` (la propuesta de siempre)."""
    # Import diferido: `nodes` importa `write`, que importa este módulo.
    from posiq.application.nodes.diferencial import ESCENARIO_ELEGIDO

    elegido = next((g for g in guardados or [] if g.elegido), None)
    return None if elegido is None or elegido.id == ESCENARIO_ELEGIDO else elegido


def plan_del_escenario(plan: Plan, escenario: EscenarioPlan) -> Plan:
    """El plan con las mismas fases y solo las acciones que el escenario mantiene.

    El presupuesto no se toca: el coste declarado puede cubrir solo algunas acciones y el sistema
    nunca inventa costes. `nota_para_la_propuesta` explica ambas cifras.
    """
    mantenidas = set(escenario.mantenidas)
    fases = [
        f.model_copy(update={"acciones": [a for a in f.acciones if a.id in mantenidas]})
        for f in plan.fases
    ]
    return plan.model_copy(update={"fases": fases})


def nota_para_la_propuesta(guardado: EscenarioGuardado, plan: Plan) -> str:
    """Limitación que explica qué escenario usa la propuesta y qué queda fuera."""
    e = guardado.escenario
    partes = [
        f"Propuesta con el escenario «{guardado.id}»: {len(e.mantenidas)} de "
        f"{len(plan.acciones)} acciones del plan; {len(e.aplazadas)} aplazadas."
    ]
    if e.hallazgos_sin_cubrir:
        partes.append(f"Hallazgos sin cubrir: {', '.join(e.hallazgos_sin_cubrir)}.")
    partes.append("El presupuesto indicado es el estimado para el plan completo.")
    if e.coste_declarado_eur is not None:
        partes.append(
            "Coste declarado por el consultor para las acciones mantenidas: "
            f"{e.coste_declarado_eur:,.0f} €.".replace(",", ".")
        )
    return " ".join(partes)

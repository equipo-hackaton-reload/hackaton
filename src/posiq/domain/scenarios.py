"""Escenarios del plan: qué acciones se mantienen o aplazan y con qué efecto simulado. Puro.

Ver docs/adr/0009-escenarios-del-plan.md. Nada de este módulo inventa cifras: el esfuerzo sale de
la talla de cada acción (S = 1, M = 2, L = 3), los euros solo de `costes_declarados` y el score de
`simulation.simulate_plan`, sin modificarlo.

Orden de evaluación (determinista)
    Las acciones se recorren en orden topológico de `dependencias`; entre las que están listas se
    toma la primera en el orden del plan (fase y, dentro de la fase, posición). Así una acción se
    decide siempre después de las acciones de las que depende. Las dependencias que no son
    acciones del plan se ignoran (no hay nada que mantener ni aplazar). Las acciones de un ciclo de
    dependencias, y las que dependen de ellas, se aplazan por `dependencia`.

Precedencia de motivos (el primero que se cumple es el que se registra)
    1. `desactivada`: no está en `acciones_activas`.
    2. `dependencia`: alguna de sus dependencias no se mantiene (en cascada).
    3. `fuera_de_prioridad`: hay `prioridad` y su palanca no está en ella.
    4. `fuera_de_presupuesto`: tiene coste declarado y no cabe en lo que queda de presupuesto.
    5. `capacidad`: sus puntos de esfuerzo no caben en lo que queda de capacidad.
    Una acción aplazada no consume presupuesto ni capacidad; una posterior más pequeña puede caber
    (llenado voraz en el orden de evaluación).

Presupuesto
    Solo consumen presupuesto las acciones con coste en `costes_declarados`. Las que no lo tienen
    se mantienen sin consumirlo: el sistema no estima costes. `coste_declarado_eur` suma los costes
    declarados de las mantenidas y es None si ninguna mantenida tiene coste declarado.
"""

import heapq
from collections.abc import Iterable
from typing import Final, Literal

from posiq.domain.scenario_schemas import (
    AccionAplazada,
    EntradaEscenario,
    EscenarioPlan,
    MotivoAplazamiento,
    NombreEscenario,
)
from posiq.domain.schemas import Action, Finding, Metrics, Plan, Talla
from posiq.domain.simulation import simulate_plan

_TOLERANCIA_EUR: Final = 1e-6  # que 0,1 + 0,2 € quepan en 0,3 €
PUNTOS_ESFUERZO: Final[dict[Talla, int]] = {"S": 1, "M": 2, "L": 3}
ORDEN_IMPACTO: Final[dict[Talla, int]] = {"L": 3, "M": 2, "S": 1}

Preajuste = Literal["minimo_viable", "equilibrado", "completo"]
PREAJUSTES: Final[tuple[Preajuste, ...]] = ("minimo_viable", "equilibrado", "completo")


def _eur(valor: float) -> str:
    """Euros en formato español: 1.500 €, 1.500,50 €."""
    entero = f"{valor:,.0f}" if float(valor).is_integer() else f"{valor:,.2f}"
    return entero.replace(",", "·").replace(".", ",").replace("·", ".") + " €"


def _orden_de_evaluacion(acciones: list[Action]) -> tuple[list[Action], list[Action]]:
    """(Acciones en orden topológico con desempate por orden del plan, acciones bloqueadas).

    Las bloqueadas son las de un ciclo de dependencias y las que dependen de ellas.
    """
    indice = {a.id: i for i, a in enumerate(acciones)}
    deps = {a.id: {d for d in a.dependencias if d in indice} for a in acciones}
    pendientes = {a.id: len(deps[a.id]) for a in acciones}
    dependientes: dict[str, list[str]] = {a.id: [] for a in acciones}
    for a in acciones:
        for d in deps[a.id]:
            dependientes[d].append(a.id)
    listas = [indice[a.id] for a in acciones if pendientes[a.id] == 0]
    heapq.heapify(listas)
    orden: list[Action] = []
    while listas:
        actual = acciones[heapq.heappop(listas)]
        orden.append(actual)
        for siguiente in dependientes[actual.id]:
            pendientes[siguiente] -= 1
            if pendientes[siguiente] == 0:
                heapq.heappush(listas, indice[siguiente])
    hechas = {a.id for a in orden}
    return orden, [a for a in acciones if a.id not in hechas]


def _validar_ids(entrada: EntradaEscenario, acciones: list[Action]) -> None:
    ids = {a.id for a in acciones}
    if len(ids) != len(acciones):
        raise ValueError("el plan tiene ids de acción repetidos")
    desconocidas = sorted(
        (set(entrada.acciones_activas or []) | set(entrada.costes_declarados)) - ids
    )
    if desconocidas:
        raise ValueError(f"acciones que no están en el plan: {desconocidas}")


def _cubre(accion: Action, medicion_cubre: bool) -> bool:
    """Si la acción cuenta como cobertura de sus hallazgos."""
    return medicion_cubre or accion.palanca != "medicion"


def _plan_reducido(plan: Plan, mantenidas: set[str]) -> Plan:
    """El mismo plan, con las mismas fases, quedándose solo con las acciones mantenidas."""
    return plan.model_copy(
        update={
            "fases": [
                f.model_copy(update={"acciones": [a for a in f.acciones if a.id in mantenidas]})
                for f in plan.fases
            ]
        }
    )


def build_scenario(
    plan: Plan,
    findings: list[Finding],
    metrics: Metrics,
    entrada: EntradaEscenario,
    nombre: NombreEscenario = "personalizado",
    *,
    detalle_desactivada: str = "el consultor la ha desactivado",
    medicion_cubre: bool = True,
) -> EscenarioPlan:
    """Aplica `entrada` a `plan` y re-simula el score con las acciones mantenidas.

    Orden de evaluación, precedencia de motivos y regla del presupuesto en el docstring del
    módulo. Lanza ValueError si `acciones_activas` o `costes_declarados` nombran acciones que no
    están en el plan. `intervalo` queda en None hasta que exista el IC del score (ADR 0008/0009).

    `medicion_cubre=False` (lo usan los preajustes): una acción de palanca `medicion` no cuenta
    como cobertura de sus hallazgos en `hallazgos_sin_cubrir`, porque no mueve la visibilidad.
    """
    acciones = plan.acciones
    ids = {a.id for a in acciones}
    _validar_ids(entrada, acciones)
    activas = None if entrada.acciones_activas is None else set(entrada.acciones_activas)
    prioridad = None if entrada.prioridad is None else set(entrada.prioridad)
    costes = entrada.costes_declarados

    orden, bloqueadas = _orden_de_evaluacion(acciones)
    mantenidas: set[str] = set()
    aplazadas: dict[str, AccionAplazada] = {}
    gastado = 0.0
    usado = 0

    def estado(dep: str) -> str:
        if dep in aplazadas:
            return f"{dep} (aplazada: {aplazadas[dep].motivo})"
        return f"{dep} (bloqueada por un ciclo de dependencias)"

    def aplazar(accion: Action, motivo: MotivoAplazamiento, detalle: str) -> None:
        aplazadas[accion.id] = AccionAplazada(action_id=accion.id, motivo=motivo, detalle=detalle)

    for accion in [*orden, *bloqueadas]:
        puntos = PUNTOS_ESFUERZO[accion.esfuerzo]
        coste = costes.get(accion.id)
        caidas = [d for d in accion.dependencias if d in ids and d not in mantenidas]
        if activas is not None and accion.id not in activas:
            aplazar(accion, "desactivada", detalle_desactivada)
        elif caidas:
            aplazar(
                accion,
                "dependencia",
                "depende de " + ", ".join(estado(d) for d in caidas) + ", que no se mantiene",
            )
        elif prioridad is not None and accion.palanca not in prioridad:
            aplazar(
                accion,
                "fuera_de_prioridad",
                f"su palanca «{accion.palanca}» no está entre las prioritarias",
            )
        elif (
            entrada.presupuesto_eur is not None
            and coste is not None
            and gastado + coste > entrada.presupuesto_eur + _TOLERANCIA_EUR
        ):
            aplazar(
                accion,
                "fuera_de_presupuesto",
                f"coste declarado {_eur(coste)}; quedan {_eur(entrada.presupuesto_eur - gastado)} "
                f"de {_eur(entrada.presupuesto_eur)}",
            )
        elif entrada.capacidad is not None and usado + puntos > entrada.capacidad:
            aplazar(
                accion,
                "capacidad",
                f"esfuerzo {accion.esfuerzo} ({puntos} puntos); quedan "
                f"{entrada.capacidad - usado} de {entrada.capacidad} puntos",
            )
        else:
            mantenidas.add(accion.id)
            usado += puntos
            gastado += coste or 0.0

    cubiertos = {
        fid
        for a in acciones
        if a.id in mantenidas and _cubre(a, medicion_cubre)
        for fid in a.finding_ids
    }
    costes_mantenidas = [costes[a.id] for a in acciones if a.id in mantenidas and a.id in costes]
    return EscenarioPlan(
        nombre=nombre,
        entrada=entrada,
        mantenidas=[a.id for a in acciones if a.id in mantenidas],
        aplazadas=[aplazadas[a.id] for a in acciones if a.id in aplazadas],
        hallazgos_sin_cubrir=[f.id for f in findings if f.id not in cubiertos],
        esfuerzo_total=usado,
        coste_declarado_eur=sum(costes_mantenidas) if costes_mantenidas else None,
        simulacion=simulate_plan(_plan_reducido(plan, mantenidas), metrics, findings),
        intervalo=None,
    )


# --- Preajustes -----------------------------------------------------------------------------------


def _cierre(acciones: list[Action]) -> dict[str, frozenset[str]]:
    """Cada acción con todas sus dependencias del plan, transitivamente."""
    ids = {a.id for a in acciones}
    deps = {a.id: [d for d in a.dependencias if d in ids] for a in acciones}
    out: dict[str, frozenset[str]] = {}
    for a in acciones:
        visto: set[str] = set()
        pila = [a.id]
        while pila:
            actual = pila.pop()
            if actual not in visto:
                visto.add(actual)
                pila.extend(deps[actual])
        out[a.id] = frozenset(visto)
    return out


def minimal_cover(plan: Plan, objetivos: Iterable[str]) -> list[str]:
    """Conjunto de acciones de menor esfuerzo que cubre todos los hallazgos `objetivos`.

    Recubrimiento exacto: se ramifica sobre el primer objetivo sin cubrir, probando cada acción que
    lo cubre junto con todas sus dependencias. Toda solución óptima contiene, para ese objetivo,
    alguna de esas acciones y su cierre, así que la búsqueda es completa. Entre soluciones de igual
    esfuerzo gana la de menos acciones y, después, la de índices del plan menores en orden
    lexicográfico. Solo se usan acciones ejecutables (fuera de ciclos de dependencias). Los
    objetivos que ninguna acción ejecutable cubre se ignoran. Las acciones de palanca `medicion` no
    cubren ningún hallazgo (no mueven la visibilidad), pero entran si otra elegida depende de ellas.
    Devuelve ids en orden del plan.
    """
    acciones = plan.acciones
    _, bloqueadas = _orden_de_evaluacion(acciones)
    sin_ciclo = {a.id for a in acciones} - {b.id for b in bloqueadas}
    ejecutables = [a for a in acciones if a.id in sin_ciclo]
    indice = {a.id: i for i, a in enumerate(acciones)}
    puntos = {a.id: PUNTOS_ESFUERZO[a.esfuerzo] for a in acciones}
    cubre = {a.id: set(a.finding_ids) if _cubre(a, False) else set() for a in acciones}
    cierre = _cierre(acciones)
    cubribles = {fid for a in ejecutables for fid in cubre[a.id]}
    pendientes = [f for f in dict.fromkeys(objetivos) if f in cubribles]

    def clave(sel: frozenset[str]) -> tuple[int, int, tuple[int, ...]]:
        return sum(puntos[a] for a in sel), len(sel), tuple(sorted(indice[a] for a in sel))

    mejor: frozenset[str] | None = None
    vistos: set[frozenset[str]] = set()

    def buscar(sel: frozenset[str]) -> None:
        nonlocal mejor
        if sel in vistos:
            return
        vistos.add(sel)
        if mejor is not None and clave(sel) >= clave(mejor):
            return
        cubiertos = {f for a in sel for f in cubre[a]}
        falta = next((f for f in pendientes if f not in cubiertos), None)
        if falta is None:
            mejor = sel
            return
        for a in ejecutables:
            if falta in cubre[a.id]:
                buscar(sel | cierre[a.id])

    buscar(frozenset())
    elegidas = mejor or frozenset()
    return [a.id for a in acciones if a.id in elegidas]


def preset_entrada(
    nombre: Preajuste, plan: Plan, findings: list[Finding]
) -> tuple[EntradaEscenario, str]:
    """Entrada de un preajuste y el detalle con que se aplazan las acciones que deja fuera.

    - `minimo_viable`: recubrimiento mínimo (`minimal_cover`) de los hallazgos del nivel de
      impacto más alto (L > M > S) que el plan puede cubrir sin acciones de medición.
    - `equilibrado`: recubrimiento mínimo de todos los hallazgos de impacto L y M.
    - `completo`: todas las acciones.
    Ningún preajuste fija presupuesto, costes, capacidad ni prioridad.
    """
    if nombre == "completo":
        return EntradaEscenario(), "no aplica"
    cubribles = {fid for a in plan.acciones if _cubre(a, False) for fid in a.finding_ids}
    con_accion = [f for f in findings if f.id in cubribles]
    if nombre == "minimo_viable":
        tope = max((ORDEN_IMPACTO[f.impacto] for f in con_accion), default=0)
        objetivos = [f.id for f in con_accion if ORDEN_IMPACTO[f.impacto] == tope]
        nivel = next((t for t, v in ORDEN_IMPACTO.items() if v == tope), "")
        detalle = (
            f"fuera del mínimo viable: no hace falta para cubrir los hallazgos de impacto {nivel} "
            "con el menor esfuerzo"
        )
    else:
        objetivos = [f.id for f in con_accion if f.impacto in ("L", "M")]
        detalle = (
            "fuera del escenario equilibrado: no hace falta para cubrir los hallazgos de impacto "
            "L y M con el menor esfuerzo"
        )
    return EntradaEscenario(acciones_activas=minimal_cover(plan, objetivos)), detalle


def build_preset(
    nombre: Preajuste, plan: Plan, findings: list[Finding], metrics: Metrics
) -> EscenarioPlan:
    """Escenario de un preajuste (`minimo_viable`, `equilibrado` o `completo`)."""
    entrada, detalle = preset_entrada(nombre, plan, findings)
    return build_scenario(
        plan, findings, metrics, entrada, nombre, detalle_desactivada=detalle, medicion_cubre=False
    )


def build_presets(plan: Plan, findings: list[Finding], metrics: Metrics) -> list[EscenarioPlan]:
    """Los tres preajustes, en orden: mínimo viable, equilibrado y completo."""
    return [build_preset(n, plan, findings, metrics) for n in PREAJUSTES]

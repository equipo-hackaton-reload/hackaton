"""Trazabilidad brief → propuesta: qué pidió el cliente y dónde lo trata la propuesta.

La IA redacta y propone enlaces (punto del brief → ids de acciones o hallazgos); este módulo, puro y
determinista, construye el encargo LITERAL desde el `BriefSummary` y decide qué está cubierto:

- Objetivos, servicios prioritarios, ciudades, públicos y competidores declarados: cubiertos si al
  menos un id enlazado existe entre las acciones del plan o los hallazgos. Los ids que no existen
  se descartan y se anotan en el motivo.
- Restricciones: cubiertas si TODAS las acciones del plan las declaran (`ignora_restriccion`, la
  misma regla que `validate_plan_against_brief`) y el plan no se declara incumplidor. Los enlaces
  del LLM no cuentan: la prueba es el plan.
- Presupuesto: cubierto si el presupuesto estimado del plan no supera el máximo del brief.
"""

from collections.abc import Mapping, Sequence

from posiq.domain.schemas import (
    BriefSummary,
    Encargo,
    Finding,
    Plan,
    PuntoBrief,
    TipoPuntoBrief,
    ignora_restriccion,
)

# Prefijo del id de cada punto: `objetivo-1`, `servicio-2`, ... (1-based, en el orden del brief).
_PREFIJOS: dict[TipoPuntoBrief, str] = {
    "objetivo": "objetivo",
    "restriccion": "restriccion",
    "servicio_prioritario": "servicio",
    "ciudad": "ciudad",
    "publico": "publico",
    "competidor": "competidor",
}
ID_PRESUPUESTO = "presupuesto"
SIN_ENLACE = "Ninguna acción ni hallazgo de la propuesta lo trata."


def _eur(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".") + " €"


def texto_presupuesto(presupuesto: tuple[int, int]) -> str:
    minimo, maximo = presupuesto
    if minimo == maximo:
        return f"{_eur(minimo)} al año"
    return f"{_eur(minimo).removesuffix(' €')}–{_eur(maximo)} al año"


def _listas(brief: BriefSummary) -> list[tuple[TipoPuntoBrief, list[str]]]:
    return [
        ("objetivo", brief.objetivos),
        ("restriccion", brief.restricciones),
        ("servicio_prioritario", brief.servicios_prioritarios),
        ("ciudad", brief.ciudades),
        ("publico", brief.publicos),
        ("competidor", brief.competidores_declarados),
    ]


def puntos_del_brief(brief: BriefSummary) -> list[PuntoBrief]:
    """Los puntos del brief, literales y aún sin enlazar (todos `pendiente`).

    Es lo que recibe el redactor para enlazar cada `id` con las acciones o hallazgos que lo tratan.
    """
    puntos = [
        PuntoBrief(id=f"{_PREFIJOS[tipo]}-{i}", tipo=tipo, texto=texto, estado="pendiente")
        for tipo, textos in _listas(brief)
        for i, texto in enumerate(textos, start=1)
    ]
    if brief.presupuesto_anual_eur:
        puntos.append(
            PuntoBrief(
                id=ID_PRESUPUESTO,
                tipo="presupuesto",
                texto=texto_presupuesto(brief.presupuesto_anual_eur),
                estado="pendiente",
            )
        )
    return puntos


def _restriccion(punto: PuntoBrief, plan: Plan) -> PuntoBrief:
    acciones = plan.acciones
    ignoran = [a.id for a in acciones if ignora_restriccion(a, punto.texto)]
    declaran = [a.id for a in acciones if a.id not in ignoran]
    if not acciones:
        motivo, cubierto = "El plan no tiene acciones.", False
    elif ignoran:
        motivo, cubierto = f"No la declaran las acciones {', '.join(ignoran)}.", False
    elif not plan.respeta_restricciones:
        motivo, cubierto = "El plan declara que no respeta las restricciones del brief.", False
    else:
        motivo, cubierto = "La declaran todas las acciones del plan.", True
    return punto.model_copy(
        update={
            "accion_ids": declaran,
            "estado": "cubierto" if cubierto else "pendiente",
            "motivo": motivo,
        }
    )


def _presupuesto(punto: PuntoBrief, plan: Plan, maximo: int) -> PuntoBrief:
    estimado = plan.presupuesto_estimado_eur
    if estimado <= maximo:
        estado, motivo = (
            "cubierto",
            f"Plan de {_eur(estimado)}, dentro del máximo de {_eur(maximo)}.",
        )
    else:
        estado, motivo = (
            "pendiente",
            f"Plan de {_eur(estimado)}, supera el máximo de {_eur(maximo)}.",
        )
    return punto.model_copy(update={"estado": estado, "motivo": motivo})


def _enlazado(
    punto: PuntoBrief, ids: Sequence[str], acciones: set[str], hallazgos: set[str]
) -> PuntoBrief:
    accion_ids: list[str] = []
    hallazgo_ids: list[str] = []
    inexistentes: list[str] = []
    for id_ in dict.fromkeys(ids):  # sin repetidos, en el orden del redactor
        if id_ in acciones:
            accion_ids.append(id_)
        elif id_ in hallazgos:
            hallazgo_ids.append(id_)
        else:
            inexistentes.append(id_)
    cubierto = bool(accion_ids or hallazgo_ids)
    motivo = "" if cubierto else SIN_ENLACE
    if inexistentes:
        motivo = f"{motivo} Ids inexistentes descartados: {', '.join(inexistentes)}.".strip()
    return punto.model_copy(
        update={
            "accion_ids": accion_ids,
            "hallazgo_ids": hallazgo_ids,
            "estado": "cubierto" if cubierto else "pendiente",
            "motivo": motivo,
        }
    )


def evaluar_cobertura(
    brief: BriefSummary,
    plan: Plan,
    hallazgos: Sequence[Finding],
    enlaces: Mapping[str, Sequence[str]] | None = None,
) -> Encargo:
    """Encargo literal del brief con la cobertura de cada punto en esta propuesta.

    `enlaces` es lo que propone el redactor: id de punto → ids de acciones o hallazgos. Los ids de
    puntos que no existen se ignoran; en restricciones y presupuesto los enlaces no cuentan.
    """
    enlaces = enlaces or {}
    acciones = {a.id for a in plan.acciones}
    ids_hallazgos = {f.id for f in hallazgos}
    cobertura: list[PuntoBrief] = []
    for punto in puntos_del_brief(brief):
        if punto.tipo == "restriccion":
            cobertura.append(_restriccion(punto, plan))
        elif punto.tipo == "presupuesto" and brief.presupuesto_anual_eur:
            cobertura.append(_presupuesto(punto, plan, brief.presupuesto_anual_eur[1]))
        else:
            cobertura.append(_enlazado(punto, enlaces.get(punto.id, []), acciones, ids_hallazgos))
    return Encargo(
        objetivos=list(brief.objetivos),
        restricciones=list(brief.restricciones),
        servicios_prioritarios=list(brief.servicios_prioritarios),
        ciudades=list(brief.ciudades),
        publicos=list(brief.publicos),
        competidores_declarados=list(brief.competidores_declarados),
        presupuesto_anual_eur=brief.presupuesto_anual_eur,
        cobertura=cobertura,
    )


def carencias(encargo: Encargo) -> list[str]:
    """Lo que falta por tratar, una línea por punto pendiente (vacía si todo está cubierto)."""
    return [f"{p.id} · {p.tipo} «{p.texto}»: {p.motivo}" for p in encargo.pendientes]

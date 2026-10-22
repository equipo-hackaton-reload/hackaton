"""Secciones del diferencial en el Word: rigor, competidores, fuentes, exactitud, escenarios,
auditoría técnica y la oferta de seguimiento con método.

`DatosDiferencial` recoge del estado del estudio lo que ya calculó `domain/` (nodo `diferencial`,
`plan` y, cuando exista, la auditoría web). Este módulo solo FORMATEA: no hay aritmética de
negocio. Un bloque que falta (estudio antiguo, bloque sin calcular) se dice en el documento, nunca
se rellena con un número inventado.

El texto que viene de los motores (afirmaciones) o de la web (evidencias) es DATO: se copia en
celdas de tabla, escapado por docxtpl, y nunca va a las instrucciones de un LLM.
"""

from collections.abc import Mapping
from datetime import date
from typing import Any, Final, get_args

from pydantic import BaseModel, ConfigDict, ValidationError

from posiq.adapters.export.formato import (
    SIN_DATOS,
    fmt_num,
    fmt_pct,
    fmt_pp,
    fmt_rango,
    fmt_score,
    ordinal,
    si_no,
)
from posiq.application.diferencial import EscenarioGuardado, Rigor
from posiq.domain.accuracy_schemas import AccionMitigacion, HallazgoExactitud
from posiq.domain.competitor_gap_schemas import BrechaCompetidores, CompetidorMedido
from posiq.domain.scenario_schemas import EscenarioPlan
from posiq.domain.schemas import Finding, Motor, Proposal
from posiq.domain.simulation_schemas import Escenario, SimulationResult
from posiq.domain.source_map_schemas import OportunidadFuente
from posiq.domain.stats_schemas import Intervalo, SignificanciaHallazgo
from posiq.domain.web_audit_schemas import AuditoriaWeb

MOTORES: Final[tuple[Motor, ...]] = get_args(Motor)
NO_CALCULADO = "No se calculó en este estudio."
MAX_AFIRMACIONES: Final = 12
"""Afirmaciones a revisar que se listan en el Word; el resto se consulta en la plataforma."""
MAX_OPORTUNIDADES: Final = 10

RIGOR_INTRO = (
    "Las cifras de un estudio con asistentes de IA son una muestra: si se repite la medición, "
    "cambian un poco. Por eso cada cifra principal va con su intervalo de confianza del 95 %. "
    "Una diferencia solo se presenta como real si su intervalo excluye el cero."
)
COMPETIDORES_INTRO = (
    "Los competidores que declara el brief frente a los que la IA pone de verdad por delante "
    "de la marca en sus respuestas."
)
FUENTES_INTRO = (
    "Fuentes que los motores citan en el sector y en las que la marca aparece menos que sus "
    "competidores. La cuota es la parte de todas las citas del sector que van a esa fuente; la "
    "brecha, cuántos puntos más aparece con los competidores que con la marca."
)
EXACTITUD_INTRO = (
    "Lo que los motores afirman sobre la marca, contrastado por reglas con los datos del brief. "
    "«A revisar por la clínica» señala expresiones de una lista de revisión (por ejemplo, "
    "promesas de resultado): no es un juicio de legalidad."
)
SIN_MITIGACIONES = "Ninguna afirmación incorrecta: no hace falta corregir ninguna fuente en origen."
ESCENARIOS_INTRO = (
    "Qué pasa con el Score de Citación si se ejecuta todo el plan o solo una parte. Son "
    "proyecciones con supuestos declarados, no promesas de resultado: la única forma de conocer "
    "el efecto real es volver a medir."
)
AUDITORIA_INTRO = (
    "¿Pueden los motores leer la web de la marca? Comprobaciones técnicas con su evidencia "
    "literal (robots.txt, sitemap, datos estructurados, texto sin JavaScript)."
)
AUDITORIA_FIXTURE = (
    "Auditoría sobre la web ficticia del caso sintético: no describe ninguna web real."
)
SEGUIMIENTO_INTRO = (
    "Esta propuesta no es una foto: el servicio es un seguimiento con método. Cada medición se "
    "compara con la anterior en las mismas condiciones y solo se informa de lo que cambia de "
    "verdad."
)
PILARES_SEGUIMIENTO = (
    (
        "Línea base",
        "Este estudio fija el punto de partida: el Score de Citación con su margen, la aparición "
        "en cada uno de los cuatro motores y la posición frente a la competencia.",
    ),
    (
        "Re-medición trimestral comparable",
        "Mismo banco de prompts, los mismos cuatro motores, el mismo juez y la configuración de "
        "la marca vigente (perfil y mercado versionados). Si la configuración cambia, el cambio "
        "queda marcado en la serie.",
    ),
    (
        "Solo cambios fuera del margen",
        "Un cambio se comunica si su intervalo de confianza excluye el cero, y siempre frente a "
        "los competidores medidos en la misma ronda.",
    ),
    (
        "Indicadores adelantados",
        "Aparición por motor, presencia en las fuentes que citan los motores y exactitud de lo "
        "que dicen de la marca: se mueven antes que el score.",
    ),
    (
        "Plan re-priorizado",
        "Tras cada medición se actualiza el estado de cada acción y se re-priorizan las "
        "siguientes según lo que haya cambiado.",
    ),
)
ESCENARIOS = {
    "minimo_viable": "Mínimo viable",
    "equilibrado": "Equilibrado",
    "completo": "Completo",
    "personalizado": "Personalizado",
}
APLAZAMIENTOS = {
    "desactivada": "desactivada",
    "dependencia": "depende de otra aplazada",
    "fuera_de_presupuesto": "fuera de presupuesto",
    "fuera_de_prioridad": "fuera de prioridad",
    "capacidad": "sin capacidad",
}
ESTADOS_AFIRMACION = {
    "correcta": "Correcta",
    "incorrecta": "Incorrecta",
    "no_verificable": "No verificable",
    "riesgo_regulatorio": "A revisar por la clínica",
}
BLOQUES_WEB = {
    "descubrimiento": "Descubrimiento",
    "contenido": "Contenido",
    "acceso_bots": "Acceso de los bots de IA",
    "agentes_api": "Agentes y API",
    "rendimiento": "Rendimiento",
}
TIPOS_VISIBILIDAD = {"espontaneo": "espontánea", "asistido": "asistida"}
ESTADOS_WEB = {"ok": "Correcto", "falla": "Falla", "no_aplica": "No aplica", "error": "Error"}


class DatosDiferencial(BaseModel):
    """Lo que el Word necesita del estado del estudio además de la `Proposal`.

    Todos los campos son opcionales: un estudio anterior al diferencial, o un bloque que no se
    pudo calcular, deja el campo en None y el documento lo dice.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rigor: Rigor | None = None
    competidores: BrechaCompetidores | None = None
    oportunidades_fuente: list[OportunidadFuente] | None = None
    exactitud: list[HallazgoExactitud] | None = None
    mitigaciones: list[AccionMitigacion] | None = None
    escenarios: list[EscenarioGuardado] | None = None
    simulacion: SimulationResult | None = None
    auditoria_web: AuditoriaWeb | None = None

    @classmethod
    def del_estado(cls, valores: Mapping[str, Any]) -> "DatosDiferencial":
        """Toma las claves del estado del grafo. Una clave ausente o que no valida queda en None
        (la exportación nunca falla por un bloque del diferencial)."""
        datos: dict[str, Any] = {}
        for nombre in cls.model_fields:
            valor = valores.get(nombre)
            if valor is None:
                continue
            try:
                datos[nombre] = getattr(cls.model_validate({nombre: valor}), nombre)
            except ValidationError:
                continue
        return cls(**datos)


# --- Formato de intervalos ------------------------------------------------------------------------


def _ic_score(i: Intervalo | None) -> str:
    return f"{fmt_score(i.valor)} {fmt_rango(i.inf, i.sup, fmt_score)}" if i else SIN_DATOS


def _ic_pct(i: Intervalo | None) -> str:
    return f"{fmt_pct(i.valor)} {fmt_rango(i.inf, i.sup, fmt_pct)}" if i else SIN_DATOS


def _rango(e: Escenario | None) -> str:
    if e is None:
        return SIN_DATOS
    return f"{fmt_score(e.esperado)} {fmt_rango(e.minimo, e.maximo, fmt_score)}"


# --- Rigor ----------------------------------------------------------------------------------------


def _veredicto(s: SignificanciaHallazgo | None) -> str:
    if s is None:
        return NO_CALCULADO
    if s.significancia is None:
        return f"Sin contraste estadístico: {s.sin_contraste}"
    if s.significancia.significativa:
        return (
            f"Se distingue del ruido de muestreo (IC 95 % sin el cero). Contraste: {s.contraste}."
        )
    return (
        "No se distingue del ruido de muestreo (el IC 95 % incluye el cero): léase como "
        f"indicio. Contraste: {s.contraste}."
    )


def contraste_hallazgo(d: DatosDiferencial | None, finding_id: str) -> str:
    if d is None or d.rigor is None:
        return NO_CALCULADO
    return _veredicto(d.rigor.hallazgos.get(finding_id))


def _rigor(r: Rigor | None) -> dict[str, Any]:
    if r is None:
        return {"hay": False, "aviso": NO_CALCULADO}
    motores = []
    for motor in MOTORES:
        aparicion = r.aparicion_por_motor.get(motor)
        motores.append(
            {
                "motor": motor,
                "aparicion": _ic_pct(aparicion),
                "margen": f"± {fmt_pp(aparicion.margen)}" if aparicion else SIN_DATOS,
                "n": str(aparicion.n) if aparicion else SIN_DATOS,
                "score": _ic_score(r.score_por_motor.get(motor)),
            }
        )
    metodo = (
        f"Intervalos del 95 %: Wilson para la aparición y bootstrap "
        f"({fmt_num(r.replicas_bootstrap, 0)} réplicas, semilla {r.semilla_bootstrap}) "
        "para el score."
        if r.replicas_bootstrap
        else "Intervalos del 95 %: Wilson para la aparición y bootstrap para el score."
    )
    return {
        "hay": True,
        "intro": RIGOR_INTRO,
        "score": _ic_score(r.score_global),
        "margen": f"± {fmt_score(r.score_global.margen)} puntos" if r.score_global else SIN_DATOS,
        "n": str(r.score_global.n) if r.score_global else SIN_DATOS,
        "metodo": metodo,
        "motores": motores,
    }


# --- Competidores y fuentes -----------------------------------------------------------------------


def _competidor(c: CompetidorMedido, sorpresas: list[str]) -> dict[str, str]:
    ventaja = SIN_DATOS
    if c.ventaja_puntos is not None:
        signo = "+" if c.ventaja_puntos > 0 else ""
        ventaja = f"{signo}{fmt_score(c.ventaja_puntos)}"
    nombre = c.nombre
    if c.nombre_declarado and c.nombre_declarado != c.nombre:
        nombre = f"{c.nombre} («{c.nombre_declarado}» en el brief)"
    return {
        "marca": nombre,
        "puesto": ordinal(c.puesto),
        "score": fmt_score(c.score),
        "ventaja": ventaja,
        "tasa": fmt_pct(c.tasa_espontanea),
        "nota": "Relevante" if c.brand_id in sorpresas else "—",
    }


def _hallazgo_txt(f: Finding) -> str:
    return f"{f.titulo}. {f.descripcion}"


def _competidores(b: BrechaCompetidores | None) -> dict[str, Any]:
    if b is None:
        return {"hay": False, "aviso": NO_CALCULADO}
    vacia = {k: "—" for k in ("puesto", "score", "ventaja", "tasa", "nota")}
    nombres = {c.brand_id: c.nombre for c in [*b.declarados, *b.no_declarados_por_delante]}
    return {
        "hay": True,
        "intro": COMPETIDORES_INTRO,
        "foco": (
            f"La marca es la {ordinal(b.puesto_foco)} de {b.n_marcas} marcas medidas, "
            f"con un Score de Citación de {fmt_score(b.score_foco)} y una visibilidad espontánea "
            f"de {fmt_pct(b.tasa_foco)}."
        ),
        "declarados": [_competidor(c, b.sorpresas) for c in b.declarados]
        or [{"marca": "El brief no declara competidores medidos", **vacia}],
        "por_delante": [_competidor(c, b.sorpresas) for c in b.no_declarados_por_delante]
        or [{"marca": "Ninguna marca no declarada va por delante", **vacia}],
        "umbral": (
            f"«Relevante»: ventaja de al menos {fmt_score(b.umbral_ventaja_puntos)} puntos "
            "sobre la marca."
        ),
        "notas": [
            *(f"Declarado en el brief y no medido: {n}." for n in b.no_resueltos),
            *(
                f"Declarado con poca presencia espontánea (menos de {fmt_pct(b.umbral_tasa)}): "
                f"{nombres.get(i, i)}."
                for i in b.declarados_poco_mencionados
            ),
            *(_hallazgo_txt(f) for f in b.hallazgos),
        ],
    }


def _fuentes(ops: list[OportunidadFuente] | None) -> dict[str, Any]:
    if ops is None:
        return {"hay": False, "aviso": NO_CALCULADO}
    filas = [
        {
            "fuente": o.dominio or "—",
            "tipo": o.tipo or "Fuera del catálogo",
            "cuota": fmt_pct(o.cuota_sector),
            "marca": fmt_pct(o.presencia_marca),
            "competidores": fmt_pct(o.presencia_competidores),
            "brecha": fmt_pp(o.gap),
            "prioridad": o.puntuacion,
        }
        for o in ops[:MAX_OPORTUNIDADES]
    ]
    resto = len(ops) - len(filas)
    return {
        "hay": True,
        "intro": FUENTES_INTRO,
        "filas": filas
        or [
            {
                "fuente": "La marca no está por debajo de sus competidores en ninguna fuente",
                **{k: "—" for k in ("tipo", "cuota", "marca", "competidores", "brecha")},
                "prioridad": "—",
            }
        ],
        "resto": f"Y {resto} oportunidades más en la plataforma." if resto > 0 else "",
    }


# --- Exactitud y auditoría ------------------------------------------------------------------------


def _exactitud(
    hallazgos: list[HallazgoExactitud] | None, mitigaciones: list[AccionMitigacion] | None
) -> dict[str, Any]:
    if hallazgos is None:
        return {"hay": False, "aviso": NO_CALCULADO}
    resumen = []
    revisar = []
    for h in hallazgos:
        resumen.append(
            [
                ("Afirmaciones analizadas", str(len(h.afirmaciones))),
                ("Correctas", str(h.n_correctas)),
                ("Incorrectas", str(h.n_incorrectas)),
                ("No verificables con el brief", str(h.n_no_verificables)),
                ("A revisar por la clínica", str(h.n_riesgo_regulatorio)),
            ]
        )
        afirmaciones = {a.id: a for a in h.afirmaciones}
        # Las incorrectas primero; la misma frase del mismo motor solo una vez.
        for estado in ("incorrecta", "riesgo_regulatorio"):
            for v in h.verificaciones:
                if v.estado != estado:
                    continue
                a = afirmaciones[v.afirmacion_id]
                fila = {
                    "motor": a.motor or SIN_DATOS,
                    "texto": a.texto.replace("**", "").strip(),
                    "estado": ESTADOS_AFIRMACION[v.estado],
                    "motivo": v.motivo,
                }
                if fila not in revisar:
                    revisar.append(fila)
    filas = revisar[:MAX_AFIRMACIONES]
    resto = len(revisar) - len(filas)
    return {
        "hay": True,
        "intro": EXACTITUD_INTRO,
        "resumen": [{"campo": c, "valor": v} for fila in resumen for c, v in fila],
        "revisar": filas
        or [
            {
                "motor": "—",
                "texto": "Ninguna afirmación incorrecta ni a revisar",
                "estado": "—",
                "motivo": "—",
            }
        ],
        "resto": f"Y {resto} afirmaciones más a revisar en la plataforma." if resto > 0 else "",
        "mitigaciones": [
            {
                "id": m.id,
                "descripcion": m.descripcion,
                "fuente": m.fuente_dominio or "Sin fuente citada",
                "afirmaciones": str(len(m.afirmacion_ids)),
            }
            for m in mitigaciones or []
        ],
        "sin_mitigaciones": SIN_MITIGACIONES,
    }


def _auditoria(a: AuditoriaWeb | None) -> dict[str, Any]:
    if a is None:
        return {"hay": False}
    return {
        "hay": True,
        "intro": AUDITORIA_INTRO,
        "aviso": AUDITORIA_FIXTURE if a.origen == "fixture" else "",
        "dominio": a.dominio,
        "puntuacion": f"{fmt_num(a.puntuacion, 0)} / 100"
        if a.puntuacion is not None
        else SIN_DATOS,
        "fecha": a.obtenido_en.strftime("%d/%m/%Y"),
        "bloques": [
            {
                "bloque": BLOQUES_WEB[b.bloque],
                "puntuacion": fmt_num(b.puntuacion, 0),
                "ok": str(b.ok),
                "falla": str(b.falla),
            }
            for b in a.bloques
        ],
        "fallos": [
            {
                "titulo": c.titulo,
                "detalle": c.detalle,
                "motores": ", ".join(c.motores_afectados) or "—",
                "evidencia": c.evidencia or "—",
            }
            for c in a.comprobaciones
            if c.estado == "falla"
        ]
        or [
            {
                "titulo": "Ninguna comprobación falla",
                "detalle": "—",
                "motores": "—",
                "evidencia": "—",
            }
        ],
        "bots": [
            {
                "bot": b.bot,
                "motor": b.motor or "—",
                "permitido": si_no(b.permitido),
            }
            for b in a.accesos_bots
        ],
    }


# --- Escenarios y simulación ----------------------------------------------------------------------


def _final(e: EscenarioPlan) -> Escenario | None:
    return (
        e.simulacion.proyecciones[-1].score if e.simulacion and e.simulacion.proyecciones else None
    )


def _escenarios(
    guardados: list[EscenarioGuardado] | None, sim: SimulationResult | None
) -> dict[str, Any]:
    escenarios = [
        {
            "nombre": ESCENARIOS[g.escenario.nombre]
            + (" (el de esta propuesta)" if g.elegido else ""),
            "mantenidas": ", ".join(g.escenario.mantenidas) or "—",
            "aplazadas": "; ".join(
                f"{a.action_id} ({APLAZAMIENTOS[a.motivo]})" for a in g.escenario.aplazadas
            )
            or "—",
            "sin_cubrir": ", ".join(g.escenario.hallazgos_sin_cubrir) or "Ninguno",
            "esfuerzo": f"{g.escenario.esfuerzo_total} puntos",
            "score": _rango(_final(g.escenario)),
        }
        for g in guardados or []
    ]
    fases = (
        [
            {
                "fase": p.fase,
                "score": _rango(p.score),
                "tasa": f"{fmt_pct(p.tasa_espontanea.esperado)} "
                f"{fmt_rango(p.tasa_espontanea.minimo, p.tasa_espontanea.maximo, fmt_pct)}",
            }
            for p in sim.proyecciones
        ]
        if sim
        else []
    )
    return {
        "hay": bool(escenarios or fases),
        "aviso": NO_CALCULADO,
        "intro": ESCENARIOS_INTRO,
        "escenarios": escenarios,
        "hay_escenarios": bool(escenarios),
        "fases": fases,
        "hay_simulacion": sim is not None,
        "actual": fmt_score(sim.score_actual) if sim else SIN_DATOS,
        "supuestos": sim.supuestos if sim else [],
        "advertencia": sim.advertencia if sim else "",
        "modelo": sim.modelo_version if sim else "",
    }


# --- Seguimiento con método -----------------------------------------------------------------------


def _segmento(clave: str) -> str:
    """`espontaneo:motor:ChatGPT` → `Visibilidad espontánea · ChatGPT`."""
    tipo, _, valor = clave.split(":", 2)
    return f"Visibilidad {TIPOS_VISIBILIDAD.get(tipo, tipo)} · {valor}"


def _seguimiento(p: Proposal, d: DatosDiferencial, fecha: date) -> dict[str, Any]:
    score = p.diagnostico.metrics.score_global
    linea_base = [
        ("Fecha de la línea base", fecha.strftime("%d/%m/%Y")),
        (
            "Score de Citación",
            _ic_score(d.rigor.score_global)
            if d.rigor and d.rigor.score_global
            else fmt_score(score.score),
        ),
        ("Motores medidos", ", ".join(p.contexto.motores)),
        ("Evaluaciones", str(score.n_evaluaciones)),
    ]
    if d.competidores and d.competidores.puesto_foco:
        linea_base.append(
            (
                "Posición frente a la competencia",
                f"{ordinal(d.competidores.puesto_foco)} de {d.competidores.n_marcas}",
            )
        )
    deltas = []
    if d.rigor:
        for clave, s in d.rigor.deltas.items():
            if not s.significativa:
                continue
            es_score = clave == "score_global"
            fmt = fmt_score if es_score else fmt_pct
            valor = fmt_score(s.delta) + " puntos" if es_score else fmt_pp(s.delta)
            deltas.append(
                {
                    "indicador": "Score de Citación" if es_score else _segmento(clave),
                    "cambio": valor,
                    "ic": fmt_rango(s.intervalo.inf, s.intervalo.sup, fmt),
                }
            )
    hay_remedicion = bool(d.rigor and d.rigor.deltas)
    return {
        "intro": SEGUIMIENTO_INTRO,
        "metodo": [{"titulo": t, "texto": x} for t, x in PILARES_SEGUIMIENTO],
        "linea_base": [{"campo": c, "valor": v} for c, v in linea_base],
        "hay_remedicion": hay_remedicion,
        "deltas": deltas
        or [{"indicador": "Ningún cambio fuera del margen", "cambio": "—", "ic": "—"}],
    }


def contexto_diferencial(p: Proposal, d: DatosDiferencial | None) -> dict[str, Any]:
    """Claves de la plantilla para las secciones del diferencial (solo formato)."""
    d = d or DatosDiferencial()
    return {
        "rigor": _rigor(d.rigor),
        "rivales": _competidores(d.competidores),
        "fuentes_op": _fuentes(d.oportunidades_fuente),
        "exactitud": _exactitud(d.exactitud, d.mitigaciones),
        "auditoria": _auditoria(d.auditoria_web),
        "escenarios": _escenarios(d.escenarios, d.simulacion),
        "seguimiento": _seguimiento(p, d, p.contexto.fecha.date()),
    }

"""Exportación de la propuesta a Word con docxtpl.

`build_context` traduce la `Proposal` a cadenas listas para la plantilla. Solo FORMATEA (redondeo,
porcentaje, separadores, etiquetas en español): no deriva cifras nuevas. Todo número del documento
es un campo de la propuesta.
"""

from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from docx.shared import Mm, RGBColor
from docxtpl import DocxTemplate, InlineImage, RichText  # type: ignore[import-untyped]

from posiq.adapters.export.branding import AgencyBrandKit
from posiq.adapters.export.diferencial import (
    DatosDiferencial,
    contexto_diferencial,
    contraste_hallazgo,
)
from posiq.adapters.export.formato import (
    SIN_DATOS,
    fmt_cifra,
    fmt_eur,
    fmt_num,
    fmt_pct,
    fmt_score,
)
from posiq.adapters.export.formato import lista as _lista
from posiq.adapters.export.formato import parrafos as _parrafos
from posiq.adapters.export.formato import semanas as _semanas
from posiq.adapters.export.template import TEMPLATE_PATH
from posiq.domain.schemas import (
    Action,
    Encargo,
    Metrics,
    Proposal,
    PuntoBrief,
    TipoVisibilidad,
    VisibilityCell,
)

MARCA_POR_DEFECTO = "posiq."
COLOR_POR_DEFECTO = "1F3A5F"
TITULO = "Propuesta de mejora de visibilidad en asistentes de IA"
AVISO_SINTETICO = (
    "Datos sintéticos del kit del reto: reproducen la estructura de un estudio real, "
    "no el comportamiento real de los motores."
)
NOTA_ESPONTANEO = (
    "Las tablas siguientes muestran solo la visibilidad espontánea (prompts que no nombran la "
    "marca). La asistida se presenta aparte y no indica que el motor descubra la marca."
)

FASES = {
    "descubrimiento": "Descubrimiento",
    "comparacion": "Comparación",
    "validacion": "Validación",
    "decision": "Decisión",
}
SEGMENTOS = {**FASES, "global": "Global"}
PALANCAS = {
    "autoridad_terceros": "Autoridad en fuentes de terceros",
    "entidad_datos": "Entidad y datos estructurados",
    "contenido": "Contenido que responde a preguntas reales",
    "reputacion": "Reputación y reseñas",
    "comunidades": "Comunidades y plataformas",
    "tecnico": "Accesibilidad técnica",
    "medicion": "Medición",
}
TIPOS: dict[TipoVisibilidad, str] = {"espontaneo": "Espontánea", "asistido": "Asistida"}
TIPOS_PUNTO = {
    "objetivo": "Objetivo",
    "restriccion": "Restricción",
    "servicio_prioritario": "Servicio prioritario",
    "ciudad": "Ciudad",
    "publico": "Público",
    "competidor": "Competidor declarado",
    "presupuesto": "Presupuesto",
}
PENDIENTE = "Pendiente"
INTRO_ENCARGO = (
    "Esto es lo que nos pedisteis en el brief, tal cual, y dónde lo trata esta propuesta. "
    "La cobertura la comprueba el sistema contra el plan y los hallazgos, no la redacción."
)
SIN_ENCARGO = "Esta propuesta no registra el encargo del brief."
ROTULO_SINTETICO = "Caso sintético del reto: datos ficticios"
ORIGENES = {"kit": "Kit del reto (datos grabados)", "api": "APIs de los motores"}


# --- Contexto -------------------------------------------------------------------------------------


class _Nombres:
    """Nombre legible de una marca: `Proposal.marcas`; si falta, la foco desde el contexto y el
    resto a partir del id."""

    def __init__(self, marcas: dict[str, str], foco_id: str, foco_nombre: str) -> None:
        self._marcas = {foco_id: foco_nombre, **marcas}

    def __call__(self, brand_id: str | None) -> str:
        if brand_id is None:
            return SIN_DATOS
        return self._marcas.get(brand_id) or brand_id.replace("-", " ").title()


def _filas_visibilidad(
    m: Metrics,
    tipo: TipoVisibilidad,
    dimension: Literal["global", "motor", "fase", "ciudad", "perfil"],
) -> list[dict[str, str]]:
    def lider(c: VisibilityCell) -> str:
        if m.lider_id is None or m.lider_id == m.marca_foco_id:
            return "—"
        otra = m.cell(m.lider_id, tipo, dimension, c.valor)
        return fmt_pct(otra.tasa) if otra else SIN_DATOS

    filas = [
        {
            "valor": SEGMENTOS.get(c.valor, c.valor),
            "tasa": fmt_pct(c.tasa),
            "n": str(c.n),
            "apariciones": str(c.apariciones),
            "fuerza": fmt_num(c.fuerza_media, 2),
            "lider": lider(c),
        }
        for c in m.cells(m.marca_foco_id, tipo, dimension)
    ]
    return filas or [_vacia("valor", "tasa", "n", "apariciones", "fuerza", "lider")]


def _vacia(*campos: str) -> dict[str, str]:
    return {c: ("Sin datos" if i == 0 else "—") for i, c in enumerate(campos)}


def _diagnostico(p: Proposal, nombre: _Nombres) -> dict[str, Any]:
    m = p.diagnostico.metrics
    s = m.score_global
    calidad = [
        {
            "tipo": TIPOS[q.tipo],
            "apariciones": str(q.apariciones),
            "fuerza": fmt_num(q.fuerza_media, 2),
            "por_tipo": "; ".join(f"{k}: {v}" for k, v in q.por_tipo_mencion.items()) or "—",
            "negativas": str(q.negativas),
            "desconocimiento": str(q.por_desconocimiento),
        }
        for q in m.calidad_menciones
        if q.brand_id == m.marca_foco_id
    ]
    fuentes = [
        {
            "dominio": f.dominio,
            "tipo": f.tipo or "Fuera del catálogo",
            "calidad": fmt_num(f.calidad, 1),
            "apariciones": str(f.apariciones),
        }
        for f in m.top_fuentes
        if f.brand_id == m.marca_foco_id
    ]
    return {
        "texto": _parrafos(p.diagnostico.texto),
        "score": fmt_score(s.score),
        "aparicion": fmt_num(s.aparicion, 1),
        "posicion": fmt_num(s.posicion, 1),
        "fuerza": fmt_num(s.fuerza, 1),
        "calidad_fuente": fmt_num(s.calidad_fuente, 1),
        "n_evaluaciones": str(s.n_evaluaciones),
        "score_version": s.score_version,
        "nota_espontaneo": NOTA_ESPONTANEO,
        "motor": _filas_visibilidad(m, "espontaneo", "motor"),
        "fase": _filas_visibilidad(m, "espontaneo", "fase"),
        "ciudad": _filas_visibilidad(m, "espontaneo", "ciudad"),
        "perfil": _filas_visibilidad(m, "espontaneo", "perfil"),
        "asistido": _filas_visibilidad(m, "asistido", "global"),
        "calidad": calidad
        or [_vacia("tipo", "apariciones", "fuerza", "por_tipo", "negativas", "desconocimiento")],
        "fuentes": fuentes or [_vacia("dominio", "tipo", "calidad", "apariciones")],
        "lider": nombre(m.lider_id),
    }


def _competencia(p: Proposal, nombre: _Nombres) -> dict[str, Any]:
    m = p.diagnostico.metrics
    ranking = []
    for i, brand_id in enumerate(p.competencia.ranking, start=1):
        s = m.score_of(brand_id)
        ranking.append(
            {
                "pos": str(i),
                "marca": nombre(brand_id),
                "score": fmt_score(s.score if s else None),
                "n": str(s.n_evaluaciones) if s else SIN_DATOS,
            }
        )
    brecha = [
        {
            "dominio": g.dominio,
            "tipo": g.tipo or "Fuera del catálogo",
            "con_lider": str(g.con_lider),
            "con_marca": str(g.con_marca),
            "brecha": str(g.brecha),
            "lider_sin_marca": str(g.lider_sin_marca),
        }
        for g in m.brecha_fuentes
    ]
    return {
        "texto": _parrafos(p.competencia.texto),
        "ranking": ranking or [_vacia("pos", "marca", "score", "n")],
        "brecha": brecha
        or [_vacia("dominio", "tipo", "con_lider", "con_marca", "brecha", "lider_sin_marca")],
    }


def _accion(a: Action) -> dict[str, str]:
    return {
        "id": a.id,
        "descripcion": a.descripcion,
        "palanca": PALANCAS[a.palanca],
        "fase": FASES[a.fase_embudo] if a.fase_embudo else "Transversal",
        "motores": _lista(list(a.motores_objetivo)) if a.motores_objetivo else "Todos",
        "esfuerzo": a.esfuerzo,
        "impacto": a.impacto,
        "responsable": a.responsable,
        "plazo": _semanas(a.plazo_semanas),
        "kpi": a.kpi,
        "entregables": _lista(a.entregables, "; "),
        "dependencias": _lista(a.dependencias),
        "hallazgos": _lista(a.finding_ids),
        "restricciones": _lista(a.restricciones_revisadas, "; "),
    }


def _donde(p: PuntoBrief) -> str:
    if p.estado == "pendiente":
        return f"pendiente: {p.motivo}" if p.motivo else "pendiente"
    if p.tipo in ("restriccion", "presupuesto"):
        return p.motivo
    partes = []
    if p.accion_ids:
        partes.append("Acciones " + _lista(p.accion_ids))
    if p.hallazgo_ids:
        partes.append("Hallazgos " + _lista(p.hallazgo_ids))
    return " · ".join(partes)


def _encargo(e: Encargo | None) -> dict[str, Any]:
    """El encargo literal y su cobertura; solo formatea lo que decidió `domain.brief_coverage`."""
    if e is None:
        return {
            "intro": SIN_ENCARGO,
            "listas": [],
            "cobertura": [_vacia("tipo", "texto", "donde", "estado")],
        }
    presupuesto = [p.texto for p in e.cobertura if p.tipo == "presupuesto"]
    listas = [
        ("Objetivos", e.objetivos),
        ("Restricciones", e.restricciones),
        ("Servicios prioritarios", e.servicios_prioritarios),
        ("Ciudades", e.ciudades),
        ("Públicos", e.publicos),
        ("Competidores declarados", e.competidores_declarados),
        ("Presupuesto", presupuesto),
    ]
    return {
        "intro": INTRO_ENCARGO,
        "listas": [{"titulo": t, "puntos": items} for t, items in listas if items],
        "cobertura": [
            {
                "tipo": TIPOS_PUNTO[p.tipo],
                "texto": p.texto,
                "donde": _donde(p),
                "estado": "Cubierto" if p.estado == "cubierto" else PENDIENTE,
            }
            for p in e.cobertura
        ]
        or [_vacia("tipo", "texto", "donde", "estado")],
    }


def build_context(
    proposal: Proposal,
    tpl: DocxTemplate,
    marca_agencia: AgencyBrandKit | None = None,
    diferencial: DatosDiferencial | None = None,
) -> dict[str, Any]:
    p = proposal
    c = p.contexto
    nombre = _Nombres(p.marcas, p.diagnostico.metrics.marca_foco_id, c.marca)
    agencia = marca_agencia.nombre if marca_agencia else MARCA_POR_DEFECTO
    color = marca_agencia.color_hex if marca_agencia else COLOR_POR_DEFECTO
    logo: Any = ""
    if marca_agencia and marca_agencia.logo_path:
        if not marca_agencia.logo_path.is_file():
            raise FileNotFoundError(f"no existe el logo de la agencia: {marca_agencia.logo_path}")
        logo = InlineImage(tpl, str(marca_agencia.logo_path), width=Mm(35))
    pie = (marca_agencia.pie_de_pagina if marca_agencia else "") or (
        f"{agencia} · Propuesta para {c.marca}"
    )
    if c.datos_sinteticos:
        pie = f"{pie} · {ROTULO_SINTETICO}"
    fecha = c.fecha.strftime("%d/%m/%Y")
    return {
        **contexto_diferencial(p, diferencial),
        "cabecera": RichText(agencia, color=color, bold=True, size=20),
        "pie": pie,
        "logo": logo,
        "titulo": TITULO,
        "marca": c.marca,
        "sector": c.sector,
        "fecha": fecha,
        "rotulo_sintetico": ROTULO_SINTETICO if c.datos_sinteticos else "",
        "aviso_sintetico": AVISO_SINTETICO if c.datos_sinteticos else "",
        "resumen": _parrafos(p.resumen_ejecutivo),
        "encargo": _encargo(p.encargo),
        "ctx": {
            "marca": c.marca,
            "sector": c.sector,
            "motores": _lista(list(c.motores)),
            "fecha": fecha,
            "origen": ORIGENES[c.origen_datos],
            "sinteticos": "Sí" if c.datos_sinteticos else "No",
            "study_id": p.study_id,
            "limitaciones": c.limitaciones,
        },
        "diag": _diagnostico(p, nombre),
        "comp": _competencia(p, nombre),
        "hallazgos": [
            {
                "id": f.id,
                "titulo": f.titulo,
                "descripcion": f.descripcion,
                "cifra": fmt_cifra(f.cifra, f.unidad),
                "origen": f.origen_cifra,
                "fase": FASES[f.fase_embudo] if f.fase_embudo else "Transversal",
                "impacto": f.impacto,
                "confianza": fmt_pct(f.confianza),
                "n_evidencias": str(len(f.evaluation_ids)),
                "contraste": contraste_hallazgo(diferencial, f.id),
            }
            for f in p.hallazgos
        ],
        "estrategia": {
            "texto": _parrafos(p.estrategia.texto),
            "objetivos": [
                {
                    "kpi": o.kpi,
                    "actual": fmt_num(o.valor_actual, 2),
                    "objetivo": fmt_num(o.valor_objetivo, 2),
                    "plazo": _semanas(o.plazo_semanas),
                }
                for o in p.estrategia.objetivos
            ]
            or [_vacia("kpi", "actual", "objetivo", "plazo")],
            "prioridades": p.estrategia.prioridades,
        },
        "plan": {
            "presupuesto": fmt_eur(p.plan.presupuesto_estimado_eur),
            "respeta": "Sí" if p.plan.respeta_restricciones else "No",
            "fases": [
                {
                    "nombre": f.nombre,
                    "semanas": str(f.semanas),
                    "objetivo": f.objetivo,
                    "acciones": [_accion(a) for a in f.acciones],
                }
                for f in p.plan.fases
            ],
        },
        "medicion": {
            "kpis": p.medicion.kpis,
            "metodologia": p.medicion.metodologia,
            "cadencia": p.medicion.cadencia,
        },
        "riesgos": [{"riesgo": r.riesgo, "mitigacion": r.mitigacion} for r in p.riesgos],
        "hoja": {
            "hitos": [
                {"semana": str(h.semana), "descripcion": h.descripcion} for h in p.hoja_ruta.hitos
            ]
            or [_vacia("semana", "descripcion")],
            "responsabilidades": [
                {"quien": quien, "que": _lista(tareas)}
                for quien, tareas in p.hoja_ruta.responsabilidades.items()
            ]
            or [_vacia("quien", "que")],
            "presupuesto": fmt_eur(p.hoja_ruta.presupuesto_eur),
            "seguimiento": p.hoja_ruta.seguimiento,
        },
    }


class DocxExporter:
    """`Exporter` a Word. Para PDF, `PdfExporter` convierte este mismo docx."""

    def __init__(self, template_path: Path = TEMPLATE_PATH) -> None:
        self.template_path = template_path

    def render(
        self,
        proposal: Proposal,
        *,
        formato: Literal["docx", "pdf"],
        marca_agencia: AgencyBrandKit | None = None,
        diferencial: DatosDiferencial | None = None,
    ) -> bytes:
        """`diferencial` (opcional, fuera del puerto `Exporter`): las cifras del estado del
        estudio que no viven en la `Proposal` (rigor, competidores, escenarios...)."""
        if formato != "docx":
            raise ValueError("DocxExporter solo genera docx; para PDF usa PdfExporter")
        tpl = DocxTemplate(str(self.template_path))
        tpl.render(build_context(proposal, tpl, marca_agencia, diferencial), autoescape=True)
        color = RGBColor.from_string(
            marca_agencia.color_hex if marca_agencia else COLOR_POR_DEFECTO
        )
        for estilo in ("Title", "Heading 1", "Heading 2", "Heading 3"):
            tpl.docx.styles[estilo].font.color.rgb = color
        buffer = BytesIO()
        tpl.save(buffer)
        return buffer.getvalue()

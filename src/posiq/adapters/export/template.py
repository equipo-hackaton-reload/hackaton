"""Plantilla docxtpl de la propuesta, construida con python-docx (reproducible, sin edición a mano).

La plantilla solo coloca valores ya formateados por `docx.build_context`: no hace aritmética.
Las diez secciones del formato del entregable (doc 06) más «Lo que nos habéis pedido» (2.ª): el
encargo literal del brief y dónde se trata cada punto (ADR 0013). Se regenera con
`uv run python scripts/build_docx_template.py`.
"""

from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.section import WD_ORIENT
from docx.shared import Pt

TEMPLATE_PATH = Path(__file__).parent / "templates" / "propuesta.docx"

SECCIONES: tuple[str, ...] = (
    "1. Resumen ejecutivo",
    "2. Lo que nos habéis pedido",
    "3. Contexto y alcance",
    "4. Diagnóstico de visibilidad",
    "5. Análisis de la competencia",
    "6. Hallazgos clave",
    "7. Estrategia recomendada",
    "8. Plan de acción por fases",
    "9. Medición y seguimiento",
    "10. Riesgos y supuestos",
    "11. Hoja de ruta y presupuesto",
)


def _p(doc: DocumentObject, text: str, style: str | None = None) -> None:
    doc.add_paragraph(text, style=style)


def _tag(doc: DocumentObject, stmt: str) -> None:
    """Párrafo de control de docxtpl (`{%p ... %}`), que desaparece al renderizar."""
    doc.add_paragraph(f"{{%p {stmt} %}}")


def _texto(doc: DocumentObject, expr: str) -> None:
    """Lista de párrafos de texto libre."""
    _tag(doc, f"for par in {expr}")
    _p(doc, "{{ par }}")
    _tag(doc, "endfor")


def _vinetas(doc: DocumentObject, expr: str) -> None:
    _tag(doc, f"for item in {expr}")
    _p(doc, "{{ item }}", "List Bullet")
    _tag(doc, "endfor")


def _tabla(doc: DocumentObject, cabeceras: list[str], expr: str, campos: list[str]) -> None:
    """Tabla con cabecera y una fila por elemento de `expr` (bucle `{%tr %}` de docxtpl)."""
    tabla = doc.add_table(rows=4, cols=len(cabeceras))
    tabla.style = "Light Grid Accent 1"
    for celda, texto in zip(tabla.rows[0].cells, cabeceras, strict=True):
        celda.text = texto
    tabla.rows[1].cells[0].text = f"{{%tr for r in {expr} %}}"
    for celda, campo in zip(tabla.rows[2].cells, campos, strict=True):
        celda.text = f"{{{{ r.{campo} }}}}"
    tabla.rows[3].cells[0].text = "{%tr endfor %}"
    doc.add_paragraph()


def _ficha(doc: DocumentObject, filas: list[tuple[str, str]]) -> None:
    """Tabla de dos columnas campo → valor."""
    tabla = doc.add_table(rows=len(filas), cols=2)
    tabla.style = "Light List Accent 1"
    for fila, (campo, valor) in zip(tabla.rows, filas, strict=True):
        fila.cells[0].text = campo
        fila.cells[1].text = valor
    doc.add_paragraph()


def _cabecera_y_pie(doc: DocumentObject) -> None:
    section = doc.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.header.paragraphs[0].text = "{{r cabecera }}"
    section.footer.paragraphs[0].text = "{{ pie }}"


def _portada(doc: DocumentObject) -> None:
    _p(doc, "{{ logo }}")
    doc.add_heading("{{ titulo }}", level=0)
    _p(doc, "{{ marca }} · {{ sector }} · {{ fecha }}")
    _tag(doc, "if aviso_sintetico")
    _p(doc, "{{ aviso_sintetico }}", "Intense Quote")
    _tag(doc, "endif")


def _encargo(doc: DocumentObject) -> None:
    """Lo que pidió el cliente, tal cual, y la tabla de cobertura punto → dónde se trata."""
    doc.add_heading(SECCIONES[1], level=1)
    _p(doc, "{{ encargo.intro }}")
    _tag(doc, "for l in encargo.listas")
    doc.add_heading("{{ l.titulo }}", level=2)
    _vinetas(doc, "l.puntos")
    _tag(doc, "endfor")
    doc.add_heading("Dónde se trata cada punto", level=2)
    _tabla(
        doc,
        ["Punto", "Lo que pedisteis", "Dónde se trata", "Estado"],
        "encargo.cobertura",
        ["tipo", "texto", "donde", "estado"],
    )


def _diagnostico(doc: DocumentObject) -> None:
    doc.add_heading(SECCIONES[3], level=1)
    _texto(doc, "diag.texto")
    _ficha(
        doc,
        [
            ("Score de Citación global (0-100)", "{{ diag.score }}"),
            ("Aparición (máx. 30)", "{{ diag.aparicion }}"),
            ("Posición (máx. 20)", "{{ diag.posicion }}"),
            ("Fuerza de recomendación (máx. 30)", "{{ diag.fuerza }}"),
            ("Calidad de la fuente (máx. 20)", "{{ diag.calidad_fuente }}"),
            ("Evaluaciones", "{{ diag.n_evaluaciones }}"),
            ("Versión del score", "{{ diag.score_version }}"),
        ],
    )
    _p(doc, "{{ diag.nota_espontaneo }}")
    cabeceras = ["Segmento", "Visibilidad espontánea", "n", "Apariciones", "Fuerza media", "Líder"]
    campos = ["valor", "tasa", "n", "apariciones", "fuerza", "lider"]
    for titulo, clave in (
        ("Visibilidad espontánea por motor", "motor"),
        ("Visibilidad espontánea por fase del embudo", "fase"),
        ("Visibilidad espontánea por ciudad", "ciudad"),
        ("Visibilidad espontánea por perfil", "perfil"),
    ):
        doc.add_heading(titulo, level=2)
        _tabla(doc, cabeceras, f"diag.{clave}", campos)
    doc.add_heading("Visibilidad asistida (referencia, no comparable)", level=2)
    _tabla(doc, ["Segmento", "Visibilidad asistida", *cabeceras[2:]], "diag.asistido", campos)
    doc.add_heading("Calidad de las menciones", level=2)
    _tabla(
        doc,
        ["Tipo", "Apariciones", "Fuerza media", "Por tipo de mención", "Negativas", "Desconoc."],
        "diag.calidad",
        ["tipo", "apariciones", "fuerza", "por_tipo", "negativas", "desconocimiento"],
    )
    doc.add_heading("Fuentes que acompañan a la marca", level=2)
    _tabla(
        doc,
        ["Dominio", "Tipo", "Calidad", "Apariciones"],
        "diag.fuentes",
        ["dominio", "tipo", "calidad", "apariciones"],
    )


def _competencia(doc: DocumentObject) -> None:
    doc.add_heading(SECCIONES[4], level=1)
    _texto(doc, "comp.texto")
    doc.add_heading("Ranking por Score de Citación", level=2)
    _tabla(
        doc,
        ["#", "Marca", "Score", "Evaluaciones"],
        "comp.ranking",
        ["pos", "marca", "score", "n"],
    )
    doc.add_heading("Brecha de fuentes frente al líder", level=2)
    _tabla(
        doc,
        ["Dominio", "Tipo", "Con líder", "Con la marca", "Brecha", "Líder sin la marca"],
        "comp.brecha",
        ["dominio", "tipo", "con_lider", "con_marca", "brecha", "lider_sin_marca"],
    )


def _hallazgos(doc: DocumentObject) -> None:
    doc.add_heading(SECCIONES[5], level=1)
    _tag(doc, "for h in hallazgos")
    doc.add_heading("{{ h.id }} · {{ h.titulo }}", level=2)
    _p(doc, "{{ h.descripcion }}")
    _ficha(
        doc,
        [
            ("Cifra", "{{ h.cifra }}"),
            ("Origen de la cifra", "{{ h.origen }}"),
            ("Fase del embudo", "{{ h.fase }}"),
            ("Impacto", "{{ h.impacto }}"),
            ("Confianza", "{{ h.confianza }}"),
            ("Evaluaciones que lo respaldan", "{{ h.n_evidencias }}"),
        ],
    )
    _tag(doc, "endfor")


def _plan(doc: DocumentObject) -> None:
    doc.add_heading(SECCIONES[7], level=1)
    _ficha(
        doc,
        [
            ("Presupuesto estimado", "{{ plan.presupuesto }}"),
            ("Respeta las restricciones del brief", "{{ plan.respeta }}"),
        ],
    )
    _tag(doc, "for f in plan.fases")
    doc.add_heading("{{ f.nombre }} · {{ f.semanas }} semanas", level=2)
    _p(doc, "Objetivo: {{ f.objetivo }}")
    _tag(doc, "for a in f.acciones")
    doc.add_heading("{{ a.id }} · {{ a.descripcion }}", level=3)
    _ficha(
        doc,
        [
            ("Palanca", "{{ a.palanca }}"),
            ("Fase del embudo", "{{ a.fase }}"),
            ("Motores objetivo", "{{ a.motores }}"),
            ("Esfuerzo / impacto", "{{ a.esfuerzo }} / {{ a.impacto }}"),
            ("Responsable", "{{ a.responsable }}"),
            ("Plazo", "{{ a.plazo }}"),
            ("KPI", "{{ a.kpi }}"),
            ("Entregables", "{{ a.entregables }}"),
            ("Dependencias", "{{ a.dependencias }}"),
            ("Hallazgos que la justifican", "{{ a.hallazgos }}"),
            ("Restricciones revisadas", "{{ a.restricciones }}"),
        ],
    )
    _tag(doc, "endfor")
    _tag(doc, "endfor")


def build_template(path: Path = TEMPLATE_PATH) -> Path:
    """Escribe la plantilla en `path` y la devuelve."""
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"  # type: ignore[attr-defined]
    normal.font.size = Pt(10.5)  # type: ignore[attr-defined]
    _cabecera_y_pie(doc)
    _portada(doc)

    doc.add_heading(SECCIONES[0], level=1)
    _texto(doc, "resumen")

    _encargo(doc)

    doc.add_heading(SECCIONES[2], level=1)
    _ficha(
        doc,
        [
            ("Marca", "{{ ctx.marca }}"),
            ("Sector", "{{ ctx.sector }}"),
            ("Motores analizados", "{{ ctx.motores }}"),
            ("Fecha del estudio", "{{ ctx.fecha }}"),
            ("Origen de los datos", "{{ ctx.origen }}"),
            ("Datos sintéticos", "{{ ctx.sinteticos }}"),
            ("Estudio", "{{ ctx.study_id }}"),
        ],
    )
    doc.add_heading("Limitaciones", level=2)
    _vinetas(doc, "ctx.limitaciones")

    _diagnostico(doc)
    _competencia(doc)
    _hallazgos(doc)

    doc.add_heading(SECCIONES[6], level=1)
    _texto(doc, "estrategia.texto")
    doc.add_heading("Objetivos", level=2)
    _tabla(
        doc,
        ["KPI", "Valor actual", "Valor objetivo", "Plazo"],
        "estrategia.objetivos",
        ["kpi", "actual", "objetivo", "plazo"],
    )
    doc.add_heading("Prioridades", level=2)
    _vinetas(doc, "estrategia.prioridades")

    _plan(doc)

    doc.add_heading(SECCIONES[8], level=1)
    doc.add_heading("KPIs", level=2)
    _vinetas(doc, "medicion.kpis")
    _ficha(
        doc,
        [("Metodología", "{{ medicion.metodologia }}"), ("Cadencia", "{{ medicion.cadencia }}")],
    )

    doc.add_heading(SECCIONES[9], level=1)
    _tabla(doc, ["Riesgo", "Mitigación"], "riesgos", ["riesgo", "mitigacion"])

    doc.add_heading(SECCIONES[10], level=1)
    doc.add_heading("Hitos", level=2)
    _tabla(doc, ["Semana", "Hito"], "hoja.hitos", ["semana", "descripcion"])
    doc.add_heading("Responsabilidades", level=2)
    _tabla(doc, ["Quién", "Qué"], "hoja.responsabilidades", ["quien", "que"])
    _ficha(
        doc,
        [("Presupuesto", "{{ hoja.presupuesto }}"), ("Seguimiento", "{{ hoja.seguimiento }}")],
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path

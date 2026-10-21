"""Golden de exportación: la propuesta de Alborada sobre el kit se renderiza a Word (y PDF si hay
LibreOffice). Guarda el ejemplo en `docs/ejemplos/propuesta_alborada_ejemplo.docx`."""

import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document

from posiq.adapters.export import (
    AgencyBrandKit,
    DocxExporter,
    PdfExporter,
    SofficeNotFoundError,
)
from posiq.adapters.export.docx import fmt_cifra, fmt_score
from posiq.adapters.export.pdf import find_soffice
from posiq.adapters.export.template import SECCIONES, TEMPLATE_PATH, build_template
from posiq.domain.brief_coverage import evaluar_cobertura, puntos_del_brief
from posiq.domain.findings import detect_findings
from posiq.domain.metrics import compute_metrics
from posiq.domain.schemas import (
    Action,
    BriefSummary,
    Competencia,
    Contexto,
    Diagnostico,
    Estrategia,
    Hito,
    HojaRuta,
    Medicion,
    Objective,
    Phase,
    Plan,
    Proposal,
    Riesgo,
    UnidadCifra,
)
from posiq.ports import Exporter
from tests.golden.conftest import STUDY_ID, Kit

EJEMPLO = (
    Path(__file__).resolve().parents[2] / "docs" / "ejemplos" / "propuesta_alborada_ejemplo.docx"
)


@pytest.fixture(scope="module")
def proposal(kit: Kit, alborada_brief: BriefSummary) -> Proposal:
    metrics = compute_metrics(
        alborada_brief,
        kit.market,
        kit.prompts,
        kit.runs,
        kit.evaluations(),
        kit.sources,
        study_id=STUDY_ID,
    )
    findings = detect_findings(metrics, alborada_brief)
    f_ids = [f.id for f in findings]
    restricciones = alborada_brief.restricciones

    def accion(id_: str, descripcion: str, finding_id: str, **kw: object) -> Action:
        return Action.model_validate(
            {
                "id": id_,
                "descripcion": descripcion,
                "finding_ids": [finding_id],
                "entregables": ["Documento revisado por el comité"],
                "restricciones_revisadas": restricciones,
                **kw,
            }
        )

    plan = Plan(
        study_id=STUDY_ID,
        objetivos=[],
        fases=[
            Phase(
                nombre="Fase 0 · Fundamentos",
                semanas=4,
                objetivo="Línea base y datos estructurados",
                acciones=[
                    accion(
                        "A1",
                        "Datos estructurados schema.org de clínica y servicios",
                        f_ids[0],
                        palanca="entidad_datos",
                        esfuerzo="S",
                        impacto="M",
                        responsable="agencia",
                        plazo_semanas=4,
                        kpi="Visibilidad espontánea global",
                    )
                ],
            ),
            Phase(
                nombre="Fase 2 · Autoridad y escala",
                semanas=16,
                objetivo="Presencia en las fuentes que citan los motores",
                acciones=[
                    accion(
                        "A2",
                        "Relaciones públicas digitales con medios de salud",
                        f_ids[-1],
                        palanca="autoridad_terceros",
                        esfuerzo="L",
                        impacto="L",
                        responsable="tercero",
                        dependencias=["A1"],
                        plazo_semanas=16,
                        kpi="Apariciones con fuente Medio",
                    )
                ],
            ),
        ],
        presupuesto_estimado_eur=22000,
        respeta_restricciones=True,
    )
    return Proposal(
        study_id=STUDY_ID,
        resumen_ejecutivo=(
            "Clínica Alborada Visión cuenta con un sólido reconocimiento asistido en los "
            "asistentes de IA analizados, alcanzando una presencia del 100 % cuando los usuarios "
            "consultan directamente por la marca.\n"
            "Sin embargo, ante consultas abiertas y espontáneas sobre cirugía refractiva y control "
            "de miopía infantil, la recomendación desciende significativamente, situándose por "
            "detrás del líder del sector (Grupo Hospitalario Valdecruz).\n"
            "Se propone un plan estratégico por fases orientado a reforzar la presencia en fuentes "
            "sanitarias de referencia, generar contenido especializado para momentos de decisión y "
            "recuperar visibilidad en Barcelona, dentro de las restricciones del brief y los "
            "recursos del equipo; cada contenido requiere revisión médica y jurídica antes de "
            "publicarse."
        ),
        contexto=Contexto(
            marca=alborada_brief.marca,
            sector=alborada_brief.sector,
            motores=["ChatGPT", "Gemini", "Perplexity", "Claude"],
            fecha=datetime(2026, 10, 21),
            origen_datos="kit",
            datos_sinteticos=True,
            limitaciones=[
                "Datos sintéticos del kit del reto: reproducen con fidelidad la estructura de "
                "un estudio GEO, pero no reflejan cuotas reales de mercado.",
                "Naturaleza probabilística de los modelos de lenguaje: las respuestas varían en "
                "el tiempo y requieren seguimiento periódico.",
                "Publicidad sanitaria regulada (RD 1907/1996): el plan no promete resultados ni "
                "hace comparativas denigratorias, y cada contenido necesita revisión médica y "
                "jurídica de la clínica antes de publicarse. Las mejoras de visibilidad son "
                "hipótesis técnicas y no garantizan resultados clínicos ni comerciales.",
            ],
        ),
        diagnostico=Diagnostico(
            texto="Diagnóstico detallado sobre la visibilidad espontánea y asistida por motor, "
            "fase del embudo y ciudad.",
            metrics=metrics,
        ),
        competencia=Competencia(
            texto="Análisis comparativo de posicionamiento y brecha de fuentes frente al líder "
            "del mercado y competidores.",
            ranking=metrics.ranking,
        ),
        hallazgos=findings,
        estrategia=Estrategia(
            texto="Estrategia orientada a consolidar la prescripción espontánea en Madrid y "
            "Barcelona, impulsando la autoridad en fuentes médicas clave.",
            objetivos=[
                Objective(
                    kpi="Score de Citación",
                    valor_actual=metrics.score_global.score or 0,
                    valor_objetivo=35,
                    plazo_semanas=26,
                )
            ],
            prioridades=["Autoridad en terceros", "Contenido por ciudad"],
        ),
        plan=plan,
        medicion=Medicion(
            kpis=["Visibilidad espontánea", "Score de Citación"],
            metodologia="Re-ejecución del estudio con el mismo banco de prompts",
            cadencia="Trimestral",
        ),
        riesgos=[
            Riesgo(
                riesgo="Variabilidad de fuentes y modelos de IA",
                mitigacion="Protocolo de re-medición periódica para monitorizar cambios "
                "algorítmicos",
            ),
            Riesgo(
                riesgo="Marco regulatorio en publicidad sanitaria",
                mitigacion="Revisión médica previa de todo contenido divulgativo sin promesas de "
                "resultados",
            ),
        ],
        hoja_ruta=HojaRuta(
            hitos=[Hito(semana=0, descripcion="Medición inicial")],
            responsabilidades={"agencia": ["A1"], "tercero": ["A2"]},
            presupuesto_eur=22000,
            seguimiento="Comité mensual de seguimiento y presentación de informe evolutivo al "
            "comité de dirección",
        ),
        marcas={b.id: b.nombre for b in kit.brands},
    )


@pytest.fixture(scope="module")
def proposal_con_encargo(proposal: Proposal, alborada_brief: BriefSummary) -> Proposal:
    """La misma propuesta con el encargo del brief: todo enlazado salvo los pilotos."""
    acciones = [a.id for a in proposal.plan.acciones]
    enlaces = {p.id: acciones for p in puntos_del_brief(alborada_brief) if p.id != "publico-4"}
    encargo = evaluar_cobertura(alborada_brief, proposal.plan, proposal.hallazgos, enlaces)
    return proposal.model_copy(update={"encargo": encargo})


@pytest.fixture(scope="module")
def docx_bytes(proposal_con_encargo: Proposal) -> bytes:
    return DocxExporter().render(proposal_con_encargo, formato="docx")


def _texto(contenido: bytes) -> str:
    doc = Document(BytesIO(contenido))
    partes = [p.text for p in doc.paragraphs]
    partes += [c.text for t in doc.tables for row in t.rows for c in row.cells]
    partes += [p.text for s in doc.sections for p in s.header.paragraphs + s.footer.paragraphs]
    return "\n".join(partes)


def _partes(contenido: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(contenido)) as z:
        return {n: z.read(n) for n in z.namelist()}


def test_cumple_el_puerto() -> None:
    exporters: list[Exporter] = [DocxExporter(), PdfExporter()]
    assert all(callable(e.render) for e in exporters)


def test_docx_con_las_secciones_y_cifras(proposal: Proposal, docx_bytes: bytes) -> None:
    texto = _texto(docx_bytes)
    posiciones = [texto.index(s) for s in SECCIONES]
    assert posiciones == sorted(posiciones)
    assert "{{" not in texto and "{%" not in texto
    score = proposal.diagnostico.metrics.score_global.score
    assert fmt_score(score) in texto
    for hallazgo in proposal.hallazgos:
        assert hallazgo.titulo in texto and hallazgo.origen_cifra in texto
        assert fmt_cifra(hallazgo.cifra, hallazgo.unidad) in texto
    assert {"fraccion", "puntos", "recuento"} <= {h.unidad for h in proposal.hallazgos}
    assert "Láser Nítida" in texto and "Instituto Oftálmico Tramuntana" in texto
    for limitacion in proposal.contexto.limitaciones:
        assert limitacion in texto
    assert "posiq." in texto
    # Solo se reescribe si cambia el contenido: el zip lleva marcas de tiempo distintas cada vez.
    if not EJEMPLO.is_file() or _partes(EJEMPLO.read_bytes()) != _partes(docx_bytes):
        EJEMPLO.parent.mkdir(parents=True, exist_ok=True)
        EJEMPLO.write_bytes(docx_bytes)


def test_docx_con_lo_que_nos_habeis_pedido(
    proposal_con_encargo: Proposal, docx_bytes: bytes
) -> None:
    texto = _texto(docx_bytes)
    encargo = proposal_con_encargo.encargo
    assert encargo is not None
    inicio = texto.index(SECCIONES[1])
    assert inicio < texto.index(SECCIONES[2]) < texto.index(SECCIONES[3])
    seccion = texto[inicio : texto.index(SECCIONES[2])]
    # Los puntos literales, en viñetas dentro de la sección.
    for punto in encargo.cobertura:
        assert punto.texto in seccion
    assert "18.000–27.000 € al año" in seccion
    # La tabla de cobertura (las tablas se leen aparte de los párrafos).
    filas = [
        [c.text for c in fila.cells]
        for t in Document(BytesIO(docx_bytes)).tables
        for fila in t.rows
        if t.rows[0].cells[0].text == "Punto"
    ]
    assert filas[0] == ["Punto", "Lo que pedisteis", "Dónde se trata", "Estado"]
    por_texto = {f[1]: f for f in filas[1:]}
    assert len(por_texto) == len(encargo.cobertura)
    assert por_texto["Madrid"] == ["Ciudad", "Madrid", "Acciones A1, A2", "Cubierto"]
    restriccion = por_texto["Sin comparativas denigratorias"]
    assert restriccion[2] == "La declaran todas las acciones del plan."
    presupuesto = por_texto["18.000–27.000 € al año"]
    assert presupuesto[2] == "Plan de 22.000 €, dentro del máximo de 27.000 €."
    pilotos = por_texto["Profesionales con requisitos específicos (pilotos)"]
    assert pilotos[2].startswith("pendiente: Ninguna acción ni hallazgo")
    assert [f[3] for f in filas[1:]].count("Pendiente") == 1


def test_docx_sin_encargo(proposal: Proposal) -> None:
    texto = _texto(DocxExporter().render(proposal, formato="docx"))
    assert SECCIONES[1] in texto and "no registra el encargo" in texto


@pytest.mark.parametrize(
    ("cifra", "unidad", "esperado"),
    [
        (0.15, "fraccion", "15,0 %"),
        (40.53, "puntos", "40,53 puntos"),
        (1.0, "puntos", "1 punto"),
        (37.0, "recuento", "37"),
        (22000.0, "eur", "22.000 €"),
    ],
)
def test_cifra_segun_unidad(cifra: float, unidad: UnidadCifra, esperado: str) -> None:
    assert fmt_cifra(cifra, unidad) == esperado


def test_sin_marcas_cae_a_los_ids(proposal: Proposal) -> None:
    sin_marcas = proposal.model_copy(update={"marcas": {}})
    texto = _texto(DocxExporter().render(sin_marcas, formato="docx"))
    assert "Laser Nitida" in texto and "Láser Nítida" not in texto
    assert proposal.contexto.marca in texto


def test_cabecera_con_marca_de_agencia(proposal: Proposal) -> None:
    kit = AgencyBrandKit(
        nombre="Agencia Norte", color_primario="#AA3300", pie_de_pagina="Confidencial"
    )
    texto = _texto(DocxExporter().render(proposal, formato="docx", marca_agencia=kit))
    assert "Agencia Norte" in texto and "Confidencial" in texto


def test_docx_exporter_rechaza_pdf(proposal: Proposal) -> None:
    with pytest.raises(ValueError, match="PdfExporter"):
        DocxExporter().render(proposal, formato="pdf")


def test_plantilla_reproducible(tmp_path: Path) -> None:
    nueva = build_template(tmp_path / "propuesta.docx")
    partes = ("word/document.xml", "word/header1.xml", "word/footer1.xml")
    with zipfile.ZipFile(TEMPLATE_PATH) as a, zipfile.ZipFile(nueva) as b:
        for parte in partes:
            assert a.read(parte) == b.read(parte), f"plantilla desactualizada: {parte}"


def test_pdf_sin_libreoffice_da_error_claro(
    proposal: Proposal, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("posiq.adapters.export.pdf.find_soffice", lambda: None)
    with pytest.raises(SofficeNotFoundError, match="LibreOffice"):
        PdfExporter().render(proposal, formato="pdf")


@pytest.mark.skipif(find_soffice() is None, reason="LibreOffice (soffice) no está instalado")
def test_pdf_con_libreoffice(proposal: Proposal) -> None:
    pdf = PdfExporter().render(proposal, formato="pdf")
    assert pdf.startswith(b"%PDF")

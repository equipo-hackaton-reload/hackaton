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
            "Alborada aparece poco cuando nadie la nombra.\nProponemos un plan por fases."
        ),
        contexto=Contexto(
            marca=alborada_brief.marca,
            sector=alborada_brief.sector,
            motores=["ChatGPT", "Gemini", "Perplexity", "Claude"],
            fecha=datetime(2026, 10, 21),
            origen_datos="kit",
            datos_sinteticos=True,
            limitaciones=[
                "Datos sintéticos del kit",
                "Los motores no son deterministas",
                "No se garantizan resultados",
            ],
        ),
        diagnostico=Diagnostico(
            texto="Diagnóstico sobre la visibilidad espontánea.", metrics=metrics
        ),
        competencia=Competencia(
            texto="El líder concentra las recomendaciones.", ranking=metrics.ranking
        ),
        hallazgos=findings,
        estrategia=Estrategia(
            texto="Ganar recomendación espontánea en Madrid y Barcelona.",
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
        riesgos=[Riesgo(riesgo="Cambios de modelo", mitigacion="Re-medición periódica")],
        hoja_ruta=HojaRuta(
            hitos=[Hito(semana=0, descripcion="Medición inicial")],
            responsabilidades={"agencia": ["A1"], "tercero": ["A2"]},
            presupuesto_eur=22000,
            seguimiento="Comité mensual",
        ),
    )


@pytest.fixture(scope="module")
def docx_bytes(proposal: Proposal) -> bytes:
    return DocxExporter().render(proposal, formato="docx")


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


def test_docx_con_las_diez_secciones_y_cifras(proposal: Proposal, docx_bytes: bytes) -> None:
    texto = _texto(docx_bytes)
    posiciones = [texto.index(s) for s in SECCIONES]
    assert posiciones == sorted(posiciones)
    assert "{{" not in texto and "{%" not in texto
    score = proposal.diagnostico.metrics.score_global.score
    assert fmt_score(score) in texto
    hallazgo = proposal.hallazgos[0]
    assert hallazgo.titulo in texto and fmt_cifra(hallazgo.cifra) in texto
    assert hallazgo.origen_cifra in texto
    for limitacion in proposal.contexto.limitaciones:
        assert limitacion in texto
    assert "posiq." in texto
    # Solo se reescribe si cambia el contenido: el zip lleva marcas de tiempo distintas cada vez.
    if not EJEMPLO.is_file() or _partes(EJEMPLO.read_bytes()) != _partes(docx_bytes):
        EJEMPLO.parent.mkdir(parents=True, exist_ok=True)
        EJEMPLO.write_bytes(docx_bytes)


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

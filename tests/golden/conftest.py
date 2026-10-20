"""Datos del kit, brief, métricas, hallazgos y plan de ejemplo de Alborada (sin red).

Las funciones normales (`load_kit`, `alborada_brief_summary`, `example_plan`…) también las usa
`scripts/evaluate_system.py`; las fixtures solo las envuelven.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from posiq.domain import kit_loader as kl
from posiq.domain.detection import detect_in_run, evaluation_from_detection
from posiq.domain.findings import detect_findings
from posiq.domain.metrics import compute_metrics
from posiq.domain.schemas import (
    Action,
    Brand,
    BriefSummary,
    Evaluation,
    Finding,
    Market,
    Metrics,
    Objective,
    Phase,
    Plan,
    PromptInstance,
    Run,
    Source,
)

STUDY_ID = "S-kit-alborada"
KIT_DIR = Path(__file__).resolve().parents[2] / "data" / "kit" / "02_Datos" / "caso_oftalmologia"


@dataclass(frozen=True)
class Kit:
    brands: list[Brand]
    prompts: list[PromptInstance]
    runs: list[Run]
    sources: list[Source]
    sample: list[Evaluation]

    @property
    def market(self) -> Market:
        return Market(marcas=self.brands, confirmado_por_humano=True)

    def evaluations(self) -> list[Evaluation]:
        """Etiquetas humanas de la muestra donde existen; detección por reglas en el resto."""
        humanas = {e.id: e for e in self.sample}
        brands = {b.id: b for b in self.brands}
        out: list[Evaluation] = []
        for run in self.runs:
            detections = detect_in_run(run, self.brands)
            for brand_id in run.marcas_a_evaluar:
                out.append(
                    humanas.get(f"{run.id}:{brand_id}")
                    or evaluation_from_detection(run, brands[brand_id], detections.get(brand_id))
                )
        return out


def load_kit(kit_dir: Path = KIT_DIR, study_id: str = STUDY_ID) -> Kit:
    brands = kl.load_brands(kit_dir / "marcas.csv")
    sources = kl.load_sources(kit_dir / "fuentes_catalogo.csv")
    templates = kl.load_prompt_bank(kit_dir / "banco_prompts.csv")
    return Kit(
        brands=brands,
        prompts=kl.load_prompt_instances(kit_dir / "ejecuciones.csv", templates, brands),
        runs=kl.load_runs(kit_dir / "ejecuciones.csv", brands, sources, study_id),
        sources=sources,
        sample=kl.load_evaluated_sample(kit_dir / "muestra_evaluada.csv", brands, study_id),
    )


def alborada_brief_summary() -> BriefSummary:
    """Ficha del brief de ejemplo (data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md)."""
    return BriefSummary(
        marca="Clínica Alborada Visión",
        sector="Sanidad privada",
        subsector="Oftalmología (cirugía refractiva y cataratas)",
        servicios_prioritarios=["Cirugía refractiva", "Control de miopía infantil"],
        publicos=[
            "Adultos de 25 a 50 años con miopía o astigmatismo",
            "Mayores de 60 años con cataratas y sus hijos",
            "Padres de niños con miopía progresiva",
            "Profesionales con requisitos específicos (pilotos)",
        ],
        ciudades=["Madrid", "Barcelona"],
        competidores_declarados=[
            "Instituto Oftálmico Tramuntana",
            "Láser Nítida",
            "Grupo Hospitalario Valdecruz",
        ],
        presupuesto_anual_eur=(18000, 27000),
        equipo=[
            "1 responsable de marketing",
            "1 persona de comunicación a media jornada",
            "Agencia colaboradora",
        ],
        restricciones=[
            "Publicidad sanitaria regulada: no prometer resultados",
            "Sin comparativas denigratorias",
        ],
        objetivos=[
            "Recomendación espontánea en asistentes de IA en Madrid y Barcelona",
            "+25 % de primeras visitas de cirugía refractiva en 12 meses",
        ],
        audiencia_del_entregable="Comité de dirección (perfil mixto médico y de negocio)",
        tono="Riguroso, cercano y sin sensacionalismo",
    )


def alborada_metrics(kit: Kit, brief: BriefSummary) -> Metrics:
    return compute_metrics(
        brief, kit.market, kit.prompts, kit.runs, kit.evaluations(), kit.sources, study_id=STUDY_ID
    )


def _action(id: str, finding_ids: list[str], brief: BriefSummary, **kw: object) -> Action:
    data: dict[str, object] = {
        "id": id,
        "finding_ids": finding_ids,
        "restricciones_revisadas": list(brief.restricciones),
    } | kw
    return Action.model_validate(data)


def example_plan(findings: list[Finding], brief: BriefSummary, study_id: str = STUDY_ID) -> Plan:
    """Plan de ejemplo para Alborada, enlazado a los hallazgos del kit que existan.

    Lo escribió una persona a mano para probar la simulación y la evaluación de calidad; no es
    salida del sistema. Las acciones cuyos hallazgos no existen se descartan.
    """
    ids = {f.id for f in findings}

    def accion(id: str, finding_ids: list[str], **kw: object) -> Action | None:
        validos = [f for f in finding_ids if f in ids]
        return _action(id, validos, brief, **kw) if validos else None

    fases = [
        (
            "Fase 0 · Fundamentos",
            6,
            "Línea base y datos de entidad coherentes",
            [
                accion(
                    "A0-1",
                    ["F-brecha-lider"],
                    descripcion="Medición base: ejecutar el banco de 52 prompts en los cuatro "
                    "motores y fijar los KPI de visibilidad espontánea por motor, fase y ciudad.",
                    palanca="medicion",
                    esfuerzo="S",
                    impacto="S",
                    responsable="Agencia",
                    entregables=["Informe de línea base"],
                    plazo_semanas=2,
                    kpi="Score de Citación espontáneo",
                ),
                accion(
                    "A0-2",
                    ["F-fuente-lider", "F-motor-debil"],
                    descripcion="Implementar datos estructurados schema.org (MedicalClinic y "
                    "Physician) en las 60 URLs y unificar nombre, dirección y servicios de "
                    "Clínica Alborada Visión en los directorios sanitarios.",
                    palanca="entidad_datos",
                    fase_embudo="descubrimiento",
                    esfuerzo="M",
                    impacto="M",
                    responsable="Agencia (desarrollo web)",
                    entregables=["Marcado schema.org validado", "Fichas de directorios"],
                    plazo_semanas=6,
                    kpi="Visibilidad espontánea en descubrimiento",
                ),
            ],
        ),
        (
            "Fase 1 · Quick wins",
            8,
            "Contenido que responde a los prompts de decisión y reputación activa",
            [
                accion(
                    "A1-1",
                    ["F-caida-embudo", "F-recomendacion-debil"],
                    descripcion="Publicar FAQ y páginas de cirugía refractiva y miopía infantil "
                    "redactadas a partir de los prompts de decisión y precio del banco, con "
                    "precios, financiación y proceso explicados sin prometer resultados.",
                    palanca="contenido",
                    fase_embudo="decision",
                    esfuerzo="M",
                    impacto="M",
                    responsable="Responsable de marketing",
                    dependencias=["A0-2"],
                    entregables=["8 páginas FAQ publicadas"],
                    plazo_semanas=8,
                    kpi="Visibilidad espontánea en decisión",
                ),
                accion(
                    "A1-2",
                    ["F-ciudad-barcelona"],
                    descripcion="Pedir reseñas a pacientes del centro de Barcelona y responder a "
                    "todas las reseñas de Google en menos de 72 horas.",
                    palanca="reputacion",
                    esfuerzo="S",
                    impacto="M",
                    responsable="Comunicación (media jornada)",
                    entregables=["Protocolo de reseñas", "Informe mensual de reseñas"],
                    plazo_semanas=8,
                    kpi="Reseñas nuevas del centro de Barcelona",
                ),
            ],
        ),
        (
            "Fase 2 · Autoridad y escala",
            16,
            "Presencia en las fuentes que citan los motores",
            [
                accion(
                    "A2-1",
                    ["F-fuente-lider", "F-motor-debil"],
                    descripcion="Conseguir ficha completa y verificada en directoriomedico.example "
                    "y presencia en rankingclinicas.example y guiaoftalmologia.example.",
                    palanca="autoridad_terceros",
                    motores_objetivo=["ChatGPT", "Claude"],
                    esfuerzo="L",
                    impacto="L",
                    responsable="Agencia (relaciones públicas)",
                    dependencias=["A0-2"],
                    entregables=["Fichas publicadas", "Candidatura a 2 rankings"],
                    plazo_semanas=16,
                    kpi="Visibilidad espontánea en ChatGPT y Claude",
                ),
                accion(
                    "A2-2",
                    ["F-ciudad-barcelona"],
                    descripcion="Guía local de cirugía refractiva en Barcelona con el centro "
                    "abierto en 2024: equipo médico, tecnología, horarios y cómo pedir cita.",
                    palanca="contenido",
                    esfuerzo="M",
                    impacto="M",
                    responsable="Responsable de marketing",
                    entregables=["Guía publicada"],
                    plazo_semanas=6,
                    kpi="Visibilidad espontánea en Barcelona",
                ),
                accion(
                    "A2-3",
                    ["F-brecha-lider", "F-asistida-vs-espontanea"],
                    descripcion="Artículos de divulgación sobre control de miopía infantil en "
                    "medios de salud (diariosalud.example, saludactual.example) firmados por "
                    "oftalmólogos del equipo, sin comparativas ni promesas de resultados.",
                    palanca="autoridad_terceros",
                    fase_embudo="comparacion",
                    esfuerzo="M",
                    impacto="M",
                    responsable="Comunicación con la agencia",
                    entregables=["3 artículos publicados"],
                    plazo_semanas=12,
                    kpi="Menciones en medios citados por los motores",
                ),
            ],
        ),
        (
            "Fase 3 · Optimización y medición",
            12,
            "Medir, aprender y ajustar",
            [
                accion(
                    "A3-1",
                    ["F-brecha-lider"],
                    descripcion="Re-medición trimestral con el mismo banco, motores y "
                    "repeticiones, comparada con la línea base.",
                    palanca="medicion",
                    esfuerzo="S",
                    impacto="S",
                    responsable="Agencia",
                    entregables=["Informe de evolución trimestral"],
                    plazo_semanas=12,
                    kpi="Score de Citación espontáneo",
                ),
                accion(
                    "A3-2",
                    ["F-motor-debil"],
                    descripcion="Vídeos cortos en YouTube en los que oftalmólogos del equipo "
                    "responden dudas frecuentes sobre cirugía refractiva.",
                    palanca="comunidades",
                    esfuerzo="M",
                    impacto="S",
                    responsable="Comunicación (media jornada)",
                    entregables=["6 vídeos publicados"],
                    plazo_semanas=12,
                    kpi="Visibilidad espontánea por motor",
                ),
            ],
        ),
    ]
    return Plan(
        study_id=study_id,
        objetivos=[
            Objective(
                kpi="Score de Citación espontáneo",
                valor_actual=25.9,
                valor_objetivo=35,
                plazo_semanas=42,
            ),
            Objective(
                kpi="Visibilidad espontánea en Barcelona",
                valor_actual=0.04,
                valor_objetivo=0.2,
                plazo_semanas=42,
            ),
        ],
        fases=[
            Phase(
                nombre=nombre,
                semanas=semanas,
                objetivo=objetivo,
                acciones=[a for a in acciones if a is not None],
            )
            for nombre, semanas, objetivo, acciones in fases
        ],
        presupuesto_estimado_eur=22000,
        respeta_restricciones=True,
    )


@pytest.fixture(scope="session")
def kit(kit_dir: Path) -> Kit:
    return load_kit(kit_dir)


@pytest.fixture(scope="session")
def alborada_brief() -> BriefSummary:
    return alborada_brief_summary()


@pytest.fixture(scope="session")
def alborada_study(kit: Kit, alborada_brief: BriefSummary) -> tuple[Metrics, list[Finding], Plan]:
    """Métricas, hallazgos y plan de ejemplo del estudio del kit."""
    metrics = alborada_metrics(kit, alborada_brief)
    findings = detect_findings(metrics, alborada_brief)
    return metrics, findings, example_plan(findings, alborada_brief)

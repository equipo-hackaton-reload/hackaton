"""Datos de demo copiados de las fixtures golden; no requiere pytest ni llamadas externas."""

from datetime import datetime
from pathlib import Path

from posiq.domain import kit_loader as kl
from posiq.domain.schemas import (
    Action,
    Brand,
    BriefSummary,
    Competencia,
    Contexto,
    Diagnostico,
    Estrategia,
    Finding,
    Hito,
    HojaRuta,
    Medicion,
    Metrics,
    Objective,
    Phase,
    Plan,
    Proposal,
    Riesgo,
)

STUDY_ID = "S-kit-alborada"

KIT_DIR = Path(__file__).resolve().parents[4] / "data" / "kit" / "02_Datos" / "caso_oftalmologia"


# Identidad deseada que dice el brief de Alborada, con su texto literal: la propuesta de valor del
# apartado 2 y sus «Diferenciales».
POSICIONAMIENTO_ALBORADA = (
    "Clínica oftalmológica privada de tamaño medio con una oferta centrada en la cirugía que "
    "permite dejar las gafas y en el tratamiento de cataratas"
)
ATRIBUTOS_ALBORADA = (
    "Seguimiento postoperatorio personalizado incluido durante 12 meses",
    "Valoración preoperatoria completa en una sola visita",
    "Equipo médico estable y bien valorado por los pacientes",
)


def identidad_deseada_alborada(brief_texto: str) -> dict[str, str | list[str]]:
    """Posicionamiento y atributos deseados de Alborada que aparecen tal cual en `brief_texto`.

    Lo que el texto no contiene se queda vacío: el fixture no inventa identidad de marca.
    """
    texto = " ".join(brief_texto.split()).casefold()
    return {
        "posicionamiento_deseado": (
            POSICIONAMIENTO_ALBORADA if POSICIONAMIENTO_ALBORADA.casefold() in texto else ""
        ),
        "atributos_deseados": [a for a in ATRIBUTOS_ALBORADA if a.casefold() in texto],
    }


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


def alborada_proposal(
    metrics: Metrics,
    findings: list[Finding],
    plan: Plan,
    brief: BriefSummary,
    brands: list[Brand] | None = None,
) -> Proposal:
    """Propuesta mínima válida de Alborada sobre el plan de ejemplo (sin cifras inventadas).

    `brands` rellena `Proposal.marcas` (id → nombre legible); por defecto, las marcas del kit.
    """
    brands = brands if brands is not None else kl.load_brands(KIT_DIR / "marcas.csv")
    semana = 0
    hitos: list[Hito] = []
    for fase in plan.fases:
        semana += fase.semanas
        hitos.append(Hito(semana=semana, descripcion=f"Fin de {fase.nombre}"))
    responsabilidades: dict[str, list[str]] = {}
    for accion in plan.acciones:
        responsabilidades.setdefault(accion.responsable, []).append(accion.id)
    return Proposal(
        study_id=metrics.study_id,
        resumen_ejecutivo=(
            f"{brief.marca} aparece en los asistentes de IA sobre todo cuando la pregunta la "
            "nombra, pero mucho menos cuando el usuario pregunta en general, y queda por detrás "
            "del líder del mercado. Se propone un plan por fases centrado en las fuentes que citan "
            "los motores, contenido que responde a preguntas reales y Barcelona. Datos sintéticos "
            "del kit del hackathon."
        ),
        contexto=Contexto(
            marca=brief.marca,
            sector=f"{brief.sector} · {brief.subsector}",
            motores=["ChatGPT", "Gemini", "Perplexity", "Claude"],
            fecha=datetime(2026, 9, 14),
            origen_datos="kit",
            datos_sinteticos=True,
            limitaciones=[
                "Datos sintéticos: reproducen la estructura de un estudio real, no su resultado.",
                "Evaluaciones de la muestra etiquetadas por personas; el resto, solo por reglas.",
                "Foto en una fecha: los asistentes cambian y hay que volver a medir.",
            ],
        ),
        diagnostico=Diagnostico(
            texto="Diagnóstico de visibilidad espontánea y asistida por motor, fase y ciudad.",
            metrics=metrics,
        ),
        competencia=Competencia(
            texto="Ranking por Score de Citación espontáneo frente a competidores y líder.",
            ranking=list(metrics.ranking),
        ),
        hallazgos=findings,
        estrategia=Estrategia(
            texto="Ganar presencia en las fuentes que citan los motores y responder a las "
            "preguntas de comparación y decisión, empezando por los motores más débiles.",
            objetivos=list(plan.objetivos),
            prioridades=["Autoridad en terceros", "Contenido de decisión", "Barcelona"],
        ),
        plan=plan,
        medicion=Medicion(
            kpis=["Score de Citación espontáneo", "Visibilidad espontánea por motor y ciudad"],
            metodologia="Mismo banco de prompts, motores y repeticiones que la línea base.",
            cadencia="Trimestral",
        ),
        riesgos=[
            Riesgo(
                riesgo="Los asistentes cambian de modelo o de fuentes durante el plan",
                mitigacion="Re-medición trimestral y comparación solo entre estudios compatibles",
            ),
            Riesgo(
                riesgo="Publicidad sanitaria regulada",
                mitigacion="Revisión de cada contenido frente a las restricciones del brief",
            ),
        ],
        hoja_ruta=HojaRuta(
            hitos=hitos,
            responsabilidades=responsabilidades,
            presupuesto_eur=plan.presupuesto_estimado_eur,
            seguimiento="Informe de evolución trimestral al comité de dirección",
        ),
        marcas={b.id: b.nombre for b in brands},
    )

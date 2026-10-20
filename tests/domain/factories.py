"""Constructores mínimos de modelos para los tests del dominio."""

from datetime import datetime

from posiq.domain.schemas import (
    Action,
    Brand,
    BriefSummary,
    Evaluation,
    Run,
    Source,
)


def brand(id: str = "alborada", nombre: str = "Clínica Alborada Visión", **kw: object) -> Brand:
    data: dict[str, object] = {"id": id, "nombre": nombre, "rol": "foco"} | kw
    return Brand.model_validate(data)


def run(id: str = "EJ-1", texto: str = "", marcas: list[str] | None = None, **kw: object) -> Run:
    data: dict[str, object] = {
        "id": id,
        "prompt_id": "P-1",
        "motor": "ChatGPT",
        "repeticion": 1,
        "fecha": datetime(2026, 9, 14),
        "texto_respuesta": texto,
        "marcas_a_evaluar": marcas or ["alborada"],
    } | kw
    return Run.model_validate(data)


def evaluation(
    brand_id: str = "alborada", run_id: str = "EJ-1", aparece: bool = True, **kw: object
) -> Evaluation:
    data: dict[str, object] = {
        "id": f"{run_id}:{brand_id}",
        "run_id": run_id,
        "brand_id": brand_id,
        "aparece": aparece,
        "posicion": 1 if aparece else None,
        "fuerza": 3 if aparece else 0,
        "confianza": 1.0,
        "origen": "humano",
    } | kw
    return Evaluation.model_validate(data)


def source(dominio: str = "rankingclinicas.example", tipo: str = "Ranking / institución") -> Source:
    calidad = {"Ranking / institución": 1.0, "Medio": 0.9, "Web propia": 0.7}.get(tipo, 0.6)
    return Source.model_validate({"dominio": dominio, "tipo": tipo, "calidad": calidad})


def action(id: str = "A1", finding_ids: list[str] | None = None, **kw: object) -> Action:
    data: dict[str, object] = {
        "id": id,
        "descripcion": "Publicar FAQ de cirugía refractiva",
        "finding_ids": ["F1"] if finding_ids is None else finding_ids,
        "palanca": "contenido",
        "esfuerzo": "S",
        "impacto": "M",
        "responsable": "Marketing",
        "entregables": ["FAQ publicada"],
        "plazo_semanas": 4,
        "kpi": "visibilidad espontánea",
    } | kw
    return Action.model_validate(data)


def brief(**kw: object) -> BriefSummary:
    data: dict[str, object] = {
        "marca": "Clínica Alborada Visión",
        "sector": "Sanidad privada",
        "subsector": "Oftalmología",
        "servicios_prioritarios": ["Cirugía refractiva", "Control de miopía infantil"],
        "publicos": ["Adultos 25-50 con miopía"],
        "ciudades": ["Madrid", "Barcelona"],
        "competidores_declarados": ["Instituto Oftálmico Tramuntana", "Láser Nítida"],
        "presupuesto_anual_eur": (18000, 27000),
        "equipo": ["1 responsable de marketing"],
        "restricciones": ["No prometer resultados"],
        "objetivos": ["Recomendación espontánea en Madrid y Barcelona"],
        "audiencia_del_entregable": "Comité de dirección",
        "tono": "Riguroso",
    } | kw
    return BriefSummary.model_validate(data)

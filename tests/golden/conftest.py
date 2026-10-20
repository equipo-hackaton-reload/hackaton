"""Datos del kit y brief de Alborada para los tests golden (sin red)."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from posiq.domain import kit_loader as kl
from posiq.domain.detection import detect_in_run, evaluation_from_detection
from posiq.domain.schemas import (
    Brand,
    BriefSummary,
    Evaluation,
    Market,
    PromptInstance,
    Run,
    Source,
)

STUDY_ID = "S-kit-alborada"


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


@pytest.fixture(scope="session")
def kit(kit_dir: Path) -> Kit:
    brands = kl.load_brands(kit_dir / "marcas.csv")
    sources = kl.load_sources(kit_dir / "fuentes_catalogo.csv")
    templates = kl.load_prompt_bank(kit_dir / "banco_prompts.csv")
    return Kit(
        brands=brands,
        prompts=kl.load_prompt_instances(kit_dir / "ejecuciones.csv", templates, brands),
        runs=kl.load_runs(kit_dir / "ejecuciones.csv", brands, sources, STUDY_ID),
        sources=sources,
        sample=kl.load_evaluated_sample(kit_dir / "muestra_evaluada.csv", brands, STUDY_ID),
    )


@pytest.fixture(scope="session")
def alborada_brief() -> BriefSummary:
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

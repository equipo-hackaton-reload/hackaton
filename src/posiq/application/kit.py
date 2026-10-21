"""Datos del kit que usa el modo `kit`: marcas, catálogo de fuentes y banco de prompts instanciado.

El banco de plantillas (`templates`) es también el que el LLM instancia en modo real.

Se leen una vez por carpeta con `domain.kit_loader`. El catálogo de fuentes se usa también en modo
real: es el único catálogo con tipo y calidad de cada dominio.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from posiq.domain import kit_loader as kl
from posiq.domain.schemas import Brand, PromptInstance, PromptTemplate, Run, Source

_KIT_STUDY = "kit"


@dataclass(frozen=True)
class KitData:
    brands: list[Brand]
    sources: list[Source]
    prompts: list[PromptInstance]
    runs: list[Run]
    templates: list[PromptTemplate] = field(default_factory=list)

    def brands_in_runs(self) -> list[Brand]:
        """Marcas del kit que alguna ejecución pide evaluar, en el orden de `marcas.csv`."""
        ids = {b for r in self.runs for b in r.marcas_a_evaluar}
        return [b for b in self.brands if b.id in ids]


@lru_cache(maxsize=4)
def load_kit(kit_dir: str) -> KitData:
    path = Path(kit_dir)
    brands = kl.load_brands(path / "marcas.csv")
    sources = kl.load_sources(path / "fuentes_catalogo.csv")
    templates = kl.load_prompt_bank(path / "banco_prompts.csv")
    prompts = kl.load_prompt_instances(path / "ejecuciones.csv", templates, brands)
    runs = kl.load_runs(path / "ejecuciones.csv", brands, sources, _KIT_STUDY)
    return KitData(brands, sources, prompts, runs, templates)


def load_sources(kit_dir: str) -> list[Source]:
    return load_kit(kit_dir).sources

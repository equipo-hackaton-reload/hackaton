"""Prompts versionados de los nodos LLM (`<nodo>.v<N>.md`) y su cargador.

Cada fichero lleva una cabecera YAML (`name`, `version`, `schema` de salida y `state`: claves que el
nodo pasa como datos) y el texto de instrucciones. Los prompts no contienen datos ni marcadores de
interpolación: todo dato llega en `state` y el adaptador LLM lo envía aparte.
"""

from functools import cache
from pathlib import Path
from typing import Self

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator

from posiq.domain.schemas import PromptInstance

PROMPTS_DIR = Path(__file__).parent


class PromptSet(BaseModel):
    """Salida del nodo `prompts`: el banco instanciado para un estudio."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompts: list[PromptInstance] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_unicos(self) -> Self:
        ids = [p.id for p in self.prompts]
        if len(ids) != len(set(ids)):
            raise ValueError("PromptSet tiene ids repetidos")
        return self

    @property
    def espontaneos(self) -> list[PromptInstance]:
        return [p for p in self.prompts if p.tipo == "espontaneo"]

    @property
    def asistidos(self) -> list[PromptInstance]:
        return [p for p in self.prompts if p.tipo == "asistido"]


class PromptSpec(BaseModel):
    """Un prompt cargado: cabecera validada y texto de instrucciones."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: int = Field(ge=1)
    schema_name: str = Field(alias="schema")
    state: dict[str, str] = Field(min_length=1)
    texto: str = Field(min_length=1)

    @property
    def version_tag(self) -> str:
        """Lo que se registra en `Trace.prompt_version`, p. ej. `intake.v1`."""
        return f"{self.name}.v{self.version}"


def parse_prompt(contenido: str) -> PromptSpec:
    """Separa y valida la cabecera YAML (`---` ... `---`) y el cuerpo."""
    if not contenido.startswith("---"):
        raise ValueError("el prompt no empieza con cabecera YAML (---)")
    _, cabecera, cuerpo = contenido.split("---", 2)
    datos = yaml.safe_load(cabecera)
    if not isinstance(datos, dict):
        raise ValueError("la cabecera YAML del prompt no es un mapa")
    return PromptSpec.model_validate({**datos, "texto": cuerpo.strip()})


@cache
def load_prompt(name: str, version: int = 1) -> PromptSpec:
    spec = parse_prompt((PROMPTS_DIR / f"{name}.v{version}.md").read_text(encoding="utf-8"))
    if (spec.name, spec.version) != (name, version):
        raise ValueError(f"la cabecera de {name}.v{version}.md no coincide con su nombre")
    return spec

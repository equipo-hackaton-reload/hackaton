"""Marca de la agencia que firma la propuesta (cabecera, color y pie del documento)."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AgencyBrandKit(BaseModel):
    """Identidad visual de la agencia. `color_primario` en hexadecimal `#RRGGBB`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    nombre: str = Field(min_length=1)
    logo_path: Path | None = None
    color_primario: str = Field(default="#1F3A5F", pattern=r"^#[0-9A-Fa-f]{6}$")
    pie_de_pagina: str = ""

    @property
    def color_hex(self) -> str:
        """Color sin `#`, como lo espera Word."""
        return self.color_primario.lstrip("#").upper()

"""Exportación a PDF: genera el docx y lo convierte con LibreOffice headless."""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from posiq.adapters.export.branding import AgencyBrandKit
from posiq.adapters.export.diferencial import DatosDiferencial
from posiq.adapters.export.docx import DocxExporter
from posiq.domain.schemas import Proposal

CANDIDATOS = ("soffice", "soffice.exe", "libreoffice")
RUTAS_HABITUALES = (
    Path("C:/Program Files/LibreOffice/program/soffice.exe"),
    Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
)
TIMEOUT_S = 120


class SofficeNotFoundError(RuntimeError):
    """No hay LibreOffice (`soffice`) para convertir a PDF."""


def find_soffice() -> Path | None:
    for nombre in CANDIDATOS:
        if ruta := shutil.which(nombre):
            return Path(ruta)
    return next((r for r in RUTAS_HABITUALES if r.is_file()), None)


class PdfExporter:
    """`Exporter` a PDF (y a docx, delegando en `DocxExporter`)."""

    def __init__(self, docx: DocxExporter | None = None, soffice: Path | None = None) -> None:
        self.docx = docx or DocxExporter()
        self.soffice = soffice

    def render(
        self,
        proposal: Proposal,
        *,
        formato: Literal["docx", "pdf"],
        marca_agencia: AgencyBrandKit | None = None,
        diferencial: DatosDiferencial | None = None,
    ) -> bytes:
        contenido = self.docx.render(
            proposal, formato="docx", marca_agencia=marca_agencia, diferencial=diferencial
        )
        return contenido if formato == "docx" else self.convert(contenido)

    def convert(self, docx: bytes) -> bytes:
        soffice = self.soffice or find_soffice()
        if soffice is None:
            raise SofficeNotFoundError(
                "No se encuentra LibreOffice (`soffice`) para exportar a PDF. Instálalo "
                "(p. ej. `apt install libreoffice-writer`) o exporta en docx."
            )
        with tempfile.TemporaryDirectory(prefix="posiq-pdf-") as tmp:
            carpeta = Path(tmp)
            origen = carpeta / "propuesta.docx"
            origen.write_bytes(docx)
            # Perfil propio: dos conversiones simultáneas no comparten el bloqueo de LibreOffice.
            perfil = (carpeta / "perfil").as_uri()
            resultado = subprocess.run(
                [
                    str(soffice),
                    f"-env:UserInstallation={perfil}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(carpeta),
                    str(origen),
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_S,
                check=False,
            )
            destino = carpeta / "propuesta.pdf"
            if resultado.returncode != 0 or not destino.is_file():
                raise RuntimeError(
                    f"LibreOffice no pudo convertir a PDF (código {resultado.returncode}): "
                    f"{resultado.stderr.strip() or resultado.stdout.strip()}"
                )
            return destino.read_bytes()

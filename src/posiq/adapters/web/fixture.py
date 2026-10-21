"""`WebFetcher` de ejemplo para el modo kit: CASO SINTÉTICO, sin red (ADR 0019, «Modo kit y demo»).

Los dominios del kit son `.example`: no existen y no se pueden descargar. Este adaptador sirve
respuestas fijas escritas a mano desde `fixtures/<dominio>/respuestas.json` (ruta → estado,
content-type y fichero). Todo es ficticio (`data/kit/00_LEEME_Guia_del_kit.md`): ninguna cifra que
salga de aquí es de una web real, y la auditoría que lo usa lleva `origen="fixture"`.

`alboradavision.example` (Clínica Alborada Visión) reproduce fallos típicos:
- robots.txt bloquea `GPTBot` en `/` (el resto, permitido) y declara el sitemap;
- portada que solo pinta texto con JavaScript (casi nada visible sin JS);
- JSON-LD `Organization` sin `sameAs`;
- sin `/llms.txt` ni rutas `/.well-known/` (404), sin cabecera `Link`, sin Markdown negociado.

Aplica las mismas reglas de destino que el fetcher real (`url_permitida`): no hay atajo que
permita a la fixture servir otro host.
"""

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from posiq.domain.web_audit_schemas import MAX_CONTENIDO_CHARS, RespuestaWeb, url_permitida

DIRECTORIO_FIXTURES: Final = Path(__file__).parent / "fixtures"
AVISO_SINTETICO: Final = (
    "CASO SINTÉTICO del reto: respuestas inventadas de una web ficticia; no son de una web real."
)
_NO_ENCONTRADO: Final = "<!doctype html><title>404</title><p>No encontrado</p>"


@lru_cache(maxsize=16)
def _manifiesto(directorio: str, host: str) -> dict[str, Any] | None:
    ruta = Path(directorio) / host / "respuestas.json"
    if not ruta.is_file():
        return None
    datos: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


class FixtureWebFetcher:
    """`ports.WebFetcher` sin red: respuestas de ejemplo por dominio (CASO SINTÉTICO del kit)."""

    name = "fixture"
    aviso = AVISO_SINTETICO

    def __init__(self, directorio: str | Path = DIRECTORIO_FIXTURES) -> None:
        self.directorio = Path(directorio).resolve()

    def dominios(self) -> list[str]:
        """Dominios con respuestas de ejemplo."""
        return sorted(
            p.name for p in self.directorio.iterdir() if (p / "respuestas.json").is_file()
        )

    def get(self, url: str, *, dominio: str, accept: str | None = None) -> RespuestaWeb:
        ahora = datetime.now(UTC)
        if not url_permitida(url, dominio):
            return RespuestaWeb(url=url, accept=accept, error="url_no_permitida", obtenido_en=ahora)
        partes = urlsplit(url.strip())
        host = (partes.hostname or "").lower().rstrip(".")
        manifiesto = _manifiesto(str(self.directorio), host)
        if manifiesto is None:
            return RespuestaWeb(url=url, accept=accept, error="sin_fixture", obtenido_en=ahora)
        duracion = int(manifiesto.get("duracion_ms", 0))
        entrada = manifiesto["rutas"].get(partes.path or "/")
        if entrada is None:
            return RespuestaWeb(
                url=url,
                url_final=url,
                accept=accept,
                estado_http=404,
                contenido=_NO_ENCONTRADO,
                cabeceras={"content-type": "text/html; charset=utf-8"},
                duracion_ms=duracion,
                obtenido_en=ahora,
            )
        contenido = (self.directorio / host / entrada["fichero"]).read_text(encoding="utf-8")
        cabeceras = {"content-type": entrada["content_type"]} | dict(entrada.get("cabeceras", {}))
        return RespuestaWeb(
            url=url,
            url_final=url,
            accept=accept,
            estado_http=int(entrada["estado"]),
            contenido=contenido[:MAX_CONTENIDO_CHARS],
            truncado=len(contenido) > MAX_CONTENIDO_CHARS,
            cabeceras=cabeceras,
            duracion_ms=duracion,
            obtenido_en=ahora,
        )

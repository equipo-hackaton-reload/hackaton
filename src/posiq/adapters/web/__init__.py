"""Adaptadores `WebFetcher` de la auditoría técnica GEO (ADR 0019).

- `HttpxWebFetcher`: descarga real con protección SSRF, IP fijada, tope de bytes y de tiempo.
- `FixtureWebFetcher`: CASO SINTÉTICO del kit (`.example`), sin red.

`crear_web_fetcher` aplica la regla del ADR: `off` → sin auditoría; en modo kit, `real` se degrada
a `fixture` (los dominios del kit no existen y nada del kit se presenta como real).
"""

from typing import Literal

from posiq.adapters.web.fixture import FixtureWebFetcher
from posiq.adapters.web.httpx_fetcher import HttpxWebFetcher
from posiq.ports import WebFetcher

ModoAuditoriaWeb = Literal["off", "fixture", "real"]

__all__ = ["FixtureWebFetcher", "HttpxWebFetcher", "ModoAuditoriaWeb", "crear_web_fetcher"]


def crear_web_fetcher(modo: ModoAuditoriaWeb, *, modo_kit: bool) -> WebFetcher | None:
    """El `WebFetcher` para `modo` (`Settings.web_audit`), o None si la auditoría está apagada."""
    if modo == "off":
        return None
    if modo == "fixture" or modo_kit:
        return FixtureWebFetcher()
    return HttpxWebFetcher()

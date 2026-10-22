"""Nodo `web_audit`: auditoría técnica GEO de la web propia de la marca (ADR 0019).

Va entre `judge` y `analyze`: los hallazgos técnicos citan evaluaciones (`evaluation_ids`). Sin LLM.

1. Descarga del dominio propio de la marca del brief (`Brand.dominio`) los `RECURSOS` fijos
   (robots.txt, sitemap, portada normal y con `Accept: text/markdown`, llms.txt y los
   `.well-known`), después las URLs `Sitemap:` de robots.txt que cumplen `url_permitida` y hasta
   `MAX_PAGINAS_SITEMAP` páginas del sitemap. Las descargas son I/O del `WebFetcher` (un hilo cada
   una, para no bloquear el bucle); el fetcher no lanza: un fallo de red llega como respuesta.
2. `domain.web_audit.analizar_web` construye la `AuditoriaWeb` y `hallazgos_web` los hallazgos
   técnicos (fuera de `detect_findings`). Todo lo que viene de la web es DATO: no va a ningún LLM.
3. Cada descarga deja una `Trace` (`modelo="http:<fetcher>"`, `prompt_version="web_audit.v1"`,
   0 tokens y coste 0).

`origen` es `fixture` con `FixtureWebFetcher` y SIEMPRE en modo kit (regla de oro: nada del kit se
presenta como real); `analyze` solo suma a `findings` los hallazgos de una auditoría `real`.
Sin fetcher (`WEB_AUDIT=off`) o sin dominio: `auditoria_web=None`, sin descargas ni trazas.
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from posiq.application.deps import Deps, cost_update, db, persist_traces
from posiq.application.state import StudyState
from posiq.domain.schemas import Trace
from posiq.domain.web_audit import (
    analizar_web,
    hallazgos_web,
    paginas_sitemap,
    urls_sitemap,
    vincular_hallazgos,
)
from posiq.domain.web_audit_schemas import (
    RECURSOS,
    AuditoriaWeb,
    OrigenAuditoria,
    Recurso,
    RespuestaWeb,
)
from posiq.ports import WebFetcher

NODO = "web_audit"
PROMPT_VERSION = "web_audit.v1"


def _base(dominio: str) -> str:
    return f"https://{dominio.strip().rstrip('.').lower()}"


async def _descargar(
    fetcher: WebFetcher, url: str, dominio: str, accept: str | None = None
) -> RespuestaWeb:
    return await asyncio.to_thread(fetcher.get, url, dominio=dominio, accept=accept)


async def descargar(
    fetcher: WebFetcher, dominio: str
) -> tuple[dict[str, RespuestaWeb], list[RespuestaWeb], list[RespuestaWeb]]:
    """Las descargas de la auditoría: (fijas por id de `RECURSOS`, sitemaps, páginas)."""
    base = _base(dominio)

    async def fija(r: Recurso) -> tuple[str, RespuestaWeb]:
        return r.id, await _descargar(fetcher, base + r.ruta, dominio, r.accept)

    fijas = dict(await asyncio.gather(*(fija(r) for r in RECURSOS)))
    # El `/sitemap.xml` fijo ya está en `fijas`: no se repite aunque robots.txt lo declare.
    ya = {fijas["sitemap"].url}
    extra = [u for u in urls_sitemap(fijas.get("robots"), dominio) if u not in ya]
    sitemaps = list(await asyncio.gather(*(_descargar(fetcher, u, dominio) for u in extra)))
    candidatos = [*sitemaps, fijas["sitemap"]]
    paginas = list(
        await asyncio.gather(
            *(_descargar(fetcher, u, dominio) for u in paginas_sitemap(candidatos, dominio))
        )
    )
    return fijas, sitemaps, paginas


def trazas(study_id: str, fetcher: WebFetcher, descargas: Sequence[RespuestaWeb]) -> list[Trace]:
    """Una `Trace` por descarga: HTTP sin LLM, 0 tokens y coste 0 (ADR 0019)."""
    return [
        Trace(
            study_id=study_id,
            nodo=NODO,
            modelo=f"http:{fetcher.name}",
            prompt_version=PROMPT_VERSION,
            tokens_in=0,
            tokens_out=0,
            coste_eur=0.0,
            duracion_ms=max(0, d.duracion_ms or 0),
            fecha=d.obtenido_en,
        )
        for d in descargas
    ]


def origen_de(fetcher: WebFetcher, state: StudyState) -> OrigenAuditoria:
    """`fixture` con el fetcher de ejemplo y siempre en modo kit; `real` solo en modo real."""
    return "fixture" if fetcher.name == "fixture" or state.get("modo") == "kit" else "real"


async def web_audit(state: StudyState, deps: Deps) -> dict[str, Any]:
    vacio: dict[str, Any] = {"auditoria_web": None, "hallazgos_web": None}
    fetcher = deps.web_fetcher
    if fetcher is None:
        return vacio
    sid = state["study_id"]
    study = await db(deps.repo.get_study, sid)
    marca = next((b for b in state["market"].marcas if b.id == study.brand_id), None)
    if marca is None or not (marca.dominio or "").strip():
        return vacio
    dominio = (marca.dominio or "").strip().rstrip(".").lower()

    fijas, sitemaps, paginas = await descargar(fetcher, dominio)
    auditoria: AuditoriaWeb = analizar_web(
        fijas,
        study_id=sid,
        brand_id=marca.id,
        dominio=dominio,
        origen=origen_de(fetcher, state),
        fetcher=fetcher.name,
        obtenido_en=datetime.now(UTC),
        sitemaps=sitemaps,
        paginas=paginas,
    )
    hallazgos = hallazgos_web(
        auditoria,
        state["evaluations"],
        state["runs"],
        prompts=state["prompts"],
        brand_id=marca.id,
    )
    auditoria = vincular_hallazgos(auditoria, hallazgos)

    nuevas = trazas(sid, fetcher, [*(fijas[r.id] for r in RECURSOS), *sitemaps, *paginas])
    await persist_traces(deps, state, nuevas)
    return {"auditoria_web": auditoria, "hallazgos_web": hallazgos, **cost_update(state, nuevas)}

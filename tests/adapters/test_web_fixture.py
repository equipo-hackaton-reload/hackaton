"""`FixtureWebFetcher` (CASO SINTÉTICO del kit) y la acción técnica opcional de `FixtureLLM`."""

import json
import re

from posiq.adapters.llm._fixture_data import HALLAZGOS_WEB_TECNICOS, example_plan
from posiq.adapters.web import FixtureWebFetcher
from posiq.adapters.web.fixture import DIRECTORIO_FIXTURES
from posiq.domain.schemas import BriefSummary, Finding
from posiq.domain.web_audit_schemas import MIN_TEXTO_VISIBLE_CHARS, RECURSOS

DOMINIO = "alboradavision.example"
BASE = f"https://{DOMINIO}"


def _get(ruta: str, accept: str | None = None):  # type: ignore[no-untyped-def]
    return FixtureWebFetcher().get(BASE + ruta, dominio=DOMINIO, accept=accept)


def test_dominios_y_aviso_sintetico() -> None:
    fetcher = FixtureWebFetcher()
    assert fetcher.name == "fixture"
    assert DOMINIO in fetcher.dominios()
    assert "SINTÉTICO" in fetcher.aviso
    manifiesto = json.loads((DIRECTORIO_FIXTURES / DOMINIO / "respuestas.json").read_text("utf-8"))
    assert "SINTETICO" in manifiesto["_aviso"]
    for fichero in (DIRECTORIO_FIXTURES / DOMINIO).iterdir():
        assert "SINTETICO" in fichero.read_text("utf-8"), fichero.name


def test_robots_bloquea_gptbot_y_declara_sitemap() -> None:
    r = _get("/robots.txt")
    assert r.estado_http == 200 and r.tipo_contenido == "text/plain"
    assert re.search(r"User-agent: GPTBot\s*\nDisallow: /\s*\n", r.contenido)
    assert "Sitemap: https://alboradavision.example/sitemap.xml" in r.contenido


def test_portada_poco_texto_sin_js_y_organization_sin_sameas() -> None:
    r = _get("/")
    assert r.estado_http == 200 and r.tipo_contenido == "text/html"
    assert '"@type": "Organization"' in r.contenido and "sameAs" not in r.contenido
    sin_etiquetas = re.sub(r"<script.*?</script>|<!--.*?-->|<[^>]+>", " ", r.contenido, flags=re.S)
    visible = " ".join(sin_etiquetas.split())
    assert len(visible) < MIN_TEXTO_VISIBLE_CHARS
    assert r.link is None  # sin cabecera Link


def test_sin_llms_txt_ni_well_known_ni_markdown() -> None:
    assert _get("/llms.txt").estado_http == 404
    for recurso in RECURSOS:
        if recurso.ruta.startswith("/.well-known/"):
            assert _get(recurso.ruta).estado_http == 404, recurso.ruta
    markdown = _get("/", accept="text/markdown")
    assert markdown.tipo_contenido == "text/html" and markdown.accept == "text/markdown"


def test_sitemap_y_paginas() -> None:
    sitemap = _get("/sitemap.xml")
    assert sitemap.ok and "<urlset" in sitemap.contenido
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap.contenido)
    assert len(locs) == 3
    for loc in locs:
        assert FixtureWebFetcher().get(loc, dominio=DOMINIO).ok, loc


def test_mismas_reglas_de_destino_y_dominio_sin_fixture() -> None:
    fetcher = FixtureWebFetcher()
    fuera = fetcher.get("http://169.254.169.254/", dominio=DOMINIO)
    assert fuera.estado_http is None and fuera.error == "url_no_permitida"
    otro = fetcher.get("https://otra.example/", dominio="otra.example")
    assert otro.estado_http is None and otro.error == "sin_fixture"


# --- Acción técnica opcional del plan de ejemplo -----------------------------------------------


def _finding(id_: str) -> Finding:
    return Finding(
        id=id_,
        study_id="S-x",
        titulo=id_,
        descripcion=id_,
        impacto="M",
        confianza=0.9,
        cifra=1,
        unidad="recuento",
        origen_cifra="test",
        evaluation_ids=["E-1"],
    )


def _brief() -> BriefSummary:
    from posiq.adapters.llm._fixture_data import alborada_brief_summary

    return alborada_brief_summary()


def test_sin_hallazgo_tecnico_no_hay_accion_tecnica() -> None:
    plan = example_plan([_finding("F-brecha-lider"), _finding("F-web-propia")], _brief())
    assert all(a.palanca != "tecnico" for a in plan.acciones)
    assert "A0-3" not in {a.id for a in plan.acciones}


def test_con_hallazgo_tecnico_aparece_a0_3() -> None:
    plan = example_plan([_finding("F-brecha-lider"), _finding("F-web-bots-bloqueados")], _brief())
    accion = next(a for a in plan.acciones if a.id == "A0-3")
    assert accion.palanca == "tecnico"
    assert accion.finding_ids == ["F-web-bots-bloqueados"]
    assert set(HALLAZGOS_WEB_TECNICOS) >= set(accion.finding_ids)
    assert not re.search(r"\d", accion.descripcion)  # sin cifras inventadas

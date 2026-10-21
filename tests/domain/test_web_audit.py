"""Auditoría técnica GEO de la web (ADR 0019): parseo, comprobaciones, puntuación y hallazgos.

Todo con respuestas fijas en texto (sin red). Dos webs de referencia: `_buena()`, que lo cumple
todo (100 de 100), y `_mala()`, que falla en todo lo que puede fallar.
"""

import json
from datetime import UTC, datetime

import pytest

from posiq.domain.schemas import Evaluation, Motor, PromptInstance, Run
from posiq.domain.web_audit import (
    CONFIANZA_LITERAL,
    CONFIANZA_UMBRAL,
    ID_BOTS_BLOQUEADOS,
    acceso_bot,
    analizar_web,
    auditar,
    hallazgos_tecnicos,
    hallazgos_web,
    llms_txt_valido,
    nodos_jsonld,
    paginas_sitemap,
    parsear_content_signal,
    parsear_robots,
    parsear_sitemap,
    rels_link,
    texto_visible,
    urls_sitemap,
    vincular_hallazgos,
)
from posiq.domain.web_audit_schemas import (
    BOTS_IA,
    CATALOGO,
    MAX_EVIDENCIA_CHARS,
    AuditoriaWeb,
    RespuestaWeb,
)
from tests.domain.factories import evaluation, prompt, run

AHORA = datetime(2026, 10, 21, tzinfo=UTC)
DOM = "alboradavision.example"
BASE = f"https://{DOM}"

# --- Fixtures de texto ----------------------------------------------------------------------------

ROBOTS_BUENO = f"""# robots.txt de prueba
User-agent: *
Allow: /
Content-Signal: ai-train=no, search=yes, ai-input=yes

User-agent: GPTBot
User-agent: OAI-SearchBot
User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
User-agent: Claude-SearchBot
User-agent: Claude-Web
Allow: /

User-agent: PerplexityBot
User-agent: Perplexity-User
Allow: /

User-agent: Google-Extended
Allow: /

Sitemap: {BASE}/sitemap.xml
"""

ROBOTS_BLOQUEA = """User-agent: *
Disallow: /admin/

User-agent: GPTBot
Disallow: /

User-agent: CCBot
Disallow: /
"""

PARRAFO = (
    "Clínica Alborada Visión es una clínica oftalmológica de Madrid y Barcelona especializada en "
    "cirugía refractiva, cataratas y control de miopía infantil. "
)

JSONLD_PORTADA = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "MedicalClinic",
            "name": "Clínica Alborada Visión",
            "url": BASE,
            "sameAs": ["https://es.wikipedia.org/wiki/Alborada", f"{BASE}/sobre"],
            "employee": {"@type": "Person", "name": "Dra. Ruiz"},
        },
        {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "¿Duele la cirugía?",
                    "acceptedAnswer": {"@type": "Answer", "text": "No."},
                },
                {
                    "@type": "Question",
                    "name": "¿Cuánto dura?",
                    "acceptedAnswer": {"@type": "Answer", "text": "15 min."},
                },
            ],
        },
        {"@type": "BreadcrumbList", "itemListElement": []},
    ],
}

HTML_BUENO = f"""<!doctype html>
<html lang="es"><head><title>Clínica Alborada Visión</title>
<style>body {{ color: red }}</style>
<script type="application/ld+json">{json.dumps(JSONLD_PORTADA, ensure_ascii=False)}</script>
</head><body><h1>Alborada Visión</h1><p>{PARRAFO * 5}</p>
<script>window.app = "no cuenta";</script></body></html>"""

HTML_ARTICULO = """<html><body><p>Blog</p>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "BlogPosting", "headline": "Miopía",
 "dateModified": "2026-09-01", "author": {"@type": "Person", "name": "Dr. Gil"}}
</script></body></html>"""

HTML_HOWTO = """<html><body>
<script type="application/ld+json">{"@type": ["HowTo"], "name": "Preparar la consulta"}</script>
</body></html>"""

HTML_SPA = """<!doctype html><html><head><title>Alborada</title>
<script src="/app.js"></script></head>
<body><div id="root"></div><noscript>Activa JavaScript para ver esta web.</noscript>
<script>document.getElementById("root").innerHTML = "mucho texto que pinta JavaScript";</script>
</body></html>"""

SITEMAP = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{BASE}/</loc></url>
  <url><loc>{BASE}/blog/miopia</loc></url>
  <url><loc>{BASE}/guia/consulta</loc></url>
</urlset>"""

LLMS = f"""# Clínica Alborada Visión

> Clínica oftalmológica en Madrid y Barcelona.

- [Cirugía refractiva]({BASE}/cirugia-refractiva)
"""

LINK = f'<{BASE}/>; rel="canonical", <{BASE}/index.md>; rel="alternate"; type="text/markdown"'


def resp(
    ruta: str,
    contenido: str = "",
    estado: int | None = 200,
    tipo: str | None = "text/plain",
    *,
    accept: str | None = None,
    duracion_ms: int | None = 120,
    error: str | None = None,
    url: str | None = None,
    **cabeceras: str,
) -> RespuestaWeb:
    cab = {k.replace("_", "-"): v for k, v in cabeceras.items()}
    if tipo is not None and estado is not None:
        cab["content-type"] = tipo
    return RespuestaWeb(
        url=url or f"{BASE}{ruta}",
        url_final=None if estado is None else (url or f"{BASE}{ruta}"),
        accept=accept,
        estado_http=estado,
        contenido=contenido,
        cabeceras=cab,
        duracion_ms=None if estado is None else duracion_ms,
        error=error if estado is not None else (error or "timeout"),
        obtenido_en=AHORA,
    )


def _no(ruta: str, estado: int = 404) -> RespuestaWeb:
    return resp(ruta, "Not found", estado, "text/html")


def _buena() -> dict[str, RespuestaWeb]:
    return {
        "robots": resp("/robots.txt", ROBOTS_BUENO),
        "sitemap": resp("/sitemap.xml", SITEMAP, tipo="application/xml"),
        "portada": resp("/", HTML_BUENO, tipo="text/html; charset=utf-8", duracion_ms=640,
                        link=LINK),
        "portada_markdown": resp("/", f"# Alborada\n\n{PARRAFO}",
                                 tipo="text/markdown; charset=utf-8", accept="text/markdown"),
        "llms_txt": resp("/llms.txt", LLMS),
        "api_catalog": resp("/.well-known/api-catalog", '{"linkset": []}', tipo="application/json"),
        "openid_configuration": _no("/.well-known/openid-configuration"),
        "oauth_authorization_server": resp(
            "/.well-known/oauth-authorization-server", f'{{"issuer": "{BASE}"}}',
            tipo="application/json"),
        "oauth_protected_resource": resp(
            "/.well-known/oauth-protected-resource", f'{{"resource": "{BASE}"}}',
            tipo="application/json"),
        "mcp_server_card": resp("/.well-known/mcp/server-card.json", '{"name": "alborada"}'),
        "agent_skills": resp("/.well-known/agent-skills/index.json", '{"skills": []}'),
        "ai_catalog": resp("/.well-known/ai-catalog.json", "[]"),
    }  # fmt: skip


PAGINAS_BUENAS = [
    resp("/blog/miopia", HTML_ARTICULO, tipo="text/html"),
    resp("/guia/consulta", HTML_HOWTO, tipo="text/html"),
]


def _mala() -> dict[str, RespuestaWeb]:
    return {
        "robots": resp("/robots.txt", ROBOTS_BLOQUEA),
        "sitemap": _no("/sitemap.xml"),
        "portada": resp("/", HTML_SPA, tipo="text/html", duracion_ms=3500),
        "portada_markdown": resp("/", HTML_SPA, tipo="text/html", accept="text/markdown"),
        "llms_txt": _no("/llms.txt"),
        **{
            r: _no(f"/.well-known/{r}")
            for r in (
                "api_catalog",
                "openid_configuration",
                "oauth_authorization_server",
                "oauth_protected_resource",
                "mcp_server_card",
                "agent_skills",
                "ai_catalog",
            )
        },
    }


def _auditar(
    respuestas: dict[str, RespuestaWeb],
    sitemaps: list[RespuestaWeb] | None = None,
    paginas: list[RespuestaWeb] | None = None,
) -> AuditoriaWeb:
    return analizar_web(
        respuestas,
        study_id="S-1",
        brand_id="alborada",
        dominio=DOM,
        origen="fixture",
        fetcher="fixture",
        obtenido_en=AHORA,
        sitemaps=sitemaps or [],
        paginas=paginas or [],
    )


def _estados(a: AuditoriaWeb) -> dict[str, str]:
    return {c.id: c.estado for c in a.comprobaciones}


# --- robots.txt -----------------------------------------------------------------------------------


def test_robots_agrupa_user_agents_seguidos_y_lee_sitemap_y_content_signal() -> None:
    r = parsear_robots(ROBOTS_BUENO)
    assert [g.agentes for g in r.grupos][:2] == [
        ("*",),
        ("gptbot", "oai-searchbot", "chatgpt-user"),
    ]
    assert r.sitemaps == (f"{BASE}/sitemap.xml",)
    assert r.content_signal == "Content-Signal: ai-train=no, search=yes, ai-input=yes"
    assert r.grupo_propio("GPTBot") and r.grupo_propio("google-extended")
    assert not r.grupo_propio("CCBot")


def test_robots_bloqueo_propio_y_comodin() -> None:
    r = parsear_robots(ROBOTS_BLOQUEA)
    gpt = acceso_bot(r, "GPTBot")
    assert (gpt.permitido, gpt.grupo_propio, gpt.regla, gpt.motor) == (
        False,
        True,
        "Disallow: /",
        "ChatGPT",
    )
    claude = acceso_bot(r, "ClaudeBot")
    # El comodín solo prohíbe /admin/: la portada queda libre y no hay regla que decida.
    assert (claude.permitido, claude.grupo_propio, claude.regla) == (True, False, None)
    assert acceso_bot(r, "CCBot").permitido is False


def test_robots_el_grupo_propio_sustituye_al_comodin() -> None:
    r = parsear_robots("User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nDisallow:\n")
    assert acceso_bot(r, "GPTBot").permitido is True  # `Disallow:` vacío no prohíbe nada
    bloqueado = acceso_bot(r, "ClaudeBot")
    assert (bloqueado.permitido, bloqueado.regla) == (False, "Disallow: /")


def test_robots_combina_grupos_repetidos_del_mismo_agente() -> None:
    r = parsear_robots("User-agent: GPTBot\nAllow: /blog\n\nUser-agent: gptbot\nDisallow: /\n")
    assert acceso_bot(r, "GPTBot").permitido is False


@pytest.mark.parametrize(
    ("reglas", "permitido", "regla"),
    [
        ("Disallow: /\nAllow: /", True, "Allow: /"),  # mismo largo: gana Allow
        ("Disallow: /*", False, "Disallow: /*"),
        ("Disallow: /$", False, "Disallow: /$"),
        ("Disallow: /*.php$", True, None),
        ("Disallow: /privado", True, None),
        ("Allow: /$\nDisallow: /", True, "Allow: /$"),  # la más larga
        ("Disallow: *", False, "Disallow: *"),
    ],
)
def test_robots_regla_mas_especifica_comodin_y_ancla(
    reglas: str, permitido: bool, regla: str | None
) -> None:
    acceso = acceso_bot(parsear_robots(f"User-agent: PerplexityBot\n{reglas}\n"), "PerplexityBot")
    assert (acceso.permitido, acceso.regla) == (permitido, regla)


def test_robots_tolera_mayusculas_versiones_comentarios_y_reglas_sueltas() -> None:
    texto = (
        "﻿Disallow: /   # regla antes de cualquier User-agent: se ignora\n"
        "USER-AGENT: ClaudeBot/1.0 (+https://anthropic.com)\n"
        "DISALLOW: /   # todo\n"
        "Crawl-delay: 10\n"
    )
    r = parsear_robots(texto)
    acceso = acceso_bot(r, "ClaudeBot")
    assert (acceso.permitido, acceso.grupo_propio, acceso.regla) == (False, True, "DISALLOW: /")
    assert acceso_bot(r, "GPTBot").permitido is True


def test_sin_robots_legible_el_acceso_es_desconocido() -> None:
    acceso = acceso_bot(None, "Google-Extended")
    assert (acceso.permitido, acceso.motor, acceso.regla) == (None, "Gemini", None)


def test_content_signal_parcial_y_completa() -> None:
    s = parsear_content_signal("Content-Signal: search=yes, ai-train=NO")
    assert (s.search, s.ai_train, s.ai_input, s.completa) == (True, False, None, False)
    assert parsear_content_signal("Content-Signal: ai-train=no, search=yes, ai-input=no").completa


# --- HTML, sitemap, llms.txt y Link ---------------------------------------------------------------


def test_texto_visible_sin_script_style_noscript_ni_template() -> None:
    documento = (
        "<html><head><title>T</title><style>.a{}</style></head><body>"
        "<p>Hola &amp; adiós</p><script>var x = '<p>no</p>';</script>"
        "<noscript>Activa JS</noscript><template><p>plantilla</p></template>"
        "<!-- comentario --><div>  fin  </div></body></html>"
    )
    assert texto_visible(documento) == "T Hola & adiós fin"
    assert texto_visible(HTML_SPA) == "Alborada"


def test_jsonld_recorre_graph_anidados_y_tipos_con_prefijo() -> None:
    nodos = nodos_jsonld(HTML_BUENO, BASE)
    tipos = sorted({t for n in nodos for t in n.tipos})
    assert tipos == ["Answer", "BreadcrumbList", "FAQPage", "MedicalClinic", "Person", "Question"]
    raro = (
        '<script type="application/ld+json">{"@type": "https://schema.org/Organization"}</script>'
        '<script type="application/ld+json">{ roto </script>'
        '<script type="text/javascript">{"@type": "Person"}</script>'
        '<script type="Application/LD+JSON; charset=utf-8">[{"@type": "schema:HowTo"}]</script>'
    )
    assert [n.tipos for n in nodos_jsonld(raro)] == [("Organization",), ("HowTo",)]


def test_parsear_sitemap() -> None:
    assert parsear_sitemap(SITEMAP) == (
        "urlset",
        [f"{BASE}/", f"{BASE}/blog/miopia", f"{BASE}/guia/consulta"],
    )
    indice = "<sm:sitemapindex><sm:sitemap><sm:loc> https://a.example/s1.xml?a=1&amp;b=2 </sm:loc>"
    assert parsear_sitemap(indice + "</sm:sitemap></sm:sitemapindex>") == (
        "sitemapindex",
        ["https://a.example/s1.xml?a=1&b=2"],
    )
    assert parsear_sitemap("<html><body>404</body></html>") == (None, [])


@pytest.mark.parametrize(
    ("texto", "valido", "evidencia"),
    [
        (LLMS, True, f"# Clínica Alborada Visión · {BASE}/cirugia-refractiva"),
        ("# Alborada\n\n- [Inicio](/index.md)\n", True, "# Alborada · /index.md"),
        ("Alborada\nhttps://x.example\n", False, "Alborada"),
        ("# Alborada\n\nSin enlaces.\n", False, "# Alborada (sin URLs)"),
        ("   \n", False, "llms.txt vacío"),
    ],
)
def test_llms_txt(texto: str, valido: bool, evidencia: str) -> None:
    assert llms_txt_valido(texto) == (valido, evidencia)


def test_rels_link() -> None:
    assert rels_link(LINK) == {"canonical", "alternate"}
    assert rels_link("</app.css>; rel=preload; as=style") == {"preload"}


# --- URLs que descarga el nodo --------------------------------------------------------------------


def test_urls_sitemap_solo_del_dominio_y_sin_repetir() -> None:
    robots = resp(
        "/robots.txt",
        "User-agent: *\nAllow: /\n"
        f"Sitemap: {BASE}/sitemap.xml\n"
        f"Sitemap: {BASE}/sitemap.xml\n"
        "Sitemap: http://169.254.169.254/latest/meta-data/\n"
        "Sitemap: https://otro.example/sitemap.xml\n"
        f"Sitemap: https://blog.{DOM}/sitemap.xml\n"
        f"Sitemap: {BASE}:8080/sitemap.xml\n",
    )
    assert urls_sitemap(robots, DOM) == [f"{BASE}/sitemap.xml", f"https://blog.{DOM}/sitemap.xml"]
    assert urls_sitemap(_no("/robots.txt"), DOM) == []
    assert urls_sitemap(None, DOM) == []


def test_paginas_sitemap_sin_portada_ni_otros_hosts_y_como_mucho_tres() -> None:
    xml = "<urlset>" + "".join(
        f"<url><loc>{u}</loc></url>"
        for u in (
            f"{BASE}/",
            "https://otro.example/x",
            f"{BASE}/a",
            f"{BASE}/a",
            f"{BASE}/b",
            "http://10.0.0.1/c",
            f"{BASE}/c",
            f"{BASE}/d",
        )
    ) + "</urlset>"  # fmt: skip
    indice = resp(
        "/s.xml", f"<sitemapindex><sitemap><loc>{BASE}/z.xml</loc></sitemap></sitemapindex>"
    )
    assert paginas_sitemap([indice, _no("/x.xml"), resp("/sitemap.xml", xml)], DOM) == [
        f"{BASE}/a",
        f"{BASE}/b",
        f"{BASE}/c",
    ]


# --- Auditoría completa ---------------------------------------------------------------------------


def test_web_buena_puntua_100_en_todo() -> None:
    a = _auditar(_buena(), paginas=PAGINAS_BUENAS)
    no_ok = {k: v for k, v in _estados(a).items() if v != "ok"}
    assert no_ok == {}
    assert a.puntuacion == 100.0
    assert {b.bloque: b.puntuacion for b in a.bloques} == dict.fromkeys(
        ("descubrimiento", "contenido", "acceso_bots", "rendimiento", "agentes_api"), 100.0
    )
    assert a.motores_afectados == []
    assert all(x.permitido for x in a.accesos_bots)
    assert a.senal_contenido is not None and a.senal_contenido.completa
    assert a.tipos_schema == [
        "Answer", "BlogPosting", "BreadcrumbList", "FAQPage", "HowTo", "MedicalClinic", "Person",
        "Question",
    ]  # fmt: skip
    assert a.texto_visible_chars is not None and a.texto_visible_chars >= 500
    assert a.tiempo_respuesta_ms == 640
    assert len(a.recursos) == 12 + 2
    assert (a.origen, a.fetcher, a.version, a.dominio) == (
        "fixture",
        "fixture",
        "web_audit.v1",
        DOM,
    )
    assert auditar is analizar_web


def test_web_buena_evidencias_literales() -> None:
    a = _auditar(_buena(), paginas=PAGINAS_BUENAS)
    ev = {c.id: c.evidencia for c in a.comprobaciones}
    assert ev["robots_txt"] == "User-agent: *"
    assert ev["sitemap"] == f"<urlset> · <loc>{BASE}/</loc>"
    assert ev["sitemap_en_robots"] == f"Sitemap: {BASE}/sitemap.xml"
    assert ev["cabeceras_link"] == f"Link: {LINK}"
    assert ev["markdown_negociado"] == "Content-Type: text/markdown; charset=utf-8"
    assert ev["jsonld_organization"] == '"@type": "MedicalClinic"'
    assert ev["organization_sameas"] == '"sameAs": ["https://es.wikipedia.org/wiki/Alborada"]'
    assert ev["jsonld_faqpage"] == '"@type": "FAQPage" · 2 "Question"'
    assert ev["jsonld_article"] == '"@type": "BlogPosting" · "dateModified": "2026-09-01"'
    assert ev["content_signal"] == "Content-Signal: ai-train=no, search=yes, ai-input=yes"
    assert ev["tiempo_respuesta"] == "HTTP 200 en 640 ms"
    assert a.comprobacion("jsonld_article").recurso == f"{BASE}/blog/miopia"
    assert a.comprobacion("jsonld_howto").recurso == f"{BASE}/guia/consulta"
    assert a.comprobacion("oauth_discovery").recurso == (
        f"{BASE}/.well-known/oauth-authorization-server"
    )


def test_web_mala_falla_y_puntua_7_5() -> None:
    a = _auditar(_mala())
    estados = _estados(a)
    assert estados["robots_txt"] == "ok"
    assert estados["organization_sameas"] == "no_aplica"
    assert {k for k, v in estados.items() if v not in ("falla",)} == {
        "robots_txt",
        "organization_sameas",
    }
    puntos = {b.bloque: b.puntuacion for b in a.bloques}
    assert puntos == {
        "descubrimiento": 30.0,
        "contenido": 0.0,
        "acceso_bots": 0.0,
        "rendimiento": 0.0,
        "agentes_api": 0.0,
    }
    assert a.puntuacion == 7.5  # 25 × 30 / 100
    assert a.comprobacion("bots_ia_sin_bloqueo").motores_afectados == ["ChatGPT"]
    assert a.comprobacion("bots_ia_sin_bloqueo").evidencia == (
        "GPTBot → Disallow: /; CCBot → Disallow: /"
    )
    assert a.comprobacion("bots_ia_reglas_explicitas").motores_afectados == [
        "ChatGPT",
        "Gemini",
        "Perplexity",
        "Claude",
    ]
    assert a.comprobacion("organization_sameas").motores_afectados == []
    assert a.comprobacion("texto_sin_js").evidencia == "8 caracteres: «Alborada»"
    assert a.comprobacion("sitemap").evidencia == "HTTP 404"
    assert a.comprobacion("markdown_negociado").evidencia == "Content-Type: text/html"
    assert a.comprobacion("cabeceras_link").evidencia == "Sin cabecera Link"
    assert a.comprobacion("jsonld_organization").evidencia == "Sin JSON-LD"
    # Agentes/API es informativo: falla, pero no afecta a ningún motor.
    assert all(c.motores_afectados == [] for c in a.comprobaciones if c.bloque == "agentes_api")
    assert a.texto_visible_chars == 8 and a.tiempo_respuesta_ms == 3500
    assert a.senal_contenido is None


def test_todas_las_comprobaciones_del_catalogo_en_orden() -> None:
    a = _auditar(_mala())
    assert [c.id for c in a.comprobaciones] == list(CATALOGO)
    assert sorted(x.bot for x in a.accesos_bots) == sorted(BOTS_IA)


def test_recurso_desconocido_es_un_error_de_programacion() -> None:
    with pytest.raises(ValueError, match="Recursos desconocidos"):
        _auditar({"robot": resp("/robots.txt", ROBOTS_BUENO)})


# --- Estados: falla, error y no_aplica ------------------------------------------------------------


def test_sin_robots_las_de_bots_no_aplican() -> None:
    respuestas = _buena() | {"robots": _no("/robots.txt")}
    a = _auditar(respuestas, paginas=PAGINAS_BUENAS)
    estados = _estados(a)
    assert (estados["robots_txt"], a.comprobacion("robots_txt").evidencia) == ("falla", "HTTP 404")
    for id_ in ("sitemap_en_robots", "bots_ia_sin_bloqueo", "bots_ia_reglas_explicitas",
                "content_signal"):  # fmt: skip
        assert estados[id_] == "no_aplica", id_
    assert all(x.permitido is None for x in a.accesos_bots)
    # Acceso de bots sin nada evaluado: el bloque no puntúa y el total se renormaliza.
    assert a.puntuacion_bloque("acceso_bots").puntuacion is None
    # robots_txt falla (30) y sitemap_en_robots no aplica: 55 / 85.
    assert a.puntuacion_bloque("descubrimiento").puntuacion == 64.71
    assert a.puntuacion == round((25 * 64.71 + 35 * 100 + 10 * 100 + 5 * 100) / 75, 2)


def test_robots_que_devuelve_html_falla_y_no_se_interpreta() -> None:
    respuestas = _buena() | {
        "robots": resp("/robots.txt", "<!DOCTYPE html><html>Inicio</html>", tipo=None)
    }
    a = _auditar(respuestas)
    assert a.comprobacion("robots_txt").estado == "falla"
    assert _estados(a)["bots_ia_sin_bloqueo"] == "no_aplica"


@pytest.mark.parametrize("linea", ["Sitemap: /sitemap.xml", "Sitemap: http://[::1/sitemap.xml"])
def test_sitemap_en_robots_exige_url_absoluta_valida(linea: str) -> None:
    robots = ROBOTS_BUENO.replace(f"Sitemap: {BASE}/sitemap.xml", linea)
    c = _auditar(_buena() | {"robots": resp("/robots.txt", robots)}).comprobacion(
        "sitemap_en_robots"
    )
    assert (c.estado, c.evidencia) == ("falla", linea)


def test_robots_sin_grupos_falla_pero_no_bloquea() -> None:
    respuestas = _buena() | {"robots": resp("/robots.txt", f"Sitemap: {BASE}/sitemap.xml\n")}
    a = _auditar(respuestas)
    estados = _estados(a)
    assert (estados["robots_txt"], estados["sitemap_en_robots"]) == ("falla", "ok")
    assert estados["bots_ia_sin_bloqueo"] == "ok"
    assert a.comprobacion("bots_ia_sin_bloqueo").evidencia == (
        "Ninguna regla Disallow afecta a / para los bots de IA"
    )
    assert estados["bots_ia_reglas_explicitas"] == "falla"


@pytest.mark.parametrize("respuesta", [_no("/robots.txt", 503), resp("/robots.txt", estado=None)])
def test_robots_inaccesible_da_error_no_no_aplica(respuesta: RespuestaWeb) -> None:
    a = _auditar(_buena() | {"robots": respuesta})
    estados = _estados(a)
    for id_ in ("robots_txt", "sitemap_en_robots", "bots_ia_sin_bloqueo",
                "bots_ia_reglas_explicitas", "content_signal"):  # fmt: skip
        assert estados[id_] == "error", id_


def test_content_signal_en_cabecera_sin_robots() -> None:
    respuestas = _buena() | {
        "robots": _no("/robots.txt"),
        "portada": resp(
            "/",
            HTML_BUENO,
            tipo="text/html",
            content_signal="ai-train=no, search=yes, ai-input=yes",
        ),
    }
    a = _auditar(respuestas)
    c = a.comprobacion("content_signal")
    assert (c.estado, c.evidencia, c.recurso) == (
        "ok",
        "Content-Signal: ai-train=no, search=yes, ai-input=yes",
        f"{BASE}/",
    )


def test_content_signal_incompleta_falla() -> None:
    robots = ROBOTS_BUENO.replace(", ai-input=yes", "")
    a = _auditar(_buena() | {"robots": resp("/robots.txt", robots)})
    c = a.comprobacion("content_signal")
    assert (c.estado, c.detalle) == ("falla", "Content-Signal no declara ai-input.")


def test_portada_sin_respuesta_da_error_en_lo_que_depende_de_ella() -> None:
    respuestas = _buena() | {"portada": resp("/", estado=None, error="timeout")}
    a = _auditar(respuestas)
    estados = _estados(a)
    for id_ in ("cabeceras_link", "texto_sin_js", "jsonld_organization", "organization_sameas",
                "jsonld_faqpage", "jsonld_person", "tiempo_respuesta"):  # fmt: skip
        assert estados[id_] == "error", id_
    assert a.puntuacion_bloque("rendimiento").puntuacion is None
    assert a.texto_visible_chars is None and a.tiempo_respuesta_ms is None
    assert "timeout" in a.comprobacion("texto_sin_js").detalle


def test_portada_ausente_cuenta_como_no_descargada() -> None:
    respuestas = _buena()
    del respuestas["portada"]
    a = _auditar(respuestas)
    c = a.comprobacion("texto_sin_js")
    assert (c.estado, c.recurso) == ("error", f"{BASE}/")


def test_portada_404_falla_y_sameas_no_aplica_pero_paginas_cuentan() -> None:
    respuestas = _buena() | {"portada": _no("/")}
    a = _auditar(respuestas, paginas=PAGINAS_BUENAS)
    estados = _estados(a)
    assert (estados["texto_sin_js"], estados["jsonld_organization"]) == ("falla", "falla")
    assert estados["organization_sameas"] == "no_aplica"
    assert (estados["jsonld_article"], estados["jsonld_howto"]) == ("ok", "ok")
    assert estados["jsonld_faqpage"] == "falla"
    assert a.comprobacion("jsonld_faqpage").recurso == f"{BASE}/blog/miopia"


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [(403, "falla"), (404, "falla"), (410, "falla"), (500, "error"), (429, "error")],
)
def test_codigos_http(estado: int, esperado: str) -> None:
    a = _auditar(_buena() | {"llms_txt": _no("/llms.txt", estado)})
    c = a.comprobacion("llms_txt")
    assert (c.estado, c.evidencia) == (esperado, f"HTTP {estado}")
    assert c.motores_afectados == (list(CATALOGO["llms_txt"].motores) if estado < 500 and
                                   estado != 429 else [])  # fmt: skip


def test_markdown_406_falla() -> None:
    a = _auditar(_buena() | {"portada_markdown": _no("/", 406)})
    assert a.comprobacion("markdown_negociado").estado == "falla"


def test_llms_txt_html_falla() -> None:
    a = _auditar(_buena() | {"llms_txt": resp("/llms.txt", "<html>404</html>", tipo="text/html")})
    assert a.comprobacion("llms_txt").evidencia == "Content-Type: text/html"


def test_sitemap_de_robots_vale_aunque_el_fijo_no_exista() -> None:
    sm = resp("/sitemaps/main.xml", SITEMAP, tipo="application/xml")
    a = _auditar(_buena() | {"sitemap": _no("/sitemap.xml")}, sitemaps=[sm])
    c = a.comprobacion("sitemap")
    assert (c.estado, c.recurso) == ("ok", f"{BASE}/sitemaps/main.xml")


def test_sitemap_invalido_y_sitemapindex() -> None:
    malo = _auditar(_buena() | {"sitemap": resp("/sitemap.xml", "<urlset></urlset>")})
    assert (malo.comprobacion("sitemap").estado, malo.comprobacion("sitemap").evidencia) == (
        "falla",
        "<urlset> sin <loc>",
    )
    indice = f"<sitemapindex><sitemap><loc>{BASE}/s1.xml</loc></sitemap></sitemapindex>"
    bueno = _auditar(_buena() | {"sitemap": resp("/sitemap.xml", indice)})
    assert bueno.comprobacion("sitemap").estado == "ok"


def test_sitemap_con_error_y_404_prefiere_la_falla() -> None:
    a = _auditar(_buena() | {"sitemap": _no("/sitemap.xml")}, sitemaps=[_no("/s.xml", 503)])
    assert a.comprobacion("sitemap").estado == "falla"
    b = _auditar(_buena() | {"sitemap": _no("/sitemap.xml", 502)})
    assert b.comprobacion("sitemap").estado == "error"


def test_link_sin_canonical_falla() -> None:
    portada = resp("/", HTML_BUENO, tipo="text/html", link="</app.css>; rel=preload")
    c = _auditar(_buena() | {"portada": portada}).comprobacion("cabeceras_link")
    assert (c.estado, c.evidencia) == ("falla", "Link: </app.css>; rel=preload")


def test_sameas_solo_interno_falla_y_externo_en_texto_vale() -> None:
    def portada(same_as: object) -> RespuestaWeb:
        datos = {"@type": "Organization", "sameAs": same_as}
        documento = f'<script type="application/ld+json">{json.dumps(datos)}</script>{PARRAFO * 5}'
        return resp("/", documento, tipo="text/html")

    interno = _auditar(_buena() | {"portada": portada([f"https://www.{DOM}/x"])})
    assert interno.comprobacion("organization_sameas").estado == "falla"
    externo = _auditar(_buena() | {"portada": portada("https://www.linkedin.com/company/x")})
    assert externo.comprobacion("organization_sameas").estado == "ok"
    sin = _auditar(
        _buena()
        | {
            "portada": resp(
                "/", '<script type="application/ld+json">{"@type": "LocalBusiness"}</script>'
            )
        }
    )
    assert (
        sin.comprobacion("organization_sameas").evidencia == '"@type": "LocalBusiness" sin sameAs'
    )


def test_faqpage_sin_preguntas_y_article_sin_fecha_fallan() -> None:
    datos = [{"@type": "FAQPage"}, {"@type": "Article", "headline": "x"}]
    documento = f'<script type="application/ld+json">{json.dumps(datos)}</script>'
    a = _auditar(_buena() | {"portada": resp("/", documento, tipo="text/html")})
    faq, art = a.comprobacion("jsonld_faqpage"), a.comprobacion("jsonld_article")
    assert faq.detalle == "Ninguna de las 1 página auditada declara un FAQPage con preguntas."
    assert art.detalle.endswith("declara Article con `dateModified`.")
    assert art.evidencia == "Tipos JSON-LD en 1 página: Article, FAQPage"


@pytest.mark.parametrize(("ms", "estado"), [(2000, "ok"), (2001, "falla")])
def test_umbral_de_tiempo(ms: int, estado: str) -> None:
    portada = resp("/", HTML_BUENO, tipo="text/html", duracion_ms=ms)
    assert _auditar(_buena() | {"portada": portada}).comprobacion("tiempo_respuesta").estado == (
        estado
    )


def test_texto_en_el_umbral() -> None:
    justo = resp("/", "<p>" + "a" * 500 + "</p>", tipo="text/html")
    corto = resp("/", "<p>" + "a" * 499 + "</p>", tipo="text/html")
    assert _auditar(_buena() | {"portada": justo}).comprobacion("texto_sin_js").estado == "ok"
    assert _auditar(_buena() | {"portada": corto}).comprobacion("texto_sin_js").estado == "falla"


def test_agentes_api_json_y_claves() -> None:
    respuestas = _buena() | {
        "api_catalog": resp("/.well-known/api-catalog", '{"apis": []}'),
        "oauth_authorization_server": _no("/.well-known/oauth-authorization-server"),
        "mcp_server_card": resp("/.well-known/mcp/server-card.json", "<html>no</html>"),
    }
    a = _auditar(respuestas, paginas=PAGINAS_BUENAS)
    estados = _estados(a)
    assert (estados["api_catalog"], estados["oauth_discovery"], estados["mcp_server_card"]) == (
        "falla",
        "falla",
        "falla",
    )
    assert a.comprobacion("api_catalog").detalle == "El JSON no incluye `linkset`."
    assert a.puntuacion_bloque("agentes_api").puntuacion == 45.0
    assert a.motores_afectados == []


def test_evidencia_recortada_a_500() -> None:
    largo = "# " + "x" * 2000 + "\nhttps://a.example\n"
    c = _auditar(_buena() | {"llms_txt": resp("/llms.txt", largo)}).comprobacion("llms_txt")
    assert len(c.evidencia) == MAX_EVIDENCIA_CHARS and c.evidencia.endswith("…")


# --- Hallazgos ------------------------------------------------------------------------------------


def _muestra() -> tuple[list[Evaluation], list[Run], list[PromptInstance]]:
    prompts = [prompt("P-esp", "generico"), prompt("P-asis", "marca")]
    motores: list[Motor] = ["ChatGPT", "Gemini", "Perplexity", "Claude"]
    runs: list[Run] = []
    evals: list[Evaluation] = []
    for m in motores:
        for p in ("P-esp", "P-asis"):
            for k, aparece in ((1, False), (2, True)):
                rid = f"R-{m}-{p}-{k}"
                runs.append(run(rid, motor=m, prompt_id=p, marcas=["alborada", "valdecruz"]))
                evals.append(evaluation("alborada", rid, aparece=aparece))
                evals.append(evaluation("valdecruz", rid, aparece=False))
    return evals, runs, prompts


def test_muestra_de_prueba_usa_instanciaciones_validas() -> None:
    evals, runs, prompts = _muestra()
    assert [p.tipo for p in prompts] == ["espontaneo", "asistido"]
    assert len(runs) == 16 and len(evals) == 32


def test_hallazgos_de_la_web_mala() -> None:
    evals, runs, prompts = _muestra()
    a = _auditar(_mala())
    hallazgos = hallazgos_web(a, evals, runs, prompts=prompts)
    por_id = {f.id: f for f in hallazgos}
    assert list(por_id) == [
        ID_BOTS_BLOQUEADOS,
        "F-web-descubrimiento",
        "F-web-contenido",
        "F-web-rendimiento",
    ]
    bots = por_id[ID_BOTS_BLOQUEADOS]
    assert (bots.impacto, bots.cifra, bots.unidad, bots.confianza) == ("L", 1, "recuento", 0.9)
    assert bots.evaluation_ids == ["R-ChatGPT-P-esp-1:alborada"]
    assert bots.origen_cifra == "web_audit.v1:bots_ia_sin_bloqueo"
    assert "«Disallow: /»" in bots.descripcion and "GPTBot (ChatGPT)" in bots.descripcion
    assert "CCBot" not in bots.descripcion  # CCBot no alimenta a un motor medido
    assert bots.titulo == "robots.txt impide a ChatGPT leer la web"

    desc = por_id["F-web-descubrimiento"]
    assert (desc.impacto, desc.cifra, desc.unidad, desc.confianza) == (
        "M",
        30.0,
        "puntos",
        CONFIANZA_LITERAL,
    )
    assert desc.origen_cifra == "web_audit.v1:descubrimiento"
    assert desc.evaluation_ids == sorted(
        f"R-{m}-P-esp-1:alborada" for m in ("ChatGPT", "Gemini", "Perplexity", "Claude")
    )
    assert "`sitemap`" in desc.descripcion and "puntúa 30 de 100" in desc.descripcion

    contenido = por_id["F-web-contenido"]
    assert (contenido.impacto, contenido.cifra, contenido.confianza) == ("L", 0.0, CONFIANZA_UMBRAL)
    assert "`texto_sin_js`" in contenido.descripcion
    assert por_id["F-web-rendimiento"].confianza == CONFIANZA_UMBRAL
    assert hallazgos_tecnicos is hallazgos_web


def test_web_buena_no_da_hallazgos() -> None:
    evals, runs, prompts = _muestra()
    a = _auditar(_buena(), paginas=PAGINAS_BUENAS)
    assert hallazgos_web(a, evals, runs, prompts=prompts) == []


def test_sin_evidencia_no_hay_hallazgo() -> None:
    evals, runs, prompts = _muestra()
    a = _auditar(_mala())
    # Solo las asistidas, o solo donde aparece, o de otro estudio: nada que citar.
    asistidas = [e for e in evals if "P-asis" in e.run_id]
    assert hallazgos_web(a, asistidas, runs, prompts=prompts) == []
    aparece = [e for e in evals if e.aparece]
    assert hallazgos_web(a, aparece, runs, prompts=prompts) == []
    otro = [e.model_copy(update={"study_id": "S-2"}) for e in evals]
    assert hallazgos_web(a, otro, runs, prompts=prompts) == []
    assert hallazgos_web(a, [], [], prompts=[]) == []


def test_solo_cuentan_los_motores_afectados_y_la_marca_pedida() -> None:
    evals, runs, prompts = _muestra()
    a = _auditar(_mala())
    sin_chatgpt = [e for e in evals if "ChatGPT" not in e.run_id]
    ids = [f.id for f in hallazgos_web(a, sin_chatgpt, runs, prompts=prompts)]
    assert ID_BOTS_BLOQUEADOS not in ids and "F-web-contenido" in ids
    otra = hallazgos_web(a, evals, runs, prompts=prompts, brand_id="valdecruz")
    bots = next(f for f in otra if f.id == ID_BOTS_BLOQUEADOS)
    assert bots.evaluation_ids == ["R-ChatGPT-P-esp-1:valdecruz", "R-ChatGPT-P-esp-2:valdecruz"]


def test_marca_fuera_de_marcas_a_evaluar_no_cuenta() -> None:
    evals, runs, prompts = _muestra()
    runs_sin = [r.model_copy(update={"marcas_a_evaluar": ["valdecruz"]}) for r in runs]
    assert hallazgos_web(_auditar(_mala()), evals, runs_sin, prompts=prompts) == []


def test_bloqueo_solo_de_bots_sin_motor_no_da_hallazgo_de_bots() -> None:
    evals, runs, prompts = _muestra()
    robots = ROBOTS_BUENO.replace("Sitemap:", "User-agent: CCBot\nDisallow: /\n\nSitemap:")
    a = _auditar(_buena() | {"robots": resp("/robots.txt", robots)}, paginas=PAGINAS_BUENAS)
    c = a.comprobacion("bots_ia_sin_bloqueo")
    assert (c.estado, c.motores_afectados) == ("falla", [])
    assert hallazgos_web(a, evals, runs, prompts=prompts) == []


def test_bots_bloqueados_varios_motores() -> None:
    evals, runs, prompts = _muestra()
    robots = "User-agent: *\nDisallow: /\n\nUser-agent: Google-Extended\nAllow: /\n"
    a = _auditar(_buena() | {"robots": resp("/robots.txt", robots)}, paginas=PAGINAS_BUENAS)
    f = next(
        h for h in hallazgos_web(a, evals, runs, prompts=prompts) if h.id == ID_BOTS_BLOQUEADOS
    )
    assert f.cifra == 3
    assert f.titulo == "robots.txt impide a ChatGPT, Perplexity y Claude leer la web"
    assert len(f.evaluation_ids) == 3


def test_vincular_hallazgos() -> None:
    evals, runs, prompts = _muestra()
    a = _auditar(_mala())
    hallazgos = hallazgos_web(a, evals, runs, prompts=prompts)
    vinculada = vincular_hallazgos(a, hallazgos)
    assert vinculada.finding_ids == [f.id for f in hallazgos]
    assert vinculada.puntuacion == a.puntuacion
    AuditoriaWeb.model_validate(vinculada.model_dump())

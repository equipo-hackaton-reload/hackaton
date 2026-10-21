"""Contrato de la auditoría técnica GEO de la web (ADR 0019): modelos, puntuación y `WebFetcher`."""

import inspect
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from posiq.domain.schemas import Motor
from posiq.domain.web_audit_schemas import (
    BLOQUES,
    BOT_MOTOR,
    BOTS_IA,
    CATALOGO,
    MAX_BYTES_DESCARGA,
    MAX_CONTENIDO_CHARS,
    MAX_REDIRECCIONES,
    PESO_BLOQUE,
    RECURSOS,
    TIMEOUT_TOTAL_RECURSO_S,
    AccesoBot,
    AuditoriaWeb,
    Comprobacion,
    EstadoComprobacion,
    IdComprobacion,
    PuntuacionBloque,
    RecursoConsultado,
    RespuestaWeb,
    SenalContenido,
    ip_permitida,
    puntuar_bloque,
    puntuar_total,
    url_permitida,
)
from posiq.ports import WebFetcher

AHORA = datetime(2026, 10, 21, tzinfo=UTC)


def _comp(id_: IdComprobacion, estado: EstadoComprobacion = "ok", **kw: object) -> Comprobacion:
    d = CATALOGO[id_]
    datos: dict[str, object] = {
        "id": id_,
        "bloque": d.bloque,
        "peso": d.peso,
        "estado": estado,
        "titulo": d.titulo,
        "detalle": "detalle",
        "evidencia": "HTTP 200" if estado in ("ok", "falla") else "",
        "recurso": "https://alboradavision.example/",
    }
    if estado == "falla":
        datos["motores_afectados"] = list(d.motores)
    datos.update(kw)
    return Comprobacion.model_validate(datos)


def _accesos() -> list[AccesoBot]:
    return [
        AccesoBot(bot=b, motor=BOT_MOTOR[b], permitido=True, regla="User-agent: *") for b in BOTS_IA
    ]


def _auditoria(
    estados: dict[IdComprobacion, EstadoComprobacion] | None = None, **kw: object
) -> AuditoriaWeb:
    estados = estados or {}
    comps = [_comp(i, estados.get(i, "ok")) for i in CATALOGO]
    bloques = [puntuar_bloque(b, comps) for b in BLOQUES]
    datos: dict[str, object] = {
        "study_id": "s1",
        "brand_id": "alborada",
        "dominio": "alboradavision.example",
        "origen": "fixture",
        "fetcher": "fixture",
        "comprobaciones": comps,
        "bloques": bloques,
        "puntuacion": puntuar_total(bloques),
        "accesos_bots": _accesos(),
        "obtenido_en": AHORA,
    }
    datos.update(kw)
    return AuditoriaWeb.model_validate(datos)


# --- catálogo ------------------------------------------------------------------------------------


def test_pesos_suman_100_por_bloque_y_en_total() -> None:
    assert sum(PESO_BLOQUE.values()) == 100
    for bloque in BLOQUES:
        assert sum(d.peso for d in CATALOGO.values() if d.bloque == bloque) == 100


def test_catalogo_cubre_la_guia() -> None:
    por_bloque = {b: {d.id for d in CATALOGO.values() if d.bloque == b} for b in BLOQUES}
    assert {
        "robots_txt",
        "sitemap",
        "sitemap_en_robots",
        "cabeceras_link",
        "markdown_negociado",
    } <= por_bloque["descubrimiento"]
    assert {
        "texto_sin_js",
        "jsonld_organization",
        "organization_sameas",
        "jsonld_faqpage",
        "jsonld_howto",
        "jsonld_article",
        "jsonld_person",
        "jsonld_breadcrumb",
        "llms_txt",
    } <= por_bloque["contenido"]
    assert {"bots_ia_sin_bloqueo", "bots_ia_reglas_explicitas", "content_signal"} <= por_bloque[
        "acceso_bots"
    ]
    assert len(por_bloque["agentes_api"]) == 6
    assert por_bloque["rendimiento"] == {"tiempo_respuesta"}
    assert PESO_BLOQUE["agentes_api"] < min(
        p for b, p in PESO_BLOQUE.items() if b != "agentes_api"
    )  # informativo


def test_bots_de_la_guia_con_su_motor() -> None:
    assert set(BOTS_IA) == {
        "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-Web",
        "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "CCBot",
    }  # fmt: skip
    assert BOT_MOTOR["Google-Extended"] == "Gemini"
    assert BOT_MOTOR["Perplexity-User"] == "Perplexity"
    assert BOT_MOTOR["CCBot"] is None


def test_recursos_incluyen_markdown_y_well_known() -> None:
    rutas = {(r.ruta, r.accept) for r in RECURSOS}
    assert ("/", "text/markdown") in rutas
    assert ("/robots.txt", None) in rutas and ("/llms.txt", None) in rutas
    assert sum(r.ruta.startswith("/.well-known/") for r in RECURSOS) == 7
    assert len({r.id for r in RECURSOS}) == len(RECURSOS)


# --- RespuestaWeb --------------------------------------------------------------------------------


def test_respuesta_web_propiedades() -> None:
    r = RespuestaWeb(
        url="https://x.example/",
        estado_http=200,
        cabeceras={"content-type": "Text/HTML; charset=utf-8", "link": '</>; rel="canonical"'},
        duracion_ms=120,
        obtenido_en=AHORA,
    )
    assert r.ok and r.tipo_contenido == "text/html" and r.link == '</>; rel="canonical"'


def test_respuesta_4xx_no_es_error() -> None:
    r = RespuestaWeb(url="https://x.example/llms.txt", estado_http=404, obtenido_en=AHORA)
    assert not r.ok and r.error is None


def test_respuesta_sin_estado_exige_error() -> None:
    with pytest.raises(ValidationError):
        RespuestaWeb(url="https://x.example/", obtenido_en=AHORA)
    r = RespuestaWeb(url="https://x.example/", error="timeout", obtenido_en=AHORA)
    assert not r.ok


@pytest.mark.parametrize("cabeceras", [{"Content-Type": "text/html"}, {"set-cookie": "a=1"}])
def test_respuesta_solo_cabeceras_relevantes_en_minusculas(cabeceras: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        RespuestaWeb(
            url="https://x.example/", estado_http=200, cabeceras=cabeceras, obtenido_en=AHORA
        )


def test_respuesta_estado_http_valido() -> None:
    with pytest.raises(ValidationError):
        RespuestaWeb(url="https://x.example/", estado_http=42, obtenido_en=AHORA)


def test_recurso_consultado_desde_respuesta() -> None:
    r = RespuestaWeb(
        url="u", accept="text/markdown", estado_http=406, duracion_ms=5, obtenido_en=AHORA
    )
    assert RecursoConsultado.de(r) == RecursoConsultado(
        url="u", accept="text/markdown", estado_http=406, duracion_ms=5
    )


# --- AccesoBot y SenalContenido ------------------------------------------------------------------


def test_acceso_bot_motor_debe_coincidir() -> None:
    AccesoBot(
        bot="GPTBot", motor="ChatGPT", permitido=False, grupo_propio=True, regla="Disallow: /"
    )
    with pytest.raises(ValidationError):
        AccesoBot(bot="GPTBot", motor="Gemini", permitido=True)
    with pytest.raises(ValidationError):
        AccesoBot(bot="CCBot", motor="ChatGPT", permitido=True)


def test_senal_contenido_completa() -> None:
    linea = "Content-Signal: ai-train=no, search=yes, ai-input=yes"
    assert SenalContenido(linea=linea, ai_train=False, search=True, ai_input=True).completa
    assert not SenalContenido(linea="Content-Signal: search=yes", search=True).completa


# --- Comprobacion --------------------------------------------------------------------------------


def test_comprobacion_bloque_y_peso_del_catalogo() -> None:
    with pytest.raises(ValidationError):
        _comp("robots_txt", bloque="contenido")
    with pytest.raises(ValidationError):
        _comp("robots_txt", peso=99)


@pytest.mark.parametrize("estado", ["ok", "falla"])
def test_comprobacion_ok_o_falla_exige_evidencia(estado: EstadoComprobacion) -> None:
    with pytest.raises(ValidationError):
        _comp("llms_txt", estado, evidencia="")


@pytest.mark.parametrize("estado", ["no_aplica", "error"])
def test_comprobacion_sin_evaluar_no_exige_evidencia(estado: EstadoComprobacion) -> None:
    assert _comp("llms_txt", estado).evidencia == ""


def test_solo_falla_afecta_a_motores() -> None:
    motores: list[Motor] = ["ChatGPT"]
    with pytest.raises(ValidationError):
        _comp("llms_txt", "ok", motores_afectados=motores)
    with pytest.raises(ValidationError):
        _comp("llms_txt", "falla", motores_afectados=["ChatGPT", "ChatGPT"])


def test_estado_desconocido_falla() -> None:
    with pytest.raises(ValidationError):
        _comp("llms_txt", "aviso")  # type: ignore[arg-type]


def test_evidencia_acotada() -> None:
    with pytest.raises(ValidationError):
        _comp("llms_txt", evidencia="x" * 501)


# --- puntuación ----------------------------------------------------------------------------------


def test_puntuacion_bloque_ignora_no_aplica_y_error() -> None:
    comps = [
        _comp("robots_txt", "ok"),  # 30
        _comp("sitemap", "falla"),  # 25
        _comp("sitemap_en_robots", "no_aplica"),  # 15
        _comp("cabeceras_link", "error"),  # 15
        _comp("markdown_negociado", "ok"),  # 15
    ]
    p = puntuar_bloque("descubrimiento", comps)
    assert p.puntuacion == round(100 * 45 / 70, 2)
    assert (p.ok, p.falla, p.no_aplica, p.error, p.peso) == (2, 1, 1, 1, 25)


def test_puntuacion_bloque_sin_evaluadas_es_none() -> None:
    p = puntuar_bloque("rendimiento", [_comp("tiempo_respuesta", "error")])
    assert p.puntuacion is None and p.error == 1


def test_puntuacion_total_renormaliza() -> None:
    bloques = [
        PuntuacionBloque(bloque="contenido", peso=35, puntuacion=100.0),
        PuntuacionBloque(bloque="acceso_bots", peso=25, puntuacion=40.0),
        PuntuacionBloque(bloque="rendimiento", peso=10, puntuacion=None),
    ]
    assert puntuar_total(bloques) == 75.0
    assert puntuar_total([PuntuacionBloque(bloque="contenido", peso=35)]) is None


# --- AuditoriaWeb --------------------------------------------------------------------------------


def test_auditoria_todo_ok_es_100() -> None:
    a = _auditoria()
    assert a.puntuacion == 100.0
    assert a.motores_afectados == []
    assert a.version == "web_audit.v1"


def test_auditoria_con_fallos() -> None:
    a = _auditoria({"texto_sin_js": "falla", "tiempo_respuesta": "error"})
    assert a.puntuacion_bloque("contenido").puntuacion == 70.0
    assert a.puntuacion_bloque("rendimiento").puntuacion is None
    assert a.puntuacion == round((25 * 100 + 35 * 70 + 25 * 100 + 5 * 100) / 90, 2)
    assert a.comprobacion("texto_sin_js").estado == "falla"
    assert a.motores_afectados == ["ChatGPT", "Gemini", "Perplexity", "Claude"]


def test_auditoria_rechaza_cifra_a_mano() -> None:
    with pytest.raises(ValidationError, match="puntuar_total"):
        _auditoria(puntuacion=90.0)
    comps = [_comp(i) for i in CATALOGO]
    bloques = [puntuar_bloque(b, comps) for b in BLOQUES]
    bloques[0] = bloques[0].model_copy(update={"puntuacion": 50.0})
    with pytest.raises(ValidationError, match="puntuar_bloque"):
        _auditoria(bloques=bloques)


def test_auditoria_exige_catalogo_completo_sin_repetidos() -> None:
    comps = [_comp(i) for i in CATALOGO if i != "llms_txt"]
    with pytest.raises(ValidationError, match="Faltan"):
        _auditoria(comprobaciones=comps)
    with pytest.raises(ValidationError, match="repetidos"):
        _auditoria(comprobaciones=[*(_comp(i) for i in CATALOGO), _comp("llms_txt")])


def test_auditoria_exige_un_acceso_por_bot() -> None:
    with pytest.raises(ValidationError, match="accesos_bots"):
        _auditoria(accesos_bots=_accesos()[:-1])


def test_auditoria_sin_respuesta_de_la_web() -> None:
    a = _auditoria(dict.fromkeys(CATALOGO, "error"))
    assert a.puntuacion is None
    assert all(b.puntuacion is None for b in a.bloques)


# --- WebFetcher ----------------------------------------------------------------------------------


class _FakeFetcher:
    """Fetcher en memoria: 404 para lo desconocido, error de red para `caido.example` y
    `url_no_permitida` fuera del dominio (como exige el contrato)."""

    name = "fake"

    def __init__(self, paginas: dict[str, str]) -> None:
        self.paginas = paginas
        self.pedidas: list[tuple[str, str | None]] = []

    def get(self, url: str, *, dominio: str, accept: str | None = None) -> RespuestaWeb:
        if not url_permitida(url, dominio):
            return RespuestaWeb(url=url, accept=accept, error="url_no_permitida", obtenido_en=AHORA)
        self.pedidas.append((url, accept))
        if "caido.example" in url:
            return RespuestaWeb(url=url, accept=accept, error="ConnectError", obtenido_en=AHORA)
        if url not in self.paginas:
            return RespuestaWeb(
                url=url, accept=accept, estado_http=404, duracion_ms=3, obtenido_en=AHORA
            )
        return RespuestaWeb(
            url=url,
            url_final=url,
            accept=accept,
            estado_http=200,
            contenido=self.paginas[url],
            cabeceras={"content-type": "text/plain"},
            duracion_ms=7,
            obtenido_en=AHORA,
        )


def _descarga(fetcher: WebFetcher, url: str) -> RespuestaWeb:
    return fetcher.get(url, dominio="a.example", accept="text/markdown")


def test_fake_cumple_el_protocolo_y_no_lanza() -> None:
    fake = _FakeFetcher({"https://a.example/robots.txt": "User-agent: *\nAllow: /"})
    fetcher: WebFetcher = fake
    assert fetcher.name == "fake"
    assert fetcher.get("https://a.example/robots.txt", dominio="a.example").ok
    assert _descarga(fetcher, "https://a.example/llms.txt").estado_http == 404
    caida = fetcher.get("https://caido.example/", dominio="caido.example")
    assert caida.estado_http is None and caida.error
    fuera = fetcher.get("http://169.254.169.254/latest/meta-data/", dominio="a.example")
    assert fuera.estado_http is None and fuera.error == "url_no_permitida"
    assert len(fake.pedidas) == 3
    assert fake.pedidas[1] == ("https://a.example/llms.txt", "text/markdown")


def test_firma_del_protocolo() -> None:
    proto = inspect.signature(WebFetcher.get)
    fake = inspect.signature(_FakeFetcher.get)
    assert list(proto.parameters) == list(fake.parameters) == ["self", "url", "dominio", "accept"]
    assert proto.parameters["dominio"].kind is inspect.Parameter.KEYWORD_ONLY
    assert proto.parameters["dominio"].default is inspect.Parameter.empty
    assert proto.parameters["accept"].kind is inspect.Parameter.KEYWORD_ONLY
    assert proto.parameters["accept"].default is None
    assert "name" in WebFetcher.__annotations__


def test_requisitos_del_contrato_en_el_docstring() -> None:
    doc = WebFetcher.get.__doc__ or ""
    for requisito in (
        "url_permitida",
        "ip_permitida",
        "MAX_REDIRECCIONES",
        "MAX_BYTES_DESCARGA",
        "TIMEOUT_TOTAL_RECURSO_S",
        "streaming",
        "DNS rebinding",
    ):
        assert requisito in doc
    assert MAX_BYTES_DESCARGA >= 2 * MAX_CONTENIDO_CHARS  # caben los caracteres (UTF-8 multibyte)
    assert 0 < TIMEOUT_TOTAL_RECURSO_S <= 10 and 0 < MAX_REDIRECCIONES <= 5


# --- Seguridad: url_permitida e ip_permitida (SSRF) -----------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://alborada.example/",
        "http://alborada.example/robots.txt",
        "https://www.alborada.example/sitemap.xml",
        "https://ALBORADA.example./blog?x=1",
        "https://blog.alborada.example:443/a",
    ],
)
def test_url_permitida_dentro_del_dominio(url: str) -> None:
    assert url_permitida(url, "alborada.example")


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/iam/",
        "http://127.0.0.1:8000/studies",
        "http://localhost/",
        "https://alborada.example.evil.com/",
        "https://evilalborada.example/",
        "https://alborada.example:8080/",
        "ftp://alborada.example/",
        "file:///etc/passwd",
        "gopher://alborada.example/",
        "https://evil.com@alborada.example/",
        "https://alborada.example@evil.com/",
        "https://evil.com\\@alborada.example/",
        "https://alborada.example:99999/",
        "//alborada.example/",
        "/sitemap.xml",
        "",
    ],
)
def test_url_no_permitida_fuera_del_dominio(url: str) -> None:
    assert not url_permitida(url, "alborada.example")


def test_url_permitida_sin_dominio() -> None:
    assert not url_permitida("https://alborada.example/", "")


@pytest.mark.parametrize("ip", ["93.184.216.34", "1.1.1.1", "2606:4700:4700::1111"])
def test_ip_publica_permitida(ip: str) -> None:
    assert ip_permitida(ip)


@pytest.mark.parametrize(
    "ip",
    [
        "10.0.0.5",
        "172.16.3.4",
        "192.168.1.1",
        "127.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "239.255.255.250",
        "240.0.0.1",
        "255.255.255.255",
        "::1",
        "::",
        "fe80::1",
        "fe80::1%eth0",
        "fc00::1",
        "fd12:3456::1",
        "ff02::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
        "64:ff9b::a00:1",
        "2002:a00:1::1",
        "2001:0:4136:e378::1",
        "[::1]",
        "no-es-ip",
        "",
    ],
)
def test_ip_no_permitida(ip: str) -> None:
    assert not ip_permitida(ip)

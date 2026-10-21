"""Auditoría técnica GEO de la web de la marca: ¿pueden los motores leerla? (ADR 0019). Puro.

Analiza las `RespuestaWeb` que ya descargó un `WebFetcher` (sin I/O aquí) y construye la
`AuditoriaWeb` con una `Comprobacion` por id de `CATALOGO`, el acceso de cada bot de IA según
robots.txt y la puntuación por bloque y total (la recalcula el validador del contrato). Después,
`hallazgos_web` convierte las comprobaciones que fallan en `Finding` normales, fuera de
`detect_findings` (como `F-web-propia`), con el criterio de evidencia del ADR 0010.

Todo lo que llega de la web es DATO: se parsea con expresiones y con `html.parser` (sin ejecutar
nada, sin resolver entidades externas) y solo vuelve al usuario como `evidencia` literal recortada a
`MAX_EVIDENCIA_CHARS`. Nunca va a las instrucciones de un LLM.

Piezas:

- **robots.txt** (RFC 9309): `parsear_robots` agrupa por `User-agent` (líneas seguidas comparten
  grupo; los grupos repetidos de un mismo agente se combinan), lee `Allow`/`Disallow` con comodín
  `*` y ancla `$`, las líneas `Sitemap:` y `Content-Signal:`. `acceso_bot` decide si el bot puede
  leer `/`: su grupo propio o, si no tiene, el comodín `*`; gana la regla más larga y, a igual
  largo, `Allow`. Un `Disallow:` vacío no prohíbe nada.
- **HTML**: `texto_visible` (sin script, style, noscript ni template) y `nodos_jsonld` (bloques
  `application/ld+json`, también `@graph` y nodos anidados como el autor Person o las Question de
  un FAQPage).
- **sitemap** (`parsear_sitemap`), **llms.txt** (`llms_txt_valido`), **cabecera Link**
  (`rels_link`) y **Content-Signal** (`parsear_content_signal`).
- **Para el nodo (C)**: `urls_sitemap` (las `Sitemap:` de robots.txt que cumplen `url_permitida`)
  y `paginas_sitemap` (hasta `MAX_PAGINAS_SITEMAP` páginas del mismo dominio, en el orden del
  sitemap).

Reglas de `estado` (ADR 0019): `error` sin respuesta o con 5xx (u otro código que no deja
verificar); `falla` con 403, 404, 406 o 410 en un recurso que debería existir (evidencia «HTTP
404»); `no_aplica` solo si la comprobación depende de otra que no se cumple (`organization_sameas`
sin Organization; `sitemap_en_robots`, `bots_ia_*` y `content_signal` sin robots.txt legible).
Las comprobaciones de Agentes/API no afectan a ningún motor (son informativas: no generan
hallazgos ni cuentan en `AuditoriaWeb.motores_afectados`).
"""

import html
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Final, Literal
from urllib.parse import urlsplit

from posiq.domain.schemas import Evaluation, Finding, Motor, PromptInstance, Run, Talla
from posiq.domain.web_audit_schemas import (
    BLOQUES,
    BOT_MOTOR,
    BOTS_IA,
    CATALOGO,
    MAX_EVIDENCIA_CHARS,
    MAX_PAGINAS_SITEMAP,
    MIN_TEXTO_VISIBLE_CHARS,
    MOTORES,
    RECURSOS,
    UMBRAL_TIEMPO_RESPUESTA_MS,
    AccesoBot,
    AuditoriaWeb,
    Bloque,
    BotIA,
    Comprobacion,
    EstadoComprobacion,
    IdComprobacion,
    OrigenAuditoria,
    RecursoConsultado,
    RespuestaWeb,
    SenalContenido,
    puntuar_bloque,
    puntuar_total,
    url_permitida,
)

# Códigos HTTP que dicen «este recurso no está» (la comprobación falla). 406: no hay la variante
# pedida (p. ej. `Accept: text/markdown`). El resto de no-2xx (5xx, 429, 401...) no deja verificar.
CODIGOS_FALLA: Final = frozenset({403, 404, 406, 410})

# Ruta que decide el acceso de los bots: la portada.
RUTA_PORTADA: Final = "/"

# Tipos schema.org que cuentan como Organization (o subtipo). Además, cualquier tipo terminado en
# «Organization» o «Business».
TIPOS_ORGANIZATION: Final = frozenset(
    {
        "Organization",
        "Corporation",
        "LocalBusiness",
        "MedicalOrganization",
        "MedicalClinic",
        "MedicalBusiness",
        "Hospital",
        "Physician",
        "Dentist",
        "Optician",
        "Pharmacy",
        "DiagnosticLab",
        "ProfessionalService",
        "OnlineStore",
        "Store",
        "NGO",
        "Consortium",
        "Cooperative",
        "Project",
    }
)
# Tipos que cuentan como Article para `jsonld_article` (deben llevar `dateModified`).
TIPOS_ARTICLE: Final = frozenset(
    {
        "Article",
        "BlogPosting",
        "NewsArticle",
        "MedicalWebPage",
        "TechArticle",
        "ScholarlyArticle",
        "MedicalScholarlyArticle",
        "Report",
        "SocialMediaPosting",
        "LiveBlogPosting",
        "AnalysisNewsArticle",
        "OpinionNewsArticle",
        "ReportageNewsArticle",
        "ReviewNewsArticle",
        "BackgroundNewsArticle",
    }
)

# Comprobaciones cuya cifra depende de un umbral (no de una evidencia literal): confianza 0,7.
COMPROBACIONES_UMBRAL: Final[frozenset[IdComprobacion]] = frozenset(
    {"texto_sin_js", "tiempo_respuesta"}
)
CONFIANZA_LITERAL: Final = 0.9
CONFIANZA_UMBRAL: Final = 0.7

# Un bloque con puntuación < 50 genera `F-web-<bloque>`; < 30, impacto L.
UMBRAL_HALLAZGO_BLOQUE: Final = 50.0
UMBRAL_IMPACTO_L_BLOQUE: Final = 30.0
# Bloques que pueden generar `F-web-<bloque>` (acceso de bots solo da `F-web-bots-bloqueados`;
# agentes/API nunca genera hallazgos).
BLOQUES_CON_HALLAZGO: Final[tuple[Bloque, ...]] = ("descubrimiento", "contenido", "rendimiento")

ID_BOTS_BLOQUEADOS: Final = "F-web-bots-bloqueados"

_TITULO_BLOQUE: Final[dict[Bloque, str]] = {
    "descubrimiento": "A los motores les cuesta descubrir las páginas de la web",
    "contenido": "La web ofrece poco contenido legible y estructurado para los motores",
    "rendimiento": "La portada tarda demasiado en responder a los rastreadores",
}

_RUTAS: Final[dict[str, str]] = {r.id: r.ruta for r in RECURSOS}


# --- Utilidades -----------------------------------------------------------------------------------


def _num(x: float) -> str:
    """Número en formato español, con hasta 2 decimales (35.5 → «35,5»)."""
    txt = f"{x:.2f}".rstrip("0").rstrip(".")
    return txt.replace(".", ",")


def _ev(texto: str) -> str:
    """Evidencia literal: sin espacios sobrantes y recortada a `MAX_EVIDENCIA_CHARS`."""
    limpio = " ".join(texto.split())
    if len(limpio) <= MAX_EVIDENCIA_CHARS:
        return limpio
    return limpio[: MAX_EVIDENCIA_CHARS - 1] + "…"


def _es_html(r: RespuestaWeb) -> bool:
    if r.tipo_contenido in ("text/html", "application/xhtml+xml"):
        return True
    inicio = r.contenido.lstrip("\ufeff \t\r\n")[:15].lower()
    return inicio.startswith("<!doctype html") or inicio.startswith("<html")


def _json(texto: str) -> Any | None:
    try:
        return json.loads(texto)
    except (ValueError, RecursionError):
        return None


def _host(url: str) -> str:
    try:
        return (urlsplit(url.strip()).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _del_dominio(url: str, dominio: str) -> bool:
    host, base = _host(url), dominio.strip().lower().rstrip(".")
    return bool(host) and (host == base or host.endswith("." + base))


def _lista_bots(bots: Iterable[BotIA]) -> str:
    return ", ".join(f"{b} ({BOT_MOTOR[b]})" if BOT_MOTOR[b] else b for b in bots)


def _lista_motores(motores: Sequence[Motor]) -> str:
    if len(motores) <= 1:
        return "".join(motores)
    return ", ".join(motores[:-1]) + " y " + motores[-1]


# --- robots.txt (RFC 9309) ------------------------------------------------------------------------


@dataclass(frozen=True)
class ReglaRobots:
    """Una línea `Allow`/`Disallow` con valor. `linea` es la línea literal (sin comentario)."""

    permite: bool
    patron: str
    linea: str


@dataclass(frozen=True)
class GrupoRobots:
    """Grupo de robots.txt: sus `User-agent` (token en minúsculas) y sus reglas."""

    agentes: tuple[str, ...]
    lineas_agente: tuple[str, ...]
    reglas: tuple[ReglaRobots, ...]


@dataclass(frozen=True)
class Robots:
    grupos: tuple[GrupoRobots, ...]
    sitemaps: tuple[str, ...]
    lineas_sitemap: tuple[str, ...]
    content_signal: str | None

    def grupo_propio(self, bot: str) -> bool:
        token = bot.lower()
        return any(token in g.agentes for g in self.grupos)


def _token_agente(valor: str) -> str:
    """`GPTBot/1.1 (+https://...)` → `gptbot`; `*` → `*`."""
    partes = valor.strip().split()
    return partes[0].split("/")[0].lower() if partes else ""


def parsear_robots(texto: str) -> Robots:
    """Parsea robots.txt según RFC 9309 (agrupación por `User-agent`)."""
    grupos: list[GrupoRobots] = []
    agentes: list[str] = []
    lineas_agente: list[str] = []
    reglas: list[ReglaRobots] = []
    con_reglas = False
    sitemaps: list[str] = []
    lineas_sitemap: list[str] = []
    content_signal: str | None = None

    def cerrar() -> None:
        if agentes:
            grupos.append(GrupoRobots(tuple(agentes), tuple(lineas_agente), tuple(reglas)))

    for bruta in texto.lstrip("\ufeff").splitlines():
        linea = bruta.split("#", 1)[0].strip()
        if ":" not in linea:
            continue
        clave, valor = (p.strip() for p in linea.split(":", 1))
        clave = clave.lower()
        if clave == "user-agent":
            if con_reglas:
                cerrar()
                agentes, lineas_agente, reglas, con_reglas = [], [], [], False
            token = _token_agente(valor)
            if token:
                agentes.append(token)
                lineas_agente.append(linea)
            continue
        # Toda línea con clave distinta de `User-agent` (Allow, Disallow, Sitemap,
        # Crawl-delay, Content-Signal o desconocida) cierra la secuencia de agentes,
        # como hace el parser de referencia de Google (google/robotstxt).
        if agentes:
            con_reglas = True
        if clave in ("allow", "disallow"):
            if not agentes:
                continue  # regla fuera de un grupo: se ignora (RFC 9309)
            if valor:  # `Disallow:` vacío no prohíbe nada
                reglas.append(ReglaRobots(clave == "allow", valor, linea))
        elif clave == "sitemap":
            # `Sitemap:` lleva una URL con `:`; se reconstruye desde la línea sin comentario.
            sitemaps.append(valor)
            lineas_sitemap.append(linea)
        elif clave == "content-signal" and content_signal is None:
            content_signal = linea
    cerrar()
    return Robots(tuple(grupos), tuple(sitemaps), tuple(lineas_sitemap), content_signal)


def _coincide(patron: str, ruta: str) -> bool:
    """¿El patrón de robots.txt (con `*` y `$`) coincide con el inicio de `ruta`?"""
    anclado = patron.endswith("$")
    cuerpo = patron[:-1] if anclado else patron
    regex = "".join(".*" if c == "*" else re.escape(c) for c in cuerpo)
    return re.match(regex + (r"\Z" if anclado else ""), ruta) is not None


def regla_decisiva(reglas: Iterable[ReglaRobots], ruta: str = RUTA_PORTADA) -> ReglaRobots | None:
    """La regla que decide `ruta`: la más larga que coincide; a igual largo, `Allow`."""
    candidatas = [r for r in reglas if _coincide(r.patron, ruta)]
    if not candidatas:
        return None
    return max(candidatas, key=lambda r: (len(r.patron), r.permite))


def acceso_bot(robots: Robots | None, bot: BotIA, ruta: str = RUTA_PORTADA) -> AccesoBot:
    """Qué dice robots.txt de `ruta` para `bot`. Sin robots.txt legible: `permitido=None`."""
    motor = BOT_MOTOR[bot]
    if robots is None:
        return AccesoBot(bot=bot, motor=motor, permitido=None)
    token = bot.lower()
    propios = [g for g in robots.grupos if token in g.agentes]
    grupos = propios or [g for g in robots.grupos if "*" in g.agentes]
    regla = regla_decisiva((r for g in grupos for r in g.reglas), ruta)
    return AccesoBot(
        bot=bot,
        motor=motor,
        permitido=regla is None or regla.permite,
        grupo_propio=bool(propios),
        regla=regla.linea if regla else None,
    )


_SENAL = re.compile(r"\b(ai-train|search|ai-input)\s*=\s*(yes|no)\b", re.IGNORECASE)


def parsear_content_signal(linea: str) -> SenalContenido:
    """`Content-Signal: ai-train=no, search=yes, ai-input=yes` → `SenalContenido`."""
    valores: dict[str, bool] = {}
    for clave, valor in _SENAL.findall(linea):
        valores.setdefault(clave.lower(), valor.lower() == "yes")
    return SenalContenido(
        linea=_ev(linea),
        ai_train=valores.get("ai-train"),
        search=valores.get("search"),
        ai_input=valores.get("ai-input"),
    )


# --- HTML: texto visible y JSON-LD ----------------------------------------------------------------

_OCULTOS: Final = frozenset({"script", "style", "noscript", "template"})


class _Texto(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.profundidad = 0
        self.partes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _OCULTOS:
            self.profundidad += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _OCULTOS and self.profundidad:
            self.profundidad -= 1

    def handle_data(self, data: str) -> None:
        if not self.profundidad:
            self.partes.append(data)


def texto_visible(documento: str) -> str:
    """Texto que ve un rastreador sin ejecutar JavaScript (sin script, style, noscript ni
    template), con los espacios colapsados."""
    p = _Texto()
    p.feed(documento)
    p.close()
    return " ".join(" ".join(p.partes).split())


class _JsonLd(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.dentro = False
        self.buffer: list[str] = []
        self.bloques: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        tipo = (dict(attrs).get("type") or "").split(";")[0].strip().lower()
        if tipo == "application/ld+json":
            self.dentro, self.buffer = True, []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.dentro:
            self.bloques.append("".join(self.buffer))
            self.dentro = False

    def handle_data(self, data: str) -> None:
        if self.dentro:
            self.buffer.append(data)


@dataclass(frozen=True)
class NodoJsonLd:
    """Un nodo JSON-LD con `@type` (también anidado), con la URL de la página donde está."""

    tipos: tuple[str, ...]
    datos: Mapping[str, Any]
    url: str


def _nombre_tipo(tipo: str) -> str:
    """`https://schema.org/MedicalClinic` o `schema:MedicalClinic` → `MedicalClinic`."""
    return tipo.strip().rsplit("/", 1)[-1].rsplit(":", 1)[-1]


def _tipos(nodo: Mapping[str, Any]) -> tuple[str, ...]:
    bruto = nodo.get("@type")
    lista = bruto if isinstance(bruto, list) else [bruto]
    return tuple(_nombre_tipo(t) for t in lista if isinstance(t, str) and t.strip())


def _recorrer(obj: Any, url: str, out: list[NodoJsonLd], profundidad: int = 0) -> None:
    if profundidad > 50:
        return
    if isinstance(obj, dict):
        tipos = _tipos(obj)
        if tipos:
            out.append(NodoJsonLd(tipos, obj, url))
        for v in obj.values():
            _recorrer(v, url, out, profundidad + 1)
    elif isinstance(obj, list):
        for v in obj:
            _recorrer(v, url, out, profundidad + 1)


def nodos_jsonld(documento: str, url: str = "") -> list[NodoJsonLd]:
    """Nodos con `@type` de los bloques `<script type="application/ld+json">` del HTML.

    Recorre `@graph` y los objetos anidados. Un bloque que no es JSON válido se ignora.
    """
    p = _JsonLd()
    p.feed(documento)
    p.close()
    out: list[NodoJsonLd] = []
    for bloque in p.bloques:
        datos = _json(bloque.strip())
        if datos is not None:
            _recorrer(datos, url, out)
    return out


def es_organization(tipo: str) -> bool:
    return tipo in TIPOS_ORGANIZATION or tipo.endswith(("Organization", "Business"))


def _valores(v: Any) -> list[Any]:
    return v if isinstance(v, list) else [v]


def _preguntas(faq: NodoJsonLd) -> int:
    encontrados: list[NodoJsonLd] = []
    _recorrer(faq.datos.get("mainEntity"), faq.url, encontrados)
    return sum(1 for n in encontrados if "Question" in n.tipos)


def same_as_externos(nodo: NodoJsonLd, dominio: str) -> list[str]:
    """URLs de `sameAs` que apuntan a otro dominio (perfiles externos)."""
    return [
        u
        for u in _valores(nodo.datos.get("sameAs"))
        if isinstance(u, str) and _host(u) and not _del_dominio(u, dominio)
    ]


# --- Sitemap, llms.txt y cabecera Link ------------------------------------------------------------

_RAIZ_SITEMAP = re.compile(r"<(?:[\w.-]+:)?(urlset|sitemapindex)\b", re.IGNORECASE)
_LOC = re.compile(r"<(?:[\w.-]+:)?loc\s*>(.*?)</(?:[\w.-]+:)?loc\s*>", re.IGNORECASE | re.DOTALL)


def parsear_sitemap(xml: str) -> tuple[Literal["urlset", "sitemapindex"] | None, list[str]]:
    """Raíz (`urlset`/`sitemapindex`, None si no es un sitemap) y las URLs `<loc>` en orden.

    Con expresiones, no con un parser XML: no se resuelven entidades ni DTD.
    """
    raiz = _RAIZ_SITEMAP.search(xml)
    if raiz is None:
        return None, []
    nombre: Literal["urlset", "sitemapindex"] = (
        "urlset" if raiz.group(1).lower() == "urlset" else "sitemapindex"
    )
    locs = [html.unescape(m.strip()) for m in _LOC.findall(xml) if m.strip()]
    return nombre, locs


_URL = re.compile(r"https?://[^\s)>\]\"']+")
_ENLACE_MD = re.compile(r"\]\(([^)\s]+)\)")


def llms_txt_valido(texto: str) -> tuple[bool, str]:
    """¿llms.txt empieza por un título `# ` y enlaza al menos una URL? Devuelve la evidencia."""
    lineas = [ln.strip() for ln in texto.lstrip("\ufeff").splitlines() if ln.strip()]
    if not lineas:
        return False, "llms.txt vacío"
    titulo = lineas[0]
    absoluta, relativa = _URL.search(texto), _ENLACE_MD.search(texto)
    url = absoluta.group(0) if absoluta else relativa.group(1) if relativa else None
    if not titulo.startswith("# "):
        return False, titulo
    if url is None:
        return False, f"{titulo} (sin URLs)"
    return True, f"{titulo} · {url}"


_REL = re.compile(r"""\brel\s*=\s*(?:"([^"]*)"|([^\s;,]+))""", re.IGNORECASE)


def rels_link(cabecera: str) -> set[str]:
    """Valores `rel` de una cabecera HTTP `Link` (RFC 8288), en minúsculas."""
    rels: set[str] = set()
    for entre_comillas, suelto in _REL.findall(cabecera):
        rels.update((entre_comillas or suelto).lower().split())
    return rels


# --- URLs que debe descargar el nodo --------------------------------------------------------------


def _robots_legible(r: RespuestaWeb | None) -> bool:
    return r is not None and r.ok and not _es_html(r)


def urls_sitemap(robots: RespuestaWeb | None, dominio: str) -> list[str]:
    """URLs `Sitemap:` de robots.txt que se pueden descargar (`url_permitida`), sin repetir.

    Vacía si no hay ninguna: entonces vale el `/sitemap.xml` fijo de `RECURSOS`. Un `Sitemap:` a
    otro host (p. ej. `http://169.254.169.254/...`) se ignora (ADR 0019, «Seguridad»).
    """
    if not _robots_legible(robots) or robots is None:
        return []
    vistas: list[str] = []
    for url in parsear_robots(robots.contenido).sitemaps:
        if url_permitida(url, dominio) and url not in vistas:
            vistas.append(url)
    return vistas


def _es_portada(url: str) -> bool:
    try:
        return urlsplit(url).path in ("", "/")
    except ValueError:
        return False


def paginas_sitemap(
    sitemaps: Iterable[RespuestaWeb], dominio: str, maximo: int = MAX_PAGINAS_SITEMAP
) -> list[str]:
    """Hasta `maximo` páginas (no la portada) de los `urlset` descargados, en el orden del sitemap
    y solo si cumplen `url_permitida`. Las de un `sitemapindex` son sitemaps, no páginas."""
    out: list[str] = []
    for r in sitemaps:
        if not r.ok:
            continue
        raiz, locs = parsear_sitemap(r.contenido)
        if raiz != "urlset":
            continue
        for url in locs:
            if len(out) >= maximo:
                return out
            if url_permitida(url, dominio) and not _es_portada(url) and url not in out:
                out.append(url)
    return out


# --- Comprobaciones -------------------------------------------------------------------------------


def _comp(
    id_: IdComprobacion,
    estado: EstadoComprobacion,
    detalle: str,
    recurso: str,
    evidencia: str = "",
    motores: Sequence[Motor] | None = None,
) -> Comprobacion:
    d = CATALOGO[id_]
    if estado == "falla":
        base = () if d.bloque == "agentes_api" else d.motores
        afectados = list(base if motores is None else motores)
    else:
        afectados = []
    return Comprobacion(
        id=id_,
        bloque=d.bloque,
        peso=d.peso,
        estado=estado,
        titulo=d.titulo,
        detalle=detalle,
        evidencia=_ev(evidencia),
        recurso=recurso,
        motores_afectados=afectados,
    )


def _url(r: RespuestaWeb | None, dominio: str, id_recurso: str) -> str:
    if r is None:
        return f"https://{dominio}{_RUTAS.get(id_recurso, '/')}"
    return r.url_final or r.url


def _sin_respuesta_valida(
    id_: IdComprobacion, r: RespuestaWeb | None, url: str
) -> Comprobacion | None:
    """La comprobación si `r` no es 2xx (error o falla según el código); None si es 2xx."""
    if r is None:
        return _comp(id_, "error", f"No se descargó {url}.", url)
    if r.estado_http is None:
        return _comp(id_, "error", f"Sin respuesta de {url} ({r.error}).", url)
    if r.ok:
        return None
    codigo = r.estado_http
    if codigo in CODIGOS_FALLA:
        return _comp(id_, "falla", f"{url} responde HTTP {codigo}.", url, f"HTTP {codigo}")
    return _comp(
        id_, "error", f"{url} responde HTTP {codigo}: no se pudo verificar.", url, f"HTTP {codigo}"
    )


def _depende_de_robots(
    id_: IdComprobacion, r: RespuestaWeb | None, url: str
) -> Comprobacion | None:
    """`no_aplica` sin robots.txt (4xx o HTML); `error` si no se pudo ver; None si es legible."""
    if _robots_legible(r):
        return None
    previa = _sin_respuesta_valida(id_, r, url)
    if previa is not None and previa.estado == "error":
        return previa
    return _comp(id_, "no_aplica", "No hay robots.txt legible: no hay reglas que mirar.", url)


def _c_robots(r: RespuestaWeb | None, robots: Robots | None, url: str) -> Comprobacion:
    previa = _sin_respuesta_valida("robots_txt", r, url)
    if previa is not None or r is None:
        return previa or _comp("robots_txt", "error", f"No se descargó {url}.", url)
    if _es_html(r):
        return _comp(
            "robots_txt",
            "falla",
            "robots.txt devuelve una página HTML, no reglas para rastreadores.",
            url,
            f"Content-Type: {r.tipo_contenido or 'text/html'} · {r.contenido.strip()[:120]}",
        )
    if robots is None or not robots.grupos:
        primera = next((ln.strip() for ln in r.contenido.splitlines() if ln.strip()), "")
        return _comp(
            "robots_txt",
            "falla",
            "robots.txt no tiene ningún grupo `User-agent:`.",
            url,
            primera or "robots.txt vacío",
        )
    n = len(robots.grupos)
    return _comp(
        "robots_txt",
        "ok",
        f"robots.txt tiene {n} grupo{'s' if n != 1 else ''} `User-agent:`.",
        url,
        robots.grupos[0].lineas_agente[0],
    )


def _c_sitemap(candidatas: Sequence[tuple[str, RespuestaWeb | None]]) -> Comprobacion:
    resultados: list[Comprobacion] = []
    for url, r in candidatas:
        previa = _sin_respuesta_valida("sitemap", r, url)
        if previa is not None or r is None:
            resultados.append(previa or _comp("sitemap", "error", f"No se descargó {url}.", url))
            continue
        raiz, locs = parsear_sitemap(r.contenido)
        if raiz is None or not locs:
            ev = f"<{raiz}> sin <loc>" if raiz else (r.contenido.strip()[:120] or "(vacío)")
            resultados.append(
                _comp("sitemap", "falla", "El sitemap no es un `urlset`/`sitemapindex` con "
                      "`<loc>`.", url, ev)
            )  # fmt: skip
            continue
        resultados.append(
            _comp(
                "sitemap",
                "ok",
                f"Sitemap `{raiz}` con {len(locs)} URL{'s' if len(locs) != 1 else ''}.",
                url,
                f"<{raiz}> · <loc>{locs[0]}</loc>",
            )
        )
    for estado in ("ok", "falla"):
        elegida = next((c for c in resultados if c.estado == estado), None)
        if elegida is not None:
            return elegida
    return resultados[0]


def _c_sitemap_en_robots(r: RespuestaWeb | None, robots: Robots | None, url: str) -> Comprobacion:
    previa = _depende_de_robots("sitemap_en_robots", r, url)
    if previa is not None or robots is None:
        return previa or _comp("sitemap_en_robots", "no_aplica", "Sin robots.txt.", url)
    for linea, valor in zip(robots.lineas_sitemap, robots.sitemaps, strict=True):
        if _host(valor) and valor.lower().startswith(("http://", "https://")):
            return _comp("sitemap_en_robots", "ok", "robots.txt declara el sitemap.", url, linea)
    ev = robots.lineas_sitemap[0] if robots.lineas_sitemap else "Sin línea `Sitemap:`"
    return _comp(
        "sitemap_en_robots",
        "falla",
        "robots.txt no declara el sitemap con una URL absoluta.",
        url,
        ev,
    )


def _c_cabeceras_link(r: RespuestaWeb | None, url: str) -> Comprobacion:
    previa = _sin_respuesta_valida("cabeceras_link", r, url)
    if previa is not None or r is None:
        return previa or _comp("cabeceras_link", "error", f"No se descargó {url}.", url)
    link = r.link
    if link and rels_link(link) & {"canonical", "alternate"}:
        return _comp(
            "cabeceras_link",
            "ok",
            "La portada envía `Link` con canonical/alternate.",
            url,
            f"Link: {link}",
        )
    return _comp(
        "cabeceras_link",
        "falla",
        'La portada no envía una cabecera `Link` con `rel="canonical"` ni `alternate`.',
        url,
        f"Link: {link}" if link else "Sin cabecera Link",
    )


def _c_markdown(r: RespuestaWeb | None, url: str) -> Comprobacion:
    previa = _sin_respuesta_valida("markdown_negociado", r, url)
    if previa is not None or r is None:
        return previa or _comp("markdown_negociado", "error", f"No se descargó {url}.", url)
    tipo = r.cabeceras.get("content-type", "")
    if r.tipo_contenido == "text/markdown":
        return _comp(
            "markdown_negociado",
            "ok",
            "Con `Accept: text/markdown` la portada responde en markdown.",
            url,
            f"Content-Type: {tipo}",
        )
    return _comp(
        "markdown_negociado",
        "falla",
        "Con `Accept: text/markdown` la portada no responde en markdown.",
        url,
        f"Content-Type: {tipo}" if tipo else "Sin Content-Type",
    )


def _c_texto(r: RespuestaWeb | None, url: str) -> tuple[Comprobacion, int | None]:
    previa = _sin_respuesta_valida("texto_sin_js", r, url)
    if previa is not None or r is None:
        return previa or _comp("texto_sin_js", "error", f"No se descargó {url}.", url), None
    texto = texto_visible(r.contenido)
    n = len(texto)
    muestra = f"«{texto[:200]}»" if texto else "(sin texto visible)"
    if n >= MIN_TEXTO_VISIBLE_CHARS:
        return _comp(
            "texto_sin_js",
            "ok",
            f"La portada tiene {n} caracteres de texto visible sin JavaScript.",
            url,
            muestra,
        ), n
    return _comp(
        "texto_sin_js",
        "falla",
        f"La portada solo tiene {n} caracteres visibles sin JavaScript (mínimo "
        f"{MIN_TEXTO_VISIBLE_CHARS}): el texto lo pinta JavaScript y los rastreadores no lo ven.",
        url,
        f"{n} caracteres: {muestra}",
    ), n


def _tipo_ev(tipo: str) -> str:
    return f'"@type": "{tipo}"'


def _c_organization(
    portada: RespuestaWeb | None, nodos_portada: Sequence[NodoJsonLd], url: str, dominio: str
) -> tuple[Comprobacion, Comprobacion]:
    previa = _sin_respuesta_valida("jsonld_organization", portada, url)
    if previa is not None:
        sameas = _comp(
            "organization_sameas",
            "error" if previa.estado == "error" else "no_aplica",
            "Sin portada no hay Organization que mirar.",
            url,
        )
        return previa, sameas
    orgs = [n for n in nodos_portada if any(es_organization(t) for t in n.tipos)]
    if not orgs:
        tipos = sorted({t for n in nodos_portada for t in n.tipos})
        org = _comp(
            "jsonld_organization",
            "falla",
            "La portada no declara Organization (ni un subtipo) en JSON-LD.",
            url,
            f"Tipos JSON-LD en la portada: {', '.join(tipos)}" if tipos else "Sin JSON-LD",
        )
        sameas = _comp(
            "organization_sameas", "no_aplica", "Sin Organization no hay `sameAs` que mirar.", url
        )
        return org, sameas
    tipo = next(t for t in orgs[0].tipos if es_organization(t))
    org = _comp(
        "jsonld_organization", "ok", f"La portada declara {tipo} en JSON-LD.", url, _tipo_ev(tipo)
    )
    for nodo in orgs:
        externos = same_as_externos(nodo, dominio)
        if externos:
            return org, _comp(
                "organization_sameas",
                "ok",
                f"La Organization enlaza {len(externos)} perfil"
                f"{'es' if len(externos) != 1 else ''} externo{'s' if len(externos) != 1 else ''}.",
                url,
                '"sameAs": ' + json.dumps(externos, ensure_ascii=False),
            )
    declarado = orgs[0].datos.get("sameAs")
    return org, _comp(
        "organization_sameas",
        "falla",
        "La Organization no enlaza perfiles externos con `sameAs`.",
        url,
        '"sameAs": ' + json.dumps(declarado, ensure_ascii=False)
        if declarado is not None
        else f"{_tipo_ev(tipo)} sin sameAs",
    )


def _c_tipo_paginas(
    id_: IdComprobacion,
    nodos: Sequence[NodoJsonLd],
    paginas_ok: Sequence[str],
    portada: RespuestaWeb | None,
    url_portada: str,
) -> Comprobacion:
    """FAQPage, HowTo, Article, Person, BreadcrumbList en alguna de las páginas auditadas."""
    nombre = CATALOGO[id_].titulo.removeprefix("JSON-LD ")
    if not paginas_ok:
        previa = _sin_respuesta_valida(id_, portada, url_portada)
        return previa or _comp(id_, "error", "No se pudo descargar ninguna página.", url_portada)
    for nodo in nodos:
        if id_ == "jsonld_faqpage" and "FAQPage" in nodo.tipos:
            n = _preguntas(nodo)
            if n:
                return _comp(
                    id_, "ok", f"FAQPage con {n} pregunta{'s' if n != 1 else ''}.", nodo.url,
                    f'{_tipo_ev("FAQPage")} · {n} "Question"',
                )  # fmt: skip
        elif id_ == "jsonld_howto" and "HowTo" in nodo.tipos:
            return _comp(id_, "ok", "Declara HowTo.", nodo.url, _tipo_ev("HowTo"))
        elif id_ == "jsonld_article":
            tipo = next((t for t in nodo.tipos if t in TIPOS_ARTICLE), None)
            fecha = nodo.datos.get("dateModified")
            if tipo and isinstance(fecha, str) and fecha.strip():
                return _comp(
                    id_, "ok", f"{tipo} con dateModified.", nodo.url,
                    f'{_tipo_ev(tipo)} · "dateModified": "{fecha.strip()}"',
                )  # fmt: skip
        elif id_ == "jsonld_person" and "Person" in nodo.tipos:
            return _comp(id_, "ok", "Declara Person.", nodo.url, _tipo_ev("Person"))
        elif id_ == "jsonld_breadcrumb" and "BreadcrumbList" in nodo.tipos:
            return _comp(id_, "ok", "Declara BreadcrumbList.", nodo.url, _tipo_ev("BreadcrumbList"))
    tipos = sorted({t for n in nodos for t in n.tipos})
    n = len(paginas_ok)
    detalle = f"Ninguna de las {n} página{'s' if n != 1 else ''} auditada{'s' if n != 1 else ''} "
    if id_ == "jsonld_article" and any(t in TIPOS_ARTICLE for nd in nodos for t in nd.tipos):
        detalle += "declara Article con `dateModified`."
    elif id_ == "jsonld_faqpage" and any("FAQPage" in nd.tipos for nd in nodos):
        detalle += "declara un FAQPage con preguntas."
    else:
        detalle += f"declara {nombre}."
    ev = f"Tipos JSON-LD en {n} página{'s' if n != 1 else ''}: {', '.join(tipos) or 'ninguno'}"
    return _comp(id_, "falla", detalle, paginas_ok[0], ev)


def _c_llms(r: RespuestaWeb | None, url: str) -> Comprobacion:
    previa = _sin_respuesta_valida("llms_txt", r, url)
    if previa is not None or r is None:
        return previa or _comp("llms_txt", "error", f"No se descargó {url}.", url)
    if _es_html(r):
        return _comp(
            "llms_txt",
            "falla",
            "/llms.txt devuelve una página HTML, no un llms.txt.",
            url,
            f"Content-Type: {r.tipo_contenido or 'text/html'}",
        )
    valido, ev = llms_txt_valido(r.contenido)
    if valido:
        return _comp("llms_txt", "ok", "llms.txt con título y enlaces.", url, ev)
    return _comp(
        "llms_txt", "falla", "llms.txt no empieza por un título `# ` o no enlaza ninguna URL.",
        url, ev,
    )  # fmt: skip


def _accesos(robots: Robots | None) -> list[AccesoBot]:
    return [acceso_bot(robots, b) for b in BOTS_IA]


def _c_bots_sin_bloqueo(
    r: RespuestaWeb | None, accesos: Sequence[AccesoBot], url: str
) -> Comprobacion:
    previa = _depende_de_robots("bots_ia_sin_bloqueo", r, url)
    if previa is not None:
        return previa
    bloqueados = [a for a in accesos if a.permitido is False]
    if not bloqueados:
        reglas = sorted({a.regla for a in accesos if a.regla})
        ev = (
            "Reglas que deciden /: " + "; ".join(reglas)
            if reglas
            else "Ninguna regla Disallow afecta a / para los bots de IA"
        )
        return _comp(
            "bots_ia_sin_bloqueo",
            "ok",
            f"Los {len(accesos)} bots de IA auditados pueden leer la portada.",
            url,
            ev,
        )
    motores = [m for m in MOTORES if any(a.motor == m for a in bloqueados)]
    return _comp(
        "bots_ia_sin_bloqueo",
        "falla",
        f"robots.txt prohíbe la portada a {_lista_bots(a.bot for a in bloqueados)}.",
        url,
        "; ".join(f"{a.bot} → {a.regla}" for a in bloqueados),
        motores,
    )


def _c_bots_explicitos(r: RespuestaWeb | None, robots: Robots | None, url: str) -> Comprobacion:
    previa = _depende_de_robots("bots_ia_reglas_explicitas", r, url)
    if previa is not None or robots is None:
        return previa or _comp("bots_ia_reglas_explicitas", "no_aplica", "Sin robots.txt.", url)
    con_motor = [b for b in BOTS_IA if BOT_MOTOR[b] is not None]
    sin_grupo = [b for b in con_motor if not robots.grupo_propio(b)]
    if not sin_grupo:
        lineas = [
            ln
            for g in robots.grupos
            for ln, ag in zip(g.lineas_agente, g.agentes, strict=True)
            if ag in {b.lower() for b in con_motor}
        ]
        return _comp(
            "bots_ia_reglas_explicitas",
            "ok",
            "robots.txt tiene un grupo propio para cada bot que alimenta a un motor medido.",
            url,
            "; ".join(lineas),
        )
    motores = [m for m in MOTORES if any(BOT_MOTOR[b] == m for b in sin_grupo)]
    return _comp(
        "bots_ia_reglas_explicitas",
        "falla",
        f"Sin grupo `User-agent:` propio para {len(sin_grupo)} de {len(con_motor)} bots; "
        "dependen del comodín.",
        url,
        "Sin grupo propio: " + ", ".join(sin_grupo),
        motores,
    )


def _senal(
    robots_r: RespuestaWeb | None, robots: Robots | None, portada: RespuestaWeb | None
) -> tuple[SenalContenido | None, str | None]:
    """Señal de contenido de robots.txt o, si no hay, de la cabecera; y el recurso de origen."""
    if robots is not None and robots.content_signal and robots_r is not None:
        return parsear_content_signal(robots.content_signal), robots_r.url_final or robots_r.url
    for r in (robots_r, portada):
        if r is not None and r.cabeceras.get("content-signal"):
            linea = f"Content-Signal: {r.cabeceras['content-signal']}"
            return parsear_content_signal(linea), r.url_final or r.url
    return None, None


def _c_content_signal(
    r: RespuestaWeb | None, senal: SenalContenido | None, recurso: str | None, url: str
) -> Comprobacion:
    if senal is None:
        previa = _depende_de_robots("content_signal", r, url)
        if previa is not None:
            return previa
        return _comp(
            "content_signal",
            "falla",
            "Ni robots.txt ni las cabeceras declaran `Content-Signal`.",
            url,
            "Sin Content-Signal",
        )
    if senal.completa:
        return _comp(
            "content_signal",
            "ok",
            "Declara ai-train, search y ai-input.",
            recurso or url,
            senal.linea,
        )
    faltan = [
        k
        for k, v in (("ai-train", senal.ai_train), ("search", senal.search),
                     ("ai-input", senal.ai_input))
        if v is None
    ]  # fmt: skip
    return _comp(
        "content_signal",
        "falla",
        f"Content-Signal no declara {', '.join(faltan)}.",
        recurso or url,
        senal.linea,
    )


def _c_json_agente(
    id_: IdComprobacion,
    candidatas: Sequence[tuple[str, RespuestaWeb | None]],
    clave: str | None,
) -> Comprobacion:
    """Comprobaciones de Agentes/API: 2xx con JSON (y con `clave` si se pide)."""
    resultados: list[Comprobacion] = []
    for url, r in candidatas:
        previa = _sin_respuesta_valida(id_, r, url)
        if previa is not None or r is None:
            resultados.append(previa or _comp(id_, "error", f"No se descargó {url}.", url))
            continue
        datos = _json(r.contenido)
        muestra = r.contenido.strip()[:200] or "(vacío)"
        if datos is None or not isinstance(datos, dict | list):
            resultados.append(_comp(id_, "falla", "La respuesta no es JSON.", url, muestra))
        elif clave is not None and not (isinstance(datos, dict) and clave in datos):
            resultados.append(_comp(id_, "falla", f"El JSON no incluye `{clave}`.", url, muestra))
        else:
            resultados.append(_comp(id_, "ok", "Responde con JSON válido.", url, muestra))
    for estado in ("ok", "falla"):
        elegida = next((c for c in resultados if c.estado == estado), None)
        if elegida is not None:
            return elegida
    return resultados[0]


def _c_tiempo(r: RespuestaWeb | None, url: str) -> Comprobacion:
    previa = _sin_respuesta_valida("tiempo_respuesta", r, url)
    if previa is not None or r is None:
        return previa or _comp("tiempo_respuesta", "error", f"No se descargó {url}.", url)
    if r.duracion_ms is None:
        return _comp("tiempo_respuesta", "error", "La descarga no registró el tiempo.", url)
    ms = r.duracion_ms
    if ms <= UMBRAL_TIEMPO_RESPUESTA_MS:
        return _comp(
            "tiempo_respuesta",
            "ok",
            f"La portada responde en {ms} ms (umbral {UMBRAL_TIEMPO_RESPUESTA_MS} ms).",
            url,
            f"HTTP {r.estado_http} en {ms} ms",
        )
    return _comp(
        "tiempo_respuesta",
        "falla",
        f"La portada tarda {ms} ms en responder (umbral {UMBRAL_TIEMPO_RESPUESTA_MS} ms).",
        url,
        f"HTTP {r.estado_http} en {ms} ms",
    )


# --- Auditoría ------------------------------------------------------------------------------------


def analizar_web(
    respuestas: Mapping[str, RespuestaWeb],
    *,
    study_id: str,
    brand_id: str,
    dominio: str,
    origen: OrigenAuditoria,
    fetcher: str,
    obtenido_en: datetime,
    sitemaps: Sequence[RespuestaWeb] = (),
    paginas: Sequence[RespuestaWeb] = (),
) -> AuditoriaWeb:
    """Construye la `AuditoriaWeb` de `dominio` a partir de descargas ya hechas (sin I/O).

    - `respuestas`: por id de `RECURSOS` (`robots`, `sitemap`, `portada`, `portada_markdown`,
      `llms_txt` y los `.well-known`). Un recurso ausente cuenta como no descargado (`error`).
    - `sitemaps`: las descargas de las URLs de `urls_sitemap(robots, dominio)` (además del
      `/sitemap.xml` fijo); basta con que uno sea válido.
    - `paginas`: las de `paginas_sitemap(...)`, donde también se buscan los tipos JSON-LD.
    """
    desconocidos = set(respuestas) - set(_RUTAS)
    if desconocidos:
        raise ValueError(f"Recursos desconocidos: {sorted(desconocidos)}")

    def r_(id_: str) -> RespuestaWeb | None:
        return respuestas.get(id_)

    def u_(id_: str) -> str:
        return _url(r_(id_), dominio, id_)

    robots_r, portada = r_("robots"), r_("portada")
    robots = parsear_robots(robots_r.contenido) if robots_r and _robots_legible(robots_r) else None
    accesos = _accesos(robots)
    senal, recurso_senal = _senal(robots_r, robots, portada)

    candidatas_sitemap: list[tuple[str, RespuestaWeb | None]] = [
        (s.url_final or s.url, s) for s in sitemaps
    ]
    candidatas_sitemap.append((u_("sitemap"), r_("sitemap")))

    url_portada = u_("portada")
    paginas_ok = [p for p in ([portada] if portada else []) + list(paginas) if p.ok]
    nodos_portada = nodos_jsonld(portada.contenido, url_portada) if portada and portada.ok else []
    nodos = list(nodos_portada)
    for p in paginas_ok[1 if portada and portada.ok else 0 :]:
        nodos.extend(nodos_jsonld(p.contenido, p.url_final or p.url))
    urls_ok = [p.url_final or p.url for p in paginas_ok]

    texto, chars = _c_texto(portada, url_portada)
    org, sameas = _c_organization(portada, nodos_portada, url_portada, dominio)

    comprobaciones = [
        _c_robots(robots_r, robots, u_("robots")),
        _c_sitemap(candidatas_sitemap),
        _c_sitemap_en_robots(robots_r, robots, u_("robots")),
        _c_cabeceras_link(portada, url_portada),
        _c_markdown(r_("portada_markdown"), u_("portada_markdown")),
        texto,
        org,
        sameas,
        *(
            _c_tipo_paginas(id_, nodos, urls_ok, portada, url_portada)
            for id_ in (
                "jsonld_faqpage",
                "jsonld_howto",
                "jsonld_article",
                "jsonld_person",
                "jsonld_breadcrumb",
            )
        ),
        _c_llms(r_("llms_txt"), u_("llms_txt")),
        _c_bots_sin_bloqueo(robots_r, accesos, u_("robots")),
        _c_bots_explicitos(robots_r, robots, u_("robots")),
        _c_content_signal(robots_r, senal, recurso_senal, u_("robots")),
        _c_json_agente("api_catalog", [(u_("api_catalog"), r_("api_catalog"))], "linkset"),
        _c_json_agente(
            "oauth_discovery",
            [
                (u_("openid_configuration"), r_("openid_configuration")),
                (u_("oauth_authorization_server"), r_("oauth_authorization_server")),
            ],
            "issuer",
        ),
        _c_json_agente(
            "oauth_protected_resource",
            [(u_("oauth_protected_resource"), r_("oauth_protected_resource"))],
            "resource",
        ),
        _c_json_agente("mcp_server_card", [(u_("mcp_server_card"), r_("mcp_server_card"))], None),
        _c_json_agente("agent_skills", [(u_("agent_skills"), r_("agent_skills"))], None),
        _c_json_agente("ai_catalog", [(u_("ai_catalog"), r_("ai_catalog"))], None),
        _c_tiempo(portada, url_portada),
    ]
    orden = list(CATALOGO)
    comprobaciones.sort(key=lambda c: orden.index(c.id))
    bloques = [puntuar_bloque(b, comprobaciones) for b in BLOQUES]

    descargas = [respuestas[r.id] for r in RECURSOS if r.id in respuestas]
    descargas += list(sitemaps) + list(paginas)
    return AuditoriaWeb(
        study_id=study_id,
        brand_id=brand_id,
        dominio=dominio,
        origen=origen,
        fetcher=fetcher,
        comprobaciones=comprobaciones,
        bloques=bloques,
        puntuacion=puntuar_total(bloques),
        accesos_bots=accesos,
        senal_contenido=senal,
        tipos_schema=sorted({t for n in nodos for t in n.tipos}),
        texto_visible_chars=chars,
        tiempo_respuesta_ms=portada.duracion_ms if portada is not None else None,
        recursos=[RecursoConsultado.de(d) for d in descargas],
        obtenido_en=obtenido_en,
    )


auditar = analizar_web
"""Alias con el nombre de `docs/estado/A.md`."""


# --- Hallazgos técnicos ---------------------------------------------------------------------------


def _evidencias(
    motores: Sequence[Motor],
    brand_id: str,
    study_id: str,
    evaluaciones: Iterable[Evaluation],
    runs: Mapping[str, Run],
    prompts: Mapping[str, PromptInstance],
) -> list[str]:
    """Evaluaciones espontáneas de la marca en las que NO aparece, en esos motores (ADR 0010)."""
    out: list[str] = []
    for e in evaluaciones:
        if e.brand_id != brand_id or e.aparece or e.study_id != study_id:
            continue
        run = runs.get(e.run_id)
        if run is None or run.motor not in motores or brand_id not in run.marcas_a_evaluar:
            continue
        prompt = prompts.get(run.prompt_id)
        if prompt is not None and prompt.tipo == "espontaneo":
            out.append(e.id)
    return sorted(out)


def _hallazgo_bots(
    auditoria: AuditoriaWeb, ids: Sequence[str], motores: Sequence[Motor]
) -> Finding:
    c = auditoria.comprobacion("bots_ia_sin_bloqueo")
    bloqueados = [a for a in auditoria.accesos_bots if a.permitido is False and a.motor in motores]
    reglas = sorted({a.regla for a in bloqueados if a.regla})
    return Finding(
        id=ID_BOTS_BLOQUEADOS,
        study_id=auditoria.study_id,
        titulo=f"robots.txt impide a {_lista_motores(motores)} leer la web",
        descripcion=(
            f"El robots.txt de {auditoria.dominio} prohíbe la portada a "
            f"{_lista_bots(a.bot for a in bloqueados)} con «{' · '.join(reglas)}». "
            f"La marca no aparece en {len(ids)} respuesta{'s' if len(ids) != 1 else ''} "
            f"espontánea{'s' if len(ids) != 1 else ''} de "
            f"{'ese motor' if len(motores) == 1 else 'esos motores'}. Comprobación `{c.id}`."
        ),
        impacto="L",
        confianza=CONFIANZA_LITERAL,
        cifra=len(motores),
        unidad="recuento",
        origen_cifra=f"{auditoria.version}:{c.id}",
        evaluation_ids=list(ids),
    )


def _hallazgo_bloque(
    auditoria: AuditoriaWeb,
    bloque: Bloque,
    puntuacion: float,
    fallan: Sequence[Comprobacion],
    ids: Sequence[str],
    motores: Sequence[Motor],
) -> Finding:
    impacto: Talla = "L" if puntuacion < UMBRAL_IMPACTO_L_BLOQUE else "M"
    umbral = any(c.id in COMPROBACIONES_UMBRAL for c in fallan)
    lista = "; ".join(f"`{c.id}` ({c.titulo})" for c in fallan)
    return Finding(
        id=f"F-web-{bloque}",
        study_id=auditoria.study_id,
        titulo=_TITULO_BLOQUE[bloque],
        descripcion=(
            f"El bloque {bloque} de la auditoría técnica de {auditoria.dominio} puntúa "
            f"{_num(puntuacion)} de 100. Fallan: {lista}. Afecta a {_lista_motores(motores)}, "
            f"donde la marca no aparece en {len(ids)} respuesta{'s' if len(ids) != 1 else ''} "
            f"espontánea{'s' if len(ids) != 1 else ''}."
        ),
        impacto=impacto,
        confianza=CONFIANZA_UMBRAL if umbral else CONFIANZA_LITERAL,
        cifra=puntuacion,
        unidad="puntos",
        origen_cifra=f"{auditoria.version}:{bloque}",
        evaluation_ids=list(ids),
    )


def hallazgos_web(
    auditoria: AuditoriaWeb,
    evaluaciones: Iterable[Evaluation],
    runs: Iterable[Run],
    *,
    prompts: Iterable[PromptInstance],
    brand_id: str | None = None,
) -> list[Finding]:
    """Hallazgos técnicos de la auditoría (ADR 0019), fuera de `detect_findings`.

    - `F-web-bots-bloqueados` (L): algún bot que alimenta a un motor medido no puede leer la
      portada. `cifra` = número de motores afectados.
    - `F-web-descubrimiento`, `F-web-contenido`, `F-web-rendimiento`: el bloque puntúa < 50
      (L si < 30; M si no). `cifra` = puntuación del bloque.
    - Acceso de bots solo da `F-web-bots-bloqueados`; Agentes/API nunca da hallazgos.
    - `evaluation_ids`: las evaluaciones espontáneas de `brand_id` (por defecto la de la
      auditoría) en las que NO aparece, de los motores afectados. Sin ninguna, no hay hallazgo.
    - `confianza`: 0,9 con evidencia literal; 0,7 si falla una comprobación de umbral
      (`texto_sin_js`, `tiempo_respuesta`).
    """
    marca = brand_id or auditoria.brand_id
    evals = list(evaluaciones)
    por_run = {r.id: r for r in runs}
    por_prompt = {p.id: p for p in prompts}

    def ids_de(motores: Sequence[Motor]) -> list[str]:
        return _evidencias(motores, marca, auditoria.study_id, evals, por_run, por_prompt)

    out: list[Finding] = []
    bots = auditoria.comprobacion("bots_ia_sin_bloqueo")
    if bots.estado == "falla" and bots.motores_afectados:
        motores = [m for m in MOTORES if m in bots.motores_afectados]
        ids = ids_de(motores)
        if ids:
            out.append(_hallazgo_bots(auditoria, ids, motores))
    for bloque in BLOQUES_CON_HALLAZGO:
        puntuacion = auditoria.puntuacion_bloque(bloque).puntuacion
        if puntuacion is None or puntuacion >= UMBRAL_HALLAZGO_BLOQUE:
            continue
        fallan = [c for c in auditoria.comprobaciones if c.bloque == bloque and c.estado == "falla"]
        tocados = {m for c in fallan for m in c.motores_afectados}
        motores = [m for m in MOTORES if m in tocados]
        ids = ids_de(motores)
        if ids:
            out.append(_hallazgo_bloque(auditoria, bloque, puntuacion, fallan, ids, motores))
    return out


hallazgos_tecnicos = hallazgos_web
"""Alias: los hallazgos técnicos de la web."""


def vincular_hallazgos(auditoria: AuditoriaWeb, hallazgos: Iterable[Finding]) -> AuditoriaWeb:
    """La auditoría con `finding_ids` = ids de los hallazgos generados a partir de ella."""
    return auditoria.model_copy(update={"finding_ids": [f.id for f in hallazgos]})

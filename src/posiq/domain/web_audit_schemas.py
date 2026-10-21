"""Modelos de la auditoría técnica GEO de la web de la marca: ¿pueden los motores leerla? (ADR 0019)

Viven fuera de `schemas.py` para no tocar el contrato compartido. El adaptador `WebFetcher`
(`ports.py`) descarga los recursos y devuelve `RespuestaWeb` (DATO crudo: nunca va a las
instrucciones de un LLM); `domain.web_audit` los analiza sin I/O y produce la `AuditoriaWeb`.

La auditoría está organizada en cinco bloques (`BLOQUES`), cada uno con sus comprobaciones
(`CATALOGO`). Cada comprobación tiene un peso dentro de su bloque y cada bloque un peso en el total;
la puntuación de preparación (0-100) es determinista y la calculan `puntuar_bloque` y
`puntuar_total`, que el validador de `AuditoriaWeb` vuelve a aplicar para que nadie pueda publicar
una cifra que no salga de las comprobaciones.

Los hallazgos técnicos se emiten como `Finding` normales fuera de `detect_findings` (como
`F-web-propia`): sus `evaluation_ids` son las respuestas espontáneas en las que la marca no aparece
en los motores afectados. La prueba de la web (línea de robots.txt, tipos JSON-LD...) va en
`Comprobacion.evidencia`, literal.
"""

import ipaddress
from datetime import datetime
from typing import Final, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from posiq.domain.schemas import Motor

VERSION_AUDITORIA: Final = "web_audit.v1"

# --- Bots de IA -----------------------------------------------------------------------------------

BotIA = Literal[
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-SearchBot",
    "Claude-Web",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "Applebot-Extended",
    "CCBot",
]

# Motor medido al que alimenta cada rastreador (user-agent de robots.txt). None: no alimenta a un
# motor concreto de los que mide posiq. (Applebot-Extended: Apple Intelligence; CCBot: Common Crawl,
# corpus de entrenamiento de muchos modelos). Se auditan igual, pero no fijan `motores_afectados`.
BOT_MOTOR: Final[dict[BotIA, Motor | None]] = {
    "GPTBot": "ChatGPT",
    "OAI-SearchBot": "ChatGPT",
    "ChatGPT-User": "ChatGPT",
    "ClaudeBot": "Claude",
    "Claude-SearchBot": "Claude",
    "Claude-Web": "Claude",
    "PerplexityBot": "Perplexity",
    "Perplexity-User": "Perplexity",
    "Google-Extended": "Gemini",
    "Applebot-Extended": None,
    "CCBot": None,
}

BOTS_IA: Final[tuple[BotIA, ...]] = tuple(BOT_MOTOR)
MOTORES: Final[tuple[Motor, ...]] = ("ChatGPT", "Gemini", "Perplexity", "Claude")

# --- Recursos que descarga el adaptador -----------------------------------------------------------

# Cabeceras HTTP que el adaptador conserva (en minúsculas); el resto se descarta.
CABECERAS_RELEVANTES: Final[tuple[str, ...]] = (
    "content-type",
    "link",
    "x-robots-tag",
    "content-signal",
    "last-modified",
)

# Cuerpo máximo que guarda el adaptador (caracteres); lo que pase se trunca y se marca `truncado`.
MAX_CONTENIDO_CHARS: Final = 500_000
# Bytes máximos que el adaptador LEE de un recurso, contados tras descomprimir (gzip/br/deflate).
# La lectura es en streaming y se corta al llegar aquí (`truncado=True`): nunca `resp.text` entero.
MAX_BYTES_DESCARGA: Final = 2_000_000
# Tiempo TOTAL por recurso (conexión + redirecciones + lectura completa del cuerpo), en segundos.
# No es un timeout por lectura: un servidor que envía un byte cada 9 s se corta a los 10 s.
TIMEOUT_TOTAL_RECURSO_S: Final = 10.0
# Saltos de redirección que el adaptador sigue (a mano, revalidando cada `Location`).
MAX_REDIRECCIONES: Final = 5
# Puertos admitidos en las URLs que se descargan (None = el del esquema).
PUERTOS_PERMITIDOS: Final[tuple[int | None, ...]] = (None, 80, 443)
# Longitud máxima de `Comprobacion.evidencia` (fragmento literal del recurso).
MAX_EVIDENCIA_CHARS: Final = 500
# Páginas del sitemap (además de la portada) en las que se buscan los tipos JSON-LD.
MAX_PAGINAS_SITEMAP: Final = 3
# Caracteres de texto visible sin JavaScript a partir de los cuales `texto_sin_js` está «ok».
MIN_TEXTO_VISIBLE_CHARS: Final = 500
# Tiempo de respuesta de la portada hasta el cual `tiempo_respuesta` está «ok».
UMBRAL_TIEMPO_RESPUESTA_MS: Final = 2000


def _normalizar_host(host: str) -> str:
    return host.strip().lower().rstrip(".")


def url_permitida(url: str, dominio: str) -> bool:
    """¿Puede el adaptador descargar `url` para la auditoría de `dominio` (`Brand.dominio`)?

    Solo `http`/`https`, sin credenciales en la URL, con puerto por defecto (`PUERTOS_PERMITIDOS`)
    y con host igual a `dominio` o subdominio suyo. Se aplica a las rutas fijas, a las URLs
    `Sitemap:` de robots.txt, a las páginas del sitemap y a cada `Location` de una redirección.
    Puro (sin DNS): la resolución y `ip_permitida` son cosa del adaptador.
    """
    base = _normalizar_host(dominio)
    if not base:
        return False
    try:
        partes = urlsplit(url.strip())
        puerto = partes.port
    except ValueError:
        return False
    if partes.scheme.lower() not in ("http", "https") or puerto not in PUERTOS_PERMITIDOS:
        return False
    if partes.username is not None or partes.password is not None or "\\" in partes.netloc:
        return False
    host = _normalizar_host(partes.hostname or "")
    return bool(host) and (host == base or host.endswith("." + base))


# Rangos IPv6 que encapsulan una IPv4 (NAT64, 6to4, Teredo): se rechazan enteros.
_IPV6_ENCAPSULADAS: Final = (
    ipaddress.IPv6Network("64:ff9b::/96"),
    ipaddress.IPv6Network("64:ff9b:1::/48"),
    ipaddress.IPv6Network("2002::/16"),
    ipaddress.IPv6Network("2001::/32"),
)


def ip_permitida(ip: str) -> bool:
    """¿Puede el adaptador conectar a `ip` (ya resuelta)? Protección SSRF del ADR 0019.

    Rechaza privadas, loopback, link-local (169.254/16, fe80::/10), CGNAT (100.64/10), ULA
    (fc00::/7), multicast, reservadas, no especificadas, las IPv4 mapeadas en IPv6 que caigan en
    alguno de esos rangos y las IPv6 que encapsulan IPv4 (NAT64, 6to4, Teredo). Solo admite
    direcciones globales. Un texto que no es IP también se rechaza.
    """
    try:
        addr: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(
            ip.strip().strip("[]")
        )
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.scope_id is not None:
            return False
        if addr.ipv4_mapped is not None:
            addr = addr.ipv4_mapped
        elif any(addr in red for red in _IPV6_ENCAPSULADAS):
            return False
    return addr.is_global and not (
        addr.is_multicast or addr.is_reserved or addr.is_unspecified or addr.is_loopback
    )


class Recurso(BaseModel):
    """Descarga fija de la auditoría: `ruta` relativa a `https://<dominio>` y `accept` pedido."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    ruta: str
    accept: str | None = None


# Rutas fijas. Además, el adaptador sigue las URLs `Sitemap:` de robots.txt (si no hay, usa
# `/sitemap.xml`) y descarga hasta `MAX_PAGINAS_SITEMAP` páginas del mismo dominio del sitemap.
# Toda URL (fija, `Sitemap:`, página del sitemap o `Location` de una redirección) pasa antes por
# `url_permitida(url, dominio)`, y toda IP resuelta por `ip_permitida` (ADR 0019, «Seguridad»).
RECURSOS: Final[tuple[Recurso, ...]] = (
    Recurso(id="robots", ruta="/robots.txt"),
    Recurso(id="sitemap", ruta="/sitemap.xml"),
    Recurso(id="portada", ruta="/"),
    Recurso(id="portada_markdown", ruta="/", accept="text/markdown"),
    Recurso(id="llms_txt", ruta="/llms.txt"),
    Recurso(id="api_catalog", ruta="/.well-known/api-catalog"),
    Recurso(id="openid_configuration", ruta="/.well-known/openid-configuration"),
    Recurso(id="oauth_authorization_server", ruta="/.well-known/oauth-authorization-server"),
    Recurso(id="oauth_protected_resource", ruta="/.well-known/oauth-protected-resource"),
    Recurso(id="mcp_server_card", ruta="/.well-known/mcp/server-card.json"),
    Recurso(id="agent_skills", ruta="/.well-known/agent-skills/index.json"),
    Recurso(id="ai_catalog", ruta="/.well-known/ai-catalog.json"),
)

# --- Bloques y catálogo de comprobaciones ---------------------------------------------------------

Bloque = Literal["descubrimiento", "contenido", "acceso_bots", "agentes_api", "rendimiento"]

# Peso de cada bloque en la puntuación total (suman 100). Agentes/API pesa poco: para una clínica es
# informativo y no genera hallazgos (ADR 0019).
PESO_BLOQUE: Final[dict[Bloque, int]] = {
    "descubrimiento": 25,
    "contenido": 35,
    "acceso_bots": 25,
    "rendimiento": 10,
    "agentes_api": 5,
}
BLOQUES: Final[tuple[Bloque, ...]] = tuple(PESO_BLOQUE)

IdComprobacion = Literal[
    # descubrimiento
    "robots_txt",
    "sitemap",
    "sitemap_en_robots",
    "cabeceras_link",
    "markdown_negociado",
    # contenido
    "texto_sin_js",
    "jsonld_organization",
    "organization_sameas",
    "jsonld_faqpage",
    "jsonld_howto",
    "jsonld_article",
    "jsonld_person",
    "jsonld_breadcrumb",
    "llms_txt",
    # acceso de bots de IA
    "bots_ia_sin_bloqueo",
    "bots_ia_reglas_explicitas",
    "content_signal",
    # agentes / API
    "api_catalog",
    "oauth_discovery",
    "oauth_protected_resource",
    "mcp_server_card",
    "agent_skills",
    "ai_catalog",
    # rendimiento
    "tiempo_respuesta",
]

EstadoComprobacion = Literal["ok", "falla", "no_aplica", "error"]
OrigenAuditoria = Literal["real", "fixture"]


class DefComprobacion(BaseModel):
    """Definición fija de una comprobación: bloque, peso dentro del bloque y qué mira.

    `motores`: motores cuya lectura de la web depende de la comprobación; si falla, son los
    `motores_afectados` por defecto (las de bots los reducen a los motores de los bots bloqueados).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: IdComprobacion
    bloque: Bloque
    peso: int = Field(gt=0, le=100)
    titulo: str
    criterio: str
    motores: tuple[Motor, ...] = MOTORES


def _def(
    id_: IdComprobacion,
    bloque: Bloque,
    peso: int,
    titulo: str,
    criterio: str,
    motores: tuple[Motor, ...] = MOTORES,
) -> DefComprobacion:
    return DefComprobacion(
        id=id_, bloque=bloque, peso=peso, titulo=titulo, criterio=criterio, motores=motores
    )


_CATALOGO: tuple[DefComprobacion, ...] = (
    # Descubrimiento (100)
    _def("robots_txt", "descubrimiento", 30, "robots.txt",
         "/robots.txt responde 2xx, no es HTML y tiene al menos un grupo `User-agent:`."),
    _def("sitemap", "descubrimiento", 25, "sitemap.xml",
         "El sitemap (el de robots.txt o /sitemap.xml) responde 2xx y es XML `urlset` o "
         "`sitemapindex` con al menos un `<loc>`."),
    _def("sitemap_en_robots", "descubrimiento", 15, "Sitemap en robots.txt",
         "robots.txt contiene una línea `Sitemap:` con una URL absoluta."),
    _def("cabeceras_link", "descubrimiento", 15, "Cabeceras Link (RFC 8288)",
         "La portada envía una cabecera HTTP `Link` con `rel=\"canonical\"` o "
         "`rel=\"alternate\"`."),
    _def("markdown_negociado", "descubrimiento", 15, "Markdown negociado",
         "Pedida con `Accept: text/markdown`, la portada responde 2xx con `Content-Type: "
         "text/markdown`."),
    # Contenido (100)
    _def("texto_sin_js", "contenido", 30, "Texto legible sin JavaScript",
         f"El HTML de la portada, sin ejecutar JavaScript, tiene al menos "
         f"{MIN_TEXTO_VISIBLE_CHARS} caracteres de texto visible (fuera de script, style, "
         "noscript y template)."),
    _def("jsonld_organization", "contenido", 15, "JSON-LD Organization",
         "La portada tiene un bloque JSON-LD de schema.org con `@type` Organization o un subtipo "
         "(MedicalOrganization, MedicalClinic, LocalBusiness...)."),
    _def("organization_sameas", "contenido", 10, "Organization con sameAs",
         "La Organization declara `sameAs` con al menos un perfil externo (otro dominio).",
         ("Gemini", "ChatGPT")),
    _def("jsonld_faqpage", "contenido", 10, "JSON-LD FAQPage",
         "Alguna página auditada declara `@type` FAQPage con al menos una Question."),
    _def("jsonld_howto", "contenido", 5, "JSON-LD HowTo",
         "Alguna página auditada declara `@type` HowTo."),
    _def("jsonld_article", "contenido", 10, "JSON-LD Article con dateModified",
         "Alguna página auditada declara Article (o BlogPosting, NewsArticle, MedicalWebPage) "
         "con `dateModified`."),
    _def("jsonld_person", "contenido", 5, "JSON-LD Person (autores)",
         "Alguna página auditada declara `@type` Person (autor o profesional)."),
    _def("jsonld_breadcrumb", "contenido", 5, "JSON-LD BreadcrumbList",
         "Alguna página auditada declara `@type` BreadcrumbList."),
    _def("llms_txt", "contenido", 10, "llms.txt",
         "/llms.txt responde 2xx, no es HTML, empieza por un título `# ` y enlaza al menos "
         "una URL."),
    # Acceso de bots de IA (100)
    _def("bots_ia_sin_bloqueo", "acceso_bots", 60, "Bots de IA no bloqueados",
         "Ningún bot de `BOTS_IA` tiene prohibida la portada (`Disallow: /` o equivalente), ni por "
         "su grupo propio ni por el comodín."),
    _def("bots_ia_reglas_explicitas", "acceso_bots", 25, "Reglas explícitas por bot",
         "robots.txt tiene un grupo `User-agent:` propio para cada bot que alimenta a un motor "
         "medido; no basta el comodín."),
    _def("content_signal", "acceso_bots", 15, "Content-Signal",
         "robots.txt (o la cabecera `Content-Signal`) declara `ai-train`, `search` y `ai-input`."),
    # Agentes / API (100, informativo)
    _def("api_catalog", "agentes_api", 20, "/.well-known/api-catalog",
         "Responde 2xx con un linkset JSON (RFC 9727)."),
    _def("oauth_discovery", "agentes_api", 15, "Descubrimiento OAuth/OpenID",
         "/.well-known/openid-configuration u oauth-authorization-server responde 2xx con JSON "
         "que incluye `issuer`."),
    _def("oauth_protected_resource", "agentes_api", 15, "oauth-protected-resource",
         "/.well-known/oauth-protected-resource responde 2xx con JSON que incluye `resource`."),
    _def("mcp_server_card", "agentes_api", 20, "MCP server card",
         "/.well-known/mcp/server-card.json responde 2xx con JSON."),
    _def("agent_skills", "agentes_api", 15, "Agent skills",
         "/.well-known/agent-skills/index.json responde 2xx con JSON."),
    _def("ai_catalog", "agentes_api", 15, "ai-catalog.json",
         "/.well-known/ai-catalog.json responde 2xx con JSON."),
    # Rendimiento (100)
    _def("tiempo_respuesta", "rendimiento", 100, "Tiempo de respuesta de la portada",
         f"La portada responde 2xx en ≤ {UMBRAL_TIEMPO_RESPUESTA_MS} ms (respuesta completa; "
         "LCP, INP y CLS quedan fuera de alcance)."),
)  # fmt: skip

CATALOGO: Final[dict[IdComprobacion, DefComprobacion]] = {d.id: d for d in _CATALOGO}


def _comprobar_catalogo() -> None:
    if sum(PESO_BLOQUE.values()) != 100:
        raise AssertionError("PESO_BLOQUE debe sumar 100")
    for bloque in BLOQUES:
        if sum(d.peso for d in _CATALOGO if d.bloque == bloque) != 100:
            raise AssertionError(f"Los pesos del bloque {bloque} deben sumar 100")
    if len(CATALOGO) != len(_CATALOGO):
        raise AssertionError("CATALOGO tiene ids repetidos")


_comprobar_catalogo()


# --- Modelos --------------------------------------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RespuestaWeb(_Model):
    """Lo que devuelve `WebFetcher.get`: una descarga, también si falló.

    - `estado_http`: None si no hubo respuesta HTTP (DNS, conexión, TLS, timeout); entonces
      `error` lo explica. Un 4xx/5xx NO es un error del fetcher: llega con su `estado_http`.
    - `url_final`: la URL tras seguir redirecciones (None si no hubo respuesta).
    - `accept`: la cabecera Accept pedida (None = la del adaptador por defecto).
    - `contenido`: cuerpo como texto, sin ejecutar JavaScript, leído en streaming hasta
      `MAX_BYTES_DESCARGA` bytes (tras descomprimir) y truncado a `MAX_CONTENIDO_CHARS`;
      `truncado` es True si se cortó por cualquiera de los dos límites.
    - `cabeceras`: solo las de `CABECERAS_RELEVANTES`, con el nombre en minúsculas.
    - `duracion_ms`: tiempo hasta tener la respuesta completa (None si no hubo respuesta).
    """

    url: str
    url_final: str | None = None
    accept: str | None = None
    estado_http: int | None = Field(default=None, ge=100, le=599)
    contenido: str = Field(default="", max_length=MAX_CONTENIDO_CHARS)
    truncado: bool = False
    cabeceras: dict[str, str] = {}
    duracion_ms: int | None = Field(default=None, ge=0)
    error: str | None = None
    obtenido_en: datetime

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if self.estado_http is None and not self.error:
            raise ValueError("RespuestaWeb sin estado_http debe explicar el fallo en `error`")
        fuera = [k for k in self.cabeceras if k not in CABECERAS_RELEVANTES]
        if fuera:
            raise ValueError(f"Cabeceras no relevantes o no en minúsculas: {fuera}")
        return self

    @property
    def ok(self) -> bool:
        """Respuesta 2xx."""
        return self.estado_http is not None and 200 <= self.estado_http < 300

    @property
    def tipo_contenido(self) -> str:
        """Tipo MIME sin parámetros y en minúsculas (`text/html; charset=utf-8` → `text/html`)."""
        return self.cabeceras.get("content-type", "").split(";")[0].strip().lower()

    @property
    def link(self) -> str | None:
        """Cabecera HTTP `Link` tal cual (RFC 8288)."""
        return self.cabeceras.get("link")


class AccesoBot(_Model):
    """Qué dice robots.txt de la portada para `bot`.

    - `permitido`: None si no hay robots.txt legible (sin robots todo está permitido, pero no hay
      evidencia que citar; la comprobación `robots_txt` ya falla).
    - `grupo_propio`: si robots.txt tiene un grupo `User-agent:` con el nombre del bot.
    - `regla`: línea literal de robots.txt que decide (None si decide la ausencia de reglas).
    """

    bot: BotIA
    motor: Motor | None
    permitido: bool | None
    grupo_propio: bool = False
    regla: str | None = None

    @model_validator(mode="after")
    def _motor_del_bot(self) -> Self:
        if self.motor != BOT_MOTOR[self.bot]:
            raise ValueError(f"{self.bot} alimenta a {BOT_MOTOR[self.bot]}, no a {self.motor}")
        return self


class SenalContenido(_Model):
    """Línea Content-Signal (robots.txt o cabecera), con `linea` literal.

    Cada señal: True = `yes`, False = `no`, None = no declarada.
    """

    linea: str = Field(min_length=1)
    ai_train: bool | None = None
    search: bool | None = None
    ai_input: bool | None = None

    @property
    def completa(self) -> bool:
        return None not in (self.ai_train, self.search, self.ai_input)


class Comprobacion(_Model):
    """Resultado de una comprobación de `CATALOGO`.

    - `estado`: `ok`, `falla`, `no_aplica` (no se puede aplicar a esta web, p. ej. sin
      Organization no hay `sameAs` que mirar) o `error` (no se pudo verificar: fallo de red,
      5xx o recurso ilegible).
    - `evidencia`: fragmento literal del recurso (línea de robots.txt, `@type` JSON-LD, «HTTP 404»).
      Obligatoria en `ok` y `falla`.
    - `recurso`: URL consultada de la que sale la evidencia.
    - `motores_afectados`: motores cuya lectura empeora porque falla (vacío si no falla).
    - `bloque` y `peso` se copian de `CATALOGO` y se validan contra él.
    """

    id: IdComprobacion
    bloque: Bloque
    peso: int
    estado: EstadoComprobacion
    titulo: str
    detalle: str = Field(min_length=1)
    evidencia: str = Field(default="", max_length=MAX_EVIDENCIA_CHARS)
    recurso: str
    motores_afectados: list[Motor] = []

    @model_validator(mode="after")
    def _segun_catalogo(self) -> Self:
        d = CATALOGO[self.id]
        if self.bloque != d.bloque or self.peso != d.peso:
            raise ValueError(f"{self.id}: bloque o peso no coinciden con el catálogo")
        if self.estado in ("ok", "falla") and not self.evidencia:
            raise ValueError(f"{self.id}: el estado `{self.estado}` exige evidencia literal")
        if self.estado != "falla" and self.motores_afectados:
            raise ValueError(f"{self.id}: solo una comprobación que falla afecta a motores")
        if len(set(self.motores_afectados)) != len(self.motores_afectados):
            raise ValueError(f"{self.id}: motores_afectados repetidos")
        return self


class PuntuacionBloque(_Model):
    """Preparación de un bloque, 0-100 (None si ninguna comprobación se pudo evaluar)."""

    bloque: Bloque
    peso: int
    puntuacion: float | None = Field(default=None, ge=0, le=100)
    ok: int = Field(default=0, ge=0)
    falla: int = Field(default=0, ge=0)
    no_aplica: int = Field(default=0, ge=0)
    error: int = Field(default=0, ge=0)


def puntuar_bloque(bloque: Bloque, comprobaciones: list[Comprobacion]) -> PuntuacionBloque:
    """Puntuación de `bloque` = 100 × pesos de las `ok` / pesos de las `ok` y `falla`.

    `no_aplica` y `error` no entran en el denominador (no se castiga lo que no se pudo ver); si no
    queda ninguna evaluada, la puntuación es None. Redondeo a 2 decimales.
    """
    propias = [c for c in comprobaciones if c.bloque == bloque]
    evaluadas = [c for c in propias if c.estado in ("ok", "falla")]
    total = sum(c.peso for c in evaluadas)
    puntos = sum(c.peso for c in evaluadas if c.estado == "ok")
    return PuntuacionBloque(
        bloque=bloque,
        peso=PESO_BLOQUE[bloque],
        puntuacion=round(100 * puntos / total, 2) if total else None,
        ok=sum(1 for c in propias if c.estado == "ok"),
        falla=sum(1 for c in propias if c.estado == "falla"),
        no_aplica=sum(1 for c in propias if c.estado == "no_aplica"),
        error=sum(1 for c in propias if c.estado == "error"),
    )


def puntuar_total(bloques: list[PuntuacionBloque]) -> float | None:
    """Media de los bloques con puntuación ponderada por `PESO_BLOQUE`, renormalizada a los
    bloques evaluados. None si ningún bloque tiene puntuación. Redondeo a 2 decimales."""
    con = [(b.peso, b.puntuacion) for b in bloques if b.puntuacion is not None]
    peso = sum(p for p, _ in con)
    if not peso:
        return None
    return round(sum(p * v for p, v in con) / peso, 2)


class RecursoConsultado(_Model):
    """Resumen de una descarga de la auditoría (sin el cuerpo), para trazabilidad."""

    url: str
    accept: str | None = None
    estado_http: int | None = None
    error: str | None = None
    duracion_ms: int | None = Field(default=None, ge=0)

    @classmethod
    def de(cls, respuesta: RespuestaWeb) -> Self:
        return cls(
            url=respuesta.url,
            accept=respuesta.accept,
            estado_http=respuesta.estado_http,
            error=respuesta.error,
            duracion_ms=respuesta.duracion_ms,
        )


class AuditoriaWeb(_Model):
    """Resultado de auditar `dominio` (ADR 0019).

    - `comprobaciones`: exactamente una por id de `CATALOGO`.
    - `bloques`: una `PuntuacionBloque` por bloque, igual a `puntuar_bloque`; `puntuacion` es
      `puntuar_total(bloques)`. El validador lo recalcula: no se aceptan cifras puestas a mano.
    - `accesos_bots`: uno por bot de `BOTS_IA`.
    - `tipos_schema`: valores `@type` de JSON-LD encontrados en las páginas auditadas.
    - `texto_visible_chars`: caracteres de texto visible de la portada sin JavaScript (None si no se
      pudo descargar). `tiempo_respuesta_ms`: el de la portada.
    - `fetcher`: `WebFetcher.name` usado; `origen`: `fixture` en modo kit (dominios `.example`).
    - `finding_ids`: hallazgos generados a partir de ella.
    """

    id: str = "auditoria-web"
    study_id: str
    brand_id: str
    dominio: str = Field(min_length=1)
    origen: OrigenAuditoria
    fetcher: str
    version: str = VERSION_AUDITORIA
    comprobaciones: list[Comprobacion]
    bloques: list[PuntuacionBloque]
    puntuacion: float | None = Field(default=None, ge=0, le=100)
    accesos_bots: list[AccesoBot]
    senal_contenido: SenalContenido | None = None
    tipos_schema: list[str] = []
    texto_visible_chars: int | None = Field(default=None, ge=0)
    tiempo_respuesta_ms: int | None = Field(default=None, ge=0)
    recursos: list[RecursoConsultado] = []
    finding_ids: list[str] = []
    obtenido_en: datetime

    @model_validator(mode="after")
    def _completa_y_coherente(self) -> Self:
        ids = [c.id for c in self.comprobaciones]
        if len(ids) != len(set(ids)):
            raise ValueError("AuditoriaWeb.comprobaciones tiene ids repetidos")
        faltan = set(CATALOGO) - set(ids)
        if faltan:
            raise ValueError(f"Faltan comprobaciones del catálogo: {sorted(faltan)}")
        if sorted(a.bot for a in self.accesos_bots) != sorted(BOTS_IA):
            raise ValueError("accesos_bots debe tener exactamente un acceso por bot de BOTS_IA")
        esperados = {b: puntuar_bloque(b, self.comprobaciones) for b in BLOQUES}
        recibidos = {b.bloque: b for b in self.bloques}
        if len(recibidos) != len(self.bloques) or recibidos != esperados:
            raise ValueError("AuditoriaWeb.bloques no coincide con puntuar_bloque")
        if self.puntuacion != puntuar_total(list(esperados.values())):
            raise ValueError("AuditoriaWeb.puntuacion no coincide con puntuar_total")
        return self

    def comprobacion(self, id_: IdComprobacion) -> Comprobacion:
        return next(c for c in self.comprobaciones if c.id == id_)

    def puntuacion_bloque(self, bloque: Bloque) -> PuntuacionBloque:
        return next(b for b in self.bloques if b.bloque == bloque)

    @property
    def motores_afectados(self) -> list[Motor]:
        """Motores con alguna comprobación en `falla` (en el orden de `MOTORES`)."""
        tocados = {m for c in self.comprobaciones for m in c.motores_afectados}
        return [m for m in MOTORES if m in tocados]

"""`HttpxWebFetcher`: seguridad del ADR 0019 probada SIN red real.

El DNS es un diccionario y la red es un backend de httpcore falso que sirve respuestas HTTP/1.1
crudas y registra a qué IP se conecta. El tiempo es un reloj falso: «esperar» es avanzarlo.
"""

import gzip
import ssl
from dataclasses import dataclass, field

import httpcore
import pytest

from posiq.adapters.web import FixtureWebFetcher, HttpxWebFetcher, crear_web_fetcher
from posiq.adapters.web.httpx_fetcher import USER_AGENT
from posiq.domain.web_audit_schemas import MAX_REDIRECCIONES, TIMEOUT_TOTAL_RECURSO_S

DOMINIO = "clinica.test"
IP_PUBLICA = "93.184.216.34"
IP_PUBLICA_2 = "93.184.216.35"


class Reloj:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@dataclass
class Respuesta:
    """Respuesta HTTP cruda: trozos (retraso_s, bytes) que el stream entrega en orden."""

    estado: int = 200
    cabeceras: list[tuple[str, str]] = field(default_factory=list)
    cuerpo: bytes = b""
    trozos: list[tuple[float, bytes]] | None = None
    retraso: float = 0.0  # antes de la línea de estado

    def crudo(self) -> list[tuple[float, bytes]]:
        cabeceras = list(self.cabeceras)
        if self.trozos is None and not any(k.lower() == "content-length" for k, _ in cabeceras):
            cabeceras.append(("Content-Length", str(len(self.cuerpo))))
        cabeceras.append(("Connection", "close"))
        cabecera = f"HTTP/1.1 {self.estado} X\r\n" + "".join(f"{k}: {v}\r\n" for k, v in cabeceras)
        inicio = (cabecera + "\r\n").encode("latin-1")
        if self.trozos is None:
            return [(self.retraso, inicio + self.cuerpo)]
        return [(self.retraso, inicio), *self.trozos]


class StreamFalso(httpcore.NetworkStream):
    def __init__(self, red: "RedFalsa", ip: str, puerto: int) -> None:
        self.red, self.ip, self.puerto = red, ip, puerto
        self.enviado = b""
        self.pendiente: list[tuple[float, bytes]] | None = None
        self.sni: str | None = None

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.enviado += buffer

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        if self.pendiente is None:
            linea, *resto = self.enviado.decode("latin-1").split("\r\n")
            ruta = linea.split(" ")[1]
            host = next(
                v.strip() for k, _, v in (h.partition(":") for h in resto) if k.lower() == "host"
            )
            self.red.peticiones.append((self.ip, host, ruta, self.enviado.decode("latin-1")))
            self.pendiente = self.red.respuestas.get((host, ruta), Respuesta(404)).crudo()
        if not self.pendiente:
            return b""
        retraso, datos = self.pendiente[0]
        if timeout is not None and retraso > timeout:
            self.red.reloj.t += timeout
            raise httpcore.ReadTimeout("lento")
        self.red.reloj.t += retraso
        trozo, sobra = datos[:max_bytes], datos[max_bytes:]
        if sobra:
            self.pendiente[0] = (0.0, sobra)
        else:
            self.pendiente.pop(0)
        return trozo

    def close(self) -> None:
        pass

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.NetworkStream:
        self.sni = server_hostname
        self.red.sni.append(server_hostname)
        return self

    def get_extra_info(self, info: str) -> object:
        return None


class RedFalsa(httpcore.NetworkBackend):
    def __init__(self, reloj: Reloj) -> None:
        self.reloj = reloj
        self.respuestas: dict[tuple[str, str], Respuesta] = {}
        self.conexiones: list[tuple[str, int]] = []
        self.peticiones: list[tuple[str, str, str, str]] = []
        self.sni: list[str | None] = []

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: object = None,
    ) -> httpcore.NetworkStream:
        self.conexiones.append((host, port))
        return StreamFalso(self, host, port)

    def sleep(self, seconds: float) -> None:
        self.reloj.t += seconds


@pytest.fixture
def reloj() -> Reloj:
    return Reloj()


@pytest.fixture
def red(reloj: Reloj) -> RedFalsa:
    return RedFalsa(reloj)


@pytest.fixture
def dns() -> dict[str, list[str]]:
    return {DOMINIO: [IP_PUBLICA], "www." + DOMINIO: [IP_PUBLICA_2]}


@pytest.fixture
def resoluciones() -> list[str]:
    return []


@pytest.fixture
def fetcher(
    red: RedFalsa, reloj: Reloj, dns: dict[str, list[str]], resoluciones: list[str]
) -> HttpxWebFetcher:
    def resolver(host: str, puerto: int) -> list[str]:
        resoluciones.append(host)
        if host not in dns:
            raise OSError("NXDOMAIN")
        return dns[host]

    return HttpxWebFetcher(resolver=resolver, backend=red, reloj=reloj)


def _redir(destino: str, estado: int = 301) -> Respuesta:
    return Respuesta(estado, [("Location", destino)])


# --- Descarga normal ------------------------------------------------------------------------------


def test_descarga_ok_cabeceras_y_ua(fetcher: HttpxWebFetcher, red: RedFalsa) -> None:
    red.respuestas[(DOMINIO, "/")] = Respuesta(
        200,
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Link", '<https://clinica.test/>; rel="canonical"'),
            ("Link", '<https://clinica.test/en/>; rel="alternate"'),
            ("Set-Cookie", "a=b"),
            ("Server", "nginx"),
        ],
        "<h1>Clínica</h1>".encode(),
    )
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http == 200 and r.ok and r.error is None
    assert r.contenido == "<h1>Clínica</h1>"
    assert r.url_final == f"http://{DOMINIO}/"
    assert r.tipo_contenido == "text/html"
    assert set(r.cabeceras) == {"content-type", "link"}
    assert "canonical" in (r.link or "") and "alternate" in (r.link or "")
    assert r.duracion_ms is not None and r.duracion_ms >= 0
    peticion = red.peticiones[0][3].lower()
    assert f"user-agent: {USER_AGENT}".lower() in peticion
    assert "accept-encoding: gzip, deflate" in peticion


def test_accept_markdown(fetcher: HttpxWebFetcher, red: RedFalsa) -> None:
    red.respuestas[(DOMINIO, "/")] = Respuesta(200, [("Content-Type", "text/markdown")], b"# Hola")
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO, accept="text/markdown")
    assert r.accept == "text/markdown" and r.tipo_contenido == "text/markdown"
    assert "accept: text/markdown\r\n" in red.peticiones[0][3].lower()


def test_4xx_no_es_error(fetcher: HttpxWebFetcher) -> None:
    r = fetcher.get(f"http://{DOMINIO}/llms.txt", dominio=DOMINIO)
    assert r.estado_http == 404 and r.error is None and not r.ok


def test_conecta_a_la_ip_validada_con_host_y_sni_del_nombre(
    fetcher: HttpxWebFetcher, red: RedFalsa, resoluciones: list[str]
) -> None:
    red.respuestas[(DOMINIO, "/")] = Respuesta(200, [("Content-Type", "text/plain")], b"ok")
    r = fetcher.get(f"https://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http == 200
    assert red.conexiones == [(IP_PUBLICA, 443)]  # la IP validada, no el nombre
    assert red.peticiones[0][1] == DOMINIO  # cabecera Host
    assert red.sni == [DOMINIO]  # SNI / certificado del nombre original
    assert resoluciones == [DOMINIO]  # una sola resolución por salto


# --- Destino --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://otro.test/",
        "ftp://clinica.test/",
        "file:///etc/passwd",
        "http://clinica.test:8080/",
        "http://user:pw@clinica.test/",
        "http://169.254.169.254/latest/meta-data/",
        "http://clinica.test.evil.test/",
    ],
)
def test_url_no_permitida_no_conecta(
    fetcher: HttpxWebFetcher, red: RedFalsa, resoluciones: list[str], url: str
) -> None:
    r = fetcher.get(url, dominio=DOMINIO)
    assert r.estado_http is None and r.error == "url_no_permitida"
    assert red.conexiones == [] and resoluciones == []


# --- IP (SSRF y DNS rebinding) --------------------------------------------------------------------


@pytest.mark.parametrize(
    "ips",
    [
        ["10.0.0.5"],
        ["127.0.0.1"],
        ["::ffff:127.0.0.1"],
        ["169.254.169.254"],
        ["192.168.1.10"],
        ["100.64.0.1"],
        ["fd00::1"],
        ["::1"],
        [IP_PUBLICA, "10.0.0.5"],  # basta una IP interna para rechazar
    ],
)
def test_ip_no_permitida(
    fetcher: HttpxWebFetcher, red: RedFalsa, dns: dict[str, list[str]], ips: list[str]
) -> None:
    dns[DOMINIO] = ips
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http is None and r.error == "ip_no_permitida"
    assert red.conexiones == []


def test_dns_falla(fetcher: HttpxWebFetcher, dns: dict[str, list[str]]) -> None:
    del dns[DOMINIO]
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http is None and r.error == "dns"
    dns[DOMINIO] = []
    assert fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO).error == "dns"


# --- Redirecciones --------------------------------------------------------------------------------


def test_redireccion_relativa_y_a_subdominio(fetcher: HttpxWebFetcher, red: RedFalsa) -> None:
    red.respuestas[(DOMINIO, "/")] = _redir("/inicio")
    red.respuestas[(DOMINIO, "/inicio")] = _redir(f"http://www.{DOMINIO}/inicio", 308)
    red.respuestas[("www." + DOMINIO, "/inicio")] = Respuesta(200, [], b"hola")
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http == 200 and r.contenido == "hola"
    assert r.url == f"http://{DOMINIO}/" and r.url_final == f"http://www.{DOMINIO}/inicio"
    assert red.conexiones == [(IP_PUBLICA, 80), (IP_PUBLICA, 80), (IP_PUBLICA_2, 80)]


@pytest.mark.parametrize(
    "location",
    ["http://otro.test/", "http://169.254.169.254/latest/meta-data/", "http://127.0.0.1/"],
)
def test_redireccion_a_otro_host_no_se_sigue(
    fetcher: HttpxWebFetcher, red: RedFalsa, location: str
) -> None:
    red.respuestas[(DOMINIO, "/")] = _redir(location, 302)
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http is None and r.error == "url_no_permitida"
    assert red.conexiones == [(IP_PUBLICA, 80)]


def test_redireccion_a_subdominio_con_ip_interna(
    fetcher: HttpxWebFetcher, red: RedFalsa, dns: dict[str, list[str]]
) -> None:
    dns["interno." + DOMINIO] = ["10.1.2.3"]
    red.respuestas[(DOMINIO, "/")] = _redir(f"http://interno.{DOMINIO}/")
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.error == "ip_no_permitida"
    assert red.conexiones == [(IP_PUBLICA, 80)]


def test_maximo_de_redirecciones(fetcher: HttpxWebFetcher, red: RedFalsa) -> None:
    for i in range(MAX_REDIRECCIONES):
        red.respuestas[(DOMINIO, f"/r{i}")] = _redir(f"/r{i + 1}")
    red.respuestas[(DOMINIO, f"/r{MAX_REDIRECCIONES}")] = Respuesta(200, [], b"fin")
    ok = fetcher.get(f"http://{DOMINIO}/r0", dominio=DOMINIO)
    assert ok.estado_http == 200 and ok.contenido == "fin"

    red.respuestas[(DOMINIO, f"/r{MAX_REDIRECCIONES}")] = _redir("/r-final")
    demasiadas = fetcher.get(f"http://{DOMINIO}/r0", dominio=DOMINIO)
    assert demasiadas.estado_http is None and demasiadas.error == "demasiadas_redirecciones"


# --- Tamaño ---------------------------------------------------------------------------------------


def test_bomba_gzip_se_corta_tras_descomprimir(red: RedFalsa, reloj: Reloj) -> None:
    fetcher = HttpxWebFetcher(
        resolver=lambda h, p: [IP_PUBLICA], backend=red, reloj=reloj, max_bytes=1000
    )
    bomba = gzip.compress(b"a" * 5_000_000)
    assert len(bomba) < 10_000
    red.respuestas[(DOMINIO, "/")] = Respuesta(
        200, [("Content-Type", "text/plain"), ("Content-Encoding", "gzip")], bomba
    )
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http == 200 and r.truncado
    assert r.contenido == "a" * 1000


def test_gzip_normal_se_descomprime(fetcher: HttpxWebFetcher, red: RedFalsa) -> None:
    red.respuestas[(DOMINIO, "/")] = Respuesta(
        200, [("Content-Encoding", "gzip")], gzip.compress("ñandú".encode())
    )
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.contenido == "ñandú" and not r.truncado


def test_cuerpo_sin_comprimir_por_encima_del_tope(red: RedFalsa, reloj: Reloj) -> None:
    fetcher = HttpxWebFetcher(
        resolver=lambda h, p: [IP_PUBLICA], backend=red, reloj=reloj, max_bytes=10
    )
    red.respuestas[(DOMINIO, "/")] = Respuesta(200, [], b"x" * 500)
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.truncado and r.contenido == "x" * 10


def test_codificacion_no_soportada(fetcher: HttpxWebFetcher, red: RedFalsa) -> None:
    red.respuestas[(DOMINIO, "/")] = Respuesta(200, [("Content-Encoding", "br")], b"\x00\x01")
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http == 200 and r.error == "codificacion_no_soportada" and r.contenido == ""


def test_gzip_corrupto(fetcher: HttpxWebFetcher, red: RedFalsa) -> None:
    red.respuestas[(DOMINIO, "/")] = Respuesta(200, [("Content-Encoding", "gzip")], b"no-gzip")
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.error == "contenido_corrupto"


# --- Tiempo ---------------------------------------------------------------------------------------


def test_servidor_lento_cortado_por_el_tope_total(
    fetcher: HttpxWebFetcher, red: RedFalsa, reloj: Reloj
) -> None:
    # Un byte cada 9 s: ninguna lectura sola pasa de 10 s, pero el total sí.
    red.respuestas[(DOMINIO, "/")] = Respuesta(200, [], trozos=[(9.0, b"a")] * 5)
    inicio = reloj.t
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http is None and r.error == "timeout"
    assert reloj.t - inicio <= TIMEOUT_TOTAL_RECURSO_S + 1e-6


def test_redirecciones_consumen_el_mismo_plazo(
    fetcher: HttpxWebFetcher, red: RedFalsa, reloj: Reloj
) -> None:
    # Cada salto tarda 6 s en responder: el segundo ya no cabe en los 10 s del recurso.
    red.respuestas[(DOMINIO, "/")] = Respuesta(301, [("Location", "/b")], retraso=6.0)
    red.respuestas[(DOMINIO, "/b")] = Respuesta(200, [], b"y", retraso=6.0)
    inicio = reloj.t
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.error == "timeout"
    assert reloj.t - inicio <= TIMEOUT_TOTAL_RECURSO_S + 1e-6


# --- Nunca lanza ----------------------------------------------------------------------------------


def test_errores_de_conexion_no_lanzan(reloj: Reloj) -> None:
    class SinConexion(RedFalsa):
        def connect_tcp(
            self, host: str, port: int, *a: object, **k: object
        ) -> httpcore.NetworkStream:  # type: ignore[override]
            raise httpcore.ConnectError("rechazada")

    fetcher = HttpxWebFetcher(
        resolver=lambda h, p: [IP_PUBLICA], backend=SinConexion(reloj), reloj=reloj
    )
    r = fetcher.get(f"http://{DOMINIO}/", dominio=DOMINIO)
    assert r.estado_http is None and r.error == "conexion"


def test_fallo_inesperado_no_lanza(red: RedFalsa, reloj: Reloj) -> None:
    def resolver(host: str, puerto: int) -> list[str]:
        raise RuntimeError("boom")

    r = HttpxWebFetcher(resolver=resolver, backend=red, reloj=reloj).get(
        f"http://{DOMINIO}/", dominio=DOMINIO
    )
    assert r.estado_http is None and r.error == "error_interno"


# --- Fábrica --------------------------------------------------------------------------------------


def test_crear_web_fetcher() -> None:
    assert crear_web_fetcher("off", modo_kit=True) is None
    assert crear_web_fetcher("off", modo_kit=False) is None
    assert isinstance(crear_web_fetcher("fixture", modo_kit=False), FixtureWebFetcher)
    # En modo kit, `real` se degrada a fixture: los dominios .example no existen.
    assert isinstance(crear_web_fetcher("real", modo_kit=True), FixtureWebFetcher)
    assert isinstance(crear_web_fetcher("real", modo_kit=False), HttpxWebFetcher)

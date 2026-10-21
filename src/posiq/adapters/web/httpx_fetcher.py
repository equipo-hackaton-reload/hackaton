"""`WebFetcher` real con httpx para la auditoría técnica GEO (ADR 0019, «Seguridad»).

`Brand.dominio` lo escribe cualquier usuario registrado: el dominio y su DNS se tratan como
hostiles. Por eso este adaptador:

- **Destino:** solo conecta si `url_permitida(url, dominio)` (http/https, puerto por defecto, sin
  credenciales, host = dominio o subdominio). Si no: `error="url_no_permitida"`, sin conexión.
- **IP fijada (SSRF y DNS rebinding):** resuelve el host UNA vez por salto, rechaza el salto si
  ALGUNA IP no cumple `ip_permitida` (`error="ip_no_permitida"`) y conecta a la IP ya validada.
  La URL conserva el nombre, así que `Host` y SNI/certificado son los del nombre original: lo
  único que cambia es el `connect_tcp` del backend de red (`_BackendFijado`).
- **Redirecciones:** a mano (`follow_redirects=False`), como mucho `MAX_REDIRECCIONES`, revalidando
  destino e IP en cada salto. Pasado el máximo: `error="demasiadas_redirecciones"`.
- **Tamaño:** lee el cuerpo crudo en streaming y lo descomprime él mismo con `max_length`, así que
  el tope `MAX_BYTES_DESCARGA` se cuenta tras descomprimir (una bomba gzip se corta igual). Solo
  pide `gzip, deflate`; otra codificación llega con `error="codificacion_no_soportada"`.
- **Tiempo:** `TIMEOUT_TOTAL_RECURSO_S` es el tope TOTAL del recurso: cada operación de red recibe
  como timeout lo que queda hasta ese plazo (`_StreamConPlazo`), y la resolución DNS también.

No lanza: todo fallo llega como `RespuestaWeb` con `estado_http`/`error`. El cuerpo es DATO; este
módulo no lo interpreta (eso es `domain.web_audit`).
"""

import codecs
import socket
import ssl
import time
import zlib
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import UTC, datetime
from typing import Final
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpcore
import httpx

from posiq.domain.web_audit_schemas import (
    CABECERAS_RELEVANTES,
    MAX_BYTES_DESCARGA,
    MAX_CONTENIDO_CHARS,
    MAX_REDIRECCIONES,
    TIMEOUT_TOTAL_RECURSO_S,
    RespuestaWeb,
    ip_permitida,
    url_permitida,
)

USER_AGENT: Final = "posiq-audit/1 (+auditoria tecnica GEO; solo lectura; sin JavaScript)"
ACCEPT_POR_DEFECTO: Final = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5"
)
ACCEPT_ENCODING: Final = "gzip, deflate"
_ESTADOS_REDIRECCION: Final = frozenset({301, 302, 303, 307, 308})
_TAM_TROZO: Final = 64 * 1024

# Resolución DNS: (host, puerto) → IPs como texto. Inyectable en los tests (nunca red real).
Resolver = Callable[[str, int], list[str]]
Reloj = Callable[[], float]
# Igual que `httpcore._backends.base.SOCKET_OPTION` (privado).
_OpcionSocket = (
    tuple[int, int, int] | tuple[int, int, bytes | bytearray] | tuple[int, int, None, int]
)


def resolver_dns(host: str, puerto: int) -> list[str]:
    """Todas las IPs de `host` (A y AAAA), sin duplicados y en el orden del sistema."""
    infos = socket.getaddrinfo(host, puerto, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def _host(host: str) -> str:
    return host.strip().lower().rstrip(".")


class _Plazo:
    """Tope total de un recurso: cada operación de red recibe como mucho lo que queda."""

    def __init__(self, reloj: Reloj, segundos: float) -> None:
        self.reloj = reloj
        self.fin = reloj() + segundos

    def restante(self) -> float:
        return self.fin - self.reloj()

    def acotar(self, timeout: float | None, exc: type[Exception]) -> float:
        restante = self.restante()
        if restante <= 0:
            raise exc("tope total del recurso agotado")
        return restante if timeout is None else min(timeout, restante)


class _StreamConPlazo(httpcore.NetworkStream):
    """Envuelve un stream de red para que ninguna lectura/escritura pase del plazo total."""

    def __init__(self, stream: httpcore.NetworkStream, plazo: _Plazo) -> None:
        self._stream = stream
        self._plazo = plazo

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self._stream.read(max_bytes, self._plazo.acotar(timeout, httpcore.ReadTimeout))

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._stream.write(buffer, self._plazo.acotar(timeout, httpcore.WriteTimeout))

    def close(self) -> None:
        self._stream.close()

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.NetworkStream:
        acotado = self._plazo.acotar(timeout, httpcore.ConnectTimeout)
        return _StreamConPlazo(
            self._stream.start_tls(ssl_context, server_hostname, acotado), self._plazo
        )

    def get_extra_info(self, info: str) -> object:
        return self._stream.get_extra_info(info)


class _BackendFijado(httpcore.NetworkBackend):
    """Backend de red que conecta SOLO a la IP ya validada para cada host (sin re-resolver)."""

    def __init__(self, base: httpcore.NetworkBackend, ips: dict[str, str], plazo: _Plazo) -> None:
        self._base = base
        self._ips = ips
        self._plazo = plazo

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[_OpcionSocket] | None = None,
    ) -> httpcore.NetworkStream:
        ip = self._ips.get(_host(host))
        if ip is None:  # defensa: nunca se conecta a un host que no se haya validado
            raise httpcore.ConnectError(f"host no validado: {host}")
        stream = self._base.connect_tcp(
            ip,
            port,
            timeout=self._plazo.acotar(timeout, httpcore.ConnectTimeout),
            local_address=local_address,
            socket_options=socket_options,
        )
        return _StreamConPlazo(stream, self._plazo)

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[_OpcionSocket] | None = None,
    ) -> httpcore.NetworkStream:
        raise httpcore.ConnectError("sockets unix no permitidos")

    def sleep(self, seconds: float) -> None:
        self._base.sleep(seconds)


class _Fallo(Exception):
    """Fallo sin respuesta HTTP utilizable: termina la descarga con `error=codigo`."""

    def __init__(self, codigo: str) -> None:
        super().__init__(codigo)
        self.codigo = codigo


class HttpxWebFetcher:
    """`ports.WebFetcher` real: GET sin JavaScript con las garantías de seguridad del ADR 0019.

    `resolver`, `backend` y `reloj` existen para probarlo sin red; en producción se usan el DNS
    del sistema, el backend síncrono de httpcore y `time.monotonic`.
    """

    name = "httpx"

    def __init__(
        self,
        *,
        timeout_total_s: float = TIMEOUT_TOTAL_RECURSO_S,
        max_bytes: int = MAX_BYTES_DESCARGA,
        max_redirecciones: int = MAX_REDIRECCIONES,
        user_agent: str = USER_AGENT,
        resolver: Resolver = resolver_dns,
        backend: httpcore.NetworkBackend | None = None,
        reloj: Reloj = time.monotonic,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self.timeout_total_s = timeout_total_s
        self.max_bytes = max_bytes
        self.max_redirecciones = max_redirecciones
        self.user_agent = user_agent
        self._resolver = resolver
        self._backend = backend or httpcore.SyncBackend()
        self._reloj = reloj
        self._ssl_context = ssl_context

    # --- API del puerto ---------------------------------------------------------------------------

    def get(self, url: str, *, dominio: str, accept: str | None = None) -> RespuestaWeb:
        obtenido = datetime.now(UTC)
        plazo = _Plazo(self._reloj, self.timeout_total_s)
        try:
            return self._descargar(url, dominio, accept, plazo, obtenido)
        except _Fallo as fallo:
            return self._fallo(url, accept, fallo.codigo, obtenido)
        except httpx.TimeoutException:
            return self._fallo(url, accept, "timeout", obtenido)
        except httpx.ConnectError as exc:
            codigo = "tls" if _es_tls(exc) else "conexion"
            return self._fallo(url, accept, codigo, obtenido)
        except (httpx.TransportError, httpx.InvalidURL):
            return self._fallo(url, accept, "error_red", obtenido)
        except Exception:  # el contrato: nunca lanza
            return self._fallo(url, accept, "error_interno", obtenido)

    # --- Internos ---------------------------------------------------------------------------------

    def _descargar(
        self, url: str, dominio: str, accept: str | None, plazo: _Plazo, obtenido: datetime
    ) -> RespuestaWeb:
        inicio = self._reloj()
        actual = _sin_fragmento(url.strip())
        for _salto in range(self.max_redirecciones + 1):
            if not url_permitida(actual, dominio):
                raise _Fallo("url_no_permitida")
            partes = urlsplit(actual)
            host = _host(partes.hostname or "")
            puerto = partes.port or (443 if partes.scheme.lower() == "https" else 80)
            ips = self._resolver_con_plazo(host, puerto, plazo)
            if not ips:
                raise _Fallo("dns")
            if not all(ip_permitida(ip) for ip in ips):
                raise _Fallo("ip_no_permitida")
            with self._cliente({host: ips[0]}, plazo) as cliente:
                peticion = cliente.build_request("GET", actual, headers=self._cabeceras(accept))
                respuesta = cliente.send(peticion, stream=True)
                try:
                    location = respuesta.headers.get("location")
                    if respuesta.status_code in _ESTADOS_REDIRECCION and location:
                        actual = _sin_fragmento(urljoin(actual, location.strip()))
                        continue
                    return self._construir(url, actual, accept, respuesta, plazo, inicio, obtenido)
                finally:
                    respuesta.close()
        raise _Fallo("demasiadas_redirecciones")

    def _resolver_con_plazo(self, host: str, puerto: int, plazo: _Plazo) -> list[str]:
        restante = plazo.restante()
        if restante <= 0:
            raise _Fallo("timeout")
        ejecutor = ThreadPoolExecutor(max_workers=1)
        try:
            futuro = ejecutor.submit(self._resolver, host, puerto)
            return list(futuro.result(timeout=restante))
        except FuturesTimeout:
            raise _Fallo("timeout") from None
        except OSError:
            raise _Fallo("dns") from None
        finally:
            ejecutor.shutdown(wait=False)

    def _cliente(self, ips: dict[str, str], plazo: _Plazo) -> httpx.Client:
        transporte = httpx.HTTPTransport(retries=0)
        # httpx no expone el backend de red: se sustituye su pool por uno con el backend que fija
        # la IP validada y acota cada operación al plazo total (probado en los tests).
        transporte._pool = httpcore.ConnectionPool(
            ssl_context=self._ssl_context or httpx.create_ssl_context(),
            http1=True,
            http2=False,
            retries=0,
            network_backend=_BackendFijado(self._backend, ips, plazo),
        )
        return httpx.Client(
            transport=transporte,
            follow_redirects=False,
            trust_env=False,  # sin proxies del entorno: la conexión va a la IP validada
            timeout=httpx.Timeout(self.timeout_total_s),
        )

    def _cabeceras(self, accept: str | None) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": accept or ACCEPT_POR_DEFECTO,
            "Accept-Encoding": ACCEPT_ENCODING,
        }

    def _construir(
        self,
        url: str,
        url_final: str,
        accept: str | None,
        respuesta: httpx.Response,
        plazo: _Plazo,
        inicio: float,
        obtenido: datetime,
    ) -> RespuestaWeb:
        cabeceras = {
            nombre: ", ".join(valores)
            for nombre in CABECERAS_RELEVANTES
            if (valores := respuesta.headers.get_list(nombre))
        }
        cuerpo, truncado, error = self._leer(respuesta, plazo)
        texto = cuerpo.decode(_charset(respuesta), errors="replace")
        if len(texto) > MAX_CONTENIDO_CHARS:
            texto, truncado = texto[:MAX_CONTENIDO_CHARS], True
        return RespuestaWeb(
            url=url,
            url_final=url_final,
            accept=accept,
            estado_http=respuesta.status_code,
            contenido=texto,
            truncado=truncado,
            cabeceras=cabeceras,
            duracion_ms=max(0, int((self._reloj() - inicio) * 1000)),
            error=error,
            obtenido_en=obtenido,
        )

    def _leer(self, respuesta: httpx.Response, plazo: _Plazo) -> tuple[bytes, bool, str | None]:
        """Cuerpo descomprimido, cortado a `max_bytes` sin cargar nunca más que eso."""
        codificacion = respuesta.headers.get("content-encoding", "").strip().lower()
        descompresor: zlib._Decompress | None
        if codificacion in ("", "identity"):
            descompresor = None
        elif codificacion in ("gzip", "x-gzip"):
            descompresor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif codificacion == "deflate":
            descompresor = zlib.decompressobj()
        else:
            return b"", False, "codificacion_no_soportada"
        cuerpo = bytearray()
        try:
            for trozo in respuesta.iter_raw(_TAM_TROZO):
                if plazo.restante() <= 0:
                    raise _Fallo("timeout")
                quedan = self.max_bytes - len(cuerpo)
                datos = descompresor.decompress(trozo, quedan + 1) if descompresor else trozo
                if len(datos) > quedan:
                    cuerpo += datos[:quedan]
                    return bytes(cuerpo), True, None
                cuerpo += datos
            if descompresor is not None:
                resto = descompresor.flush()
                quedan = self.max_bytes - len(cuerpo)
                if len(resto) > quedan:
                    cuerpo += resto[:quedan]
                    return bytes(cuerpo), True, None
                cuerpo += resto
        except zlib.error:
            return b"", False, "contenido_corrupto"
        return bytes(cuerpo), False, None

    @staticmethod
    def _fallo(url: str, accept: str | None, codigo: str, obtenido: datetime) -> RespuestaWeb:
        return RespuestaWeb(url=url, accept=accept, error=codigo, obtenido_en=obtenido)


def _sin_fragmento(url: str) -> str:
    partes = urlsplit(url)
    return urlunsplit(partes._replace(fragment=""))


def _charset(respuesta: httpx.Response) -> str:
    charset = respuesta.charset_encoding or "utf-8"
    try:
        codecs.lookup(charset)
    except LookupError:
        return "utf-8"
    return charset


def _es_tls(exc: BaseException) -> bool:
    actual: BaseException | None = exc
    while actual is not None:
        if isinstance(actual, ssl.SSLError):
            return True
        actual = actual.__cause__ or actual.__context__
    return "ssl" in str(exc).lower() or "certificate" in str(exc).lower()

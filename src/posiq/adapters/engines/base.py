"""Base de los motores reales: caché, reintentos, concurrencia, fuentes, coste y `Budget`.

Cada motor (`openai.py`, `gemini.py`, `perplexity.py`, `anthropic.py`) solo implementa `_call`, que
lanza el prompt con la búsqueda web activada y devuelve un `EngineReply` con el texto íntegro, las
URLs (o dominios) citadas, los tokens y el número de búsquedas. Todo lo demás vive aquí.

El texto que devuelven los motores es DATO: se guarda tal cual en `Run.texto_respuesta` y nunca se
interpola en instrucciones.
"""

import logging
import random
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import SecretStr

from posiq.adapters.budget import Budget, BudgetExceeded
from posiq.adapters.cache import DiskCache
from posiq.adapters.errors import require_secret
from posiq.domain import kit_loader as kl
from posiq.domain.schemas import Motor, PromptInstance, Run, Source, Trace
from posiq.settings import Settings, usd_per_m_to_eur

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({408, 409, 429})
MAX_BACKOFF_S = 30.0


@dataclass
class EngineReply:
    """Respuesta normalizada de un motor; es lo que se guarda en la caché."""

    texto: str
    urls: list[str]
    modelo: str
    tokens_in: int = 0
    tokens_out: int = 0
    busquedas: int = 0
    fecha: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class Pricing:
    """Precios en USD: por millón de tokens de entrada y salida, y por búsqueda web."""

    in_usd_per_m: float
    out_usd_per_m: float
    search_usd: float

    def eur(self, reply: EngineReply, usd_eur: float) -> float:
        return (
            usd_per_m_to_eur(reply.tokens_in, self.in_usd_per_m, usd_eur)
            + usd_per_m_to_eur(reply.tokens_out, self.out_usd_per_m, usd_eur)
            + reply.busquedas * self.search_usd * usd_eur
        )


# --- Fuentes --------------------------------------------------------------------------------------


def domain_of(url_or_domain: str) -> str | None:
    """Dominio en minúsculas y sin `www.` de una URL o de un dominio suelto; None si no hay."""
    text = url_or_domain.strip()
    if not text:
        return None
    host = urlsplit(text if "://" in text else f"//{text}").hostname
    if not host or "." not in host:
        return None
    return host.removeprefix("www.")


def resolve_sources(urls: Sequence[str], catalog: dict[str, Source]) -> list[Source]:
    """Dominios únicos (en orden de aparición) resueltos contra el catálogo del kit.

    Un subdominio hereda el tipo de su dominio padre si este está en el catálogo
    (`blog.medio.com` → `medio.com`). Un dominio desconocido queda con `tipo` y `calidad` None.
    """
    out: list[Source] = []
    seen: set[str] = set()
    for url in urls:
        dominio = domain_of(url)
        if dominio is None or dominio in seen:
            continue
        seen.add(dominio)
        partes = dominio.split(".")
        conocido = next(
            (
                catalog[".".join(partes[i:])]
                for i in range(len(partes) - 1)
                if ".".join(partes[i:]) in catalog
            ),
            None,
        )
        out.append(
            Source(dominio=dominio, tipo=conocido.tipo, calidad=conocido.calidad)
            if conocido
            else Source(dominio=dominio)
        )
    return out


@lru_cache(maxsize=4)
def load_catalog(kit_dir: str) -> dict[str, Source]:
    """Catálogo de fuentes del kit (`fuentes_catalogo.csv`) indexado por dominio."""
    return {s.dominio: s for s in kl.load_sources(Path(kit_dir) / "fuentes_catalogo.csv")}


# --- Reintentos -----------------------------------------------------------------------------------


def status_of(exc: BaseException) -> int | None:
    """Código HTTP de un error de SDK: `status_code` (OpenAI, Anthropic) o `code` (google-genai)."""
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


# --- Motor real -----------------------------------------------------------------------------------


class RealEngine(ABC):
    """`ports.Engine` sobre la API de un proveedor con búsqueda web.

    `marcas_a_evaluar` son los ids de las marcas del mercado del estudio: el motor no las conoce y
    la `Run` las necesita. Sin clave, el motor se construye y falla al llamar con
    `MissingCredentialError` nombrando la variable de entorno.
    """

    motor: Motor
    key_variable: str
    retryable_errors: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)

    def __init__(
        self,
        settings: Settings,
        marcas_a_evaluar: Sequence[str],
        *,
        client: Any | None = None,
        cache: DiskCache | None = None,
        budget: Budget | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not marcas_a_evaluar:
            raise ValueError(f"{self.motor}: hace falta al menos una marca a evaluar")
        self.name: str = self.motor
        self.marcas_a_evaluar = list(marcas_a_evaluar)
        self.cache = cache
        self.budget = budget
        self.usd_eur = settings.usd_eur
        self.max_retries = settings.engine_max_retries
        self.backoff_base_s = settings.engine_backoff_base_s
        self.concurrency = settings.engine_concurrency
        self.kit_dir = str(Path(settings.kit_dir).resolve())
        self._settings = settings
        self._client: Any = client
        self._client_lock = threading.Lock()
        self._semaphore = threading.BoundedSemaphore(settings.engine_concurrency)
        self._sleep = sleep

    # -- Lo que implementa cada motor --

    @property
    @abstractmethod
    def model(self) -> str: ...

    @property
    @abstractmethod
    def pricing(self) -> Pricing: ...

    @abstractmethod
    def _secret(self) -> SecretStr: ...

    @abstractmethod
    def _make_client(self, api_key: str) -> Any:
        """Cliente del SDK sin reintentos propios: los reintentos los hace `_retry`."""

    @abstractmethod
    def _call(self, texto: str) -> EngineReply:
        """Lanza `texto` con búsqueda web. Cada petición HTTP debe ir envuelta en `_retry`."""

    # -- Común --

    @property
    def has_key(self) -> bool:
        return bool(self._secret().get_secret_value())

    @property
    def client(self) -> Any:
        """Cliente del SDK, creado en la primera llamada (sin clave, error claro al llamar)."""
        with self._client_lock:
            if self._client is None:
                key = require_secret(self._secret(), self.key_variable, f"motor {self.motor}")
                self._client = self._make_client(key)
            return self._client

    def _retry[R](self, fn: Callable[[], R]) -> R:
        """Ejecuta `fn` con espera exponencial y jitter ante 408/409/429, 5xx y errores de red."""
        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except Exception as exc:
                status = status_of(exc)
                retryable = isinstance(exc, self.retryable_errors) or (
                    status is not None and (status in RETRYABLE_STATUS or status >= 500)
                )
                if not retryable or attempt == self.max_retries:
                    raise
                delay = min(self.backoff_base_s * 2**attempt, MAX_BACKOFF_S)
                delay += random.uniform(0, self.backoff_base_s)
                logger.warning(
                    "%s: %s (HTTP %s); reintento %d/%d en %.1f s",
                    self.motor,
                    type(exc).__name__,
                    status,
                    attempt + 1,
                    self.max_retries,
                    delay,
                )
                self._sleep(delay)
        raise AssertionError("inalcanzable")  # pragma: no cover

    def cache_key(self, prompt: PromptInstance, repeticion: int) -> str:
        return DiskCache.key(f"engine:{self.motor}", self.model, prompt.texto, repeticion)

    def ask(self, prompt: PromptInstance, *, repeticion: int, study_id: str) -> Run:
        key = self.cache_key(prompt, repeticion)
        cached = self.cache.get(key) if self.cache is not None else None
        if cached is not None:
            return self._run(prompt, repeticion, study_id, EngineReply(**cached), coste_eur=0.0)
        if self.budget is not None and self.budget.remaining_eur <= 0:
            raise BudgetExceeded(
                f"{self.motor}: presupuesto agotado ({self.budget.total_eur:.4f} € de "
                f"{self.budget.max_eur:.2f} €); no se lanza {prompt.id}"
            )

        start = time.perf_counter()
        with self._semaphore:
            reply = self._call(prompt.texto)
        if not reply.urls:
            logger.info(
                "%s: sin fuentes para %s (r%d): el modelo decidió no buscar o no citó nada "
                "(búsquedas=%d)",
                self.motor,
                prompt.id,
                repeticion,
                reply.busquedas,
            )
        coste = self.pricing.eur(reply, self.usd_eur)
        if self.cache is not None:
            self.cache.set(key, asdict(reply))
        run = self._run(prompt, repeticion, study_id, reply, coste_eur=coste)
        if self.budget is not None:
            self.budget.record(
                Trace(
                    study_id=study_id,
                    nodo=f"engine:{self.motor}",
                    modelo=reply.modelo,
                    prompt_version=prompt.id,
                    tokens_in=reply.tokens_in,
                    tokens_out=reply.tokens_out,
                    coste_eur=coste,
                    duracion_ms=round((time.perf_counter() - start) * 1000),
                    fecha=datetime.now(UTC),
                )
            )
        return run

    def _run(
        self,
        prompt: PromptInstance,
        repeticion: int,
        study_id: str,
        reply: EngineReply,
        *,
        coste_eur: float,
    ) -> Run:
        return Run(
            id=f"{prompt.id}:{self.motor}:r{repeticion}",
            study_id=study_id,
            prompt_id=prompt.id,
            motor=self.motor,
            modelo=reply.modelo,
            repeticion=repeticion,
            fecha=datetime.fromisoformat(reply.fecha),
            texto_respuesta=reply.texto,
            fuentes=resolve_sources(reply.urls, load_catalog(self.kit_dir)),
            marcas_a_evaluar=self.marcas_a_evaluar,
            coste_eur=coste_eur,
            tokens=reply.tokens_in + reply.tokens_out,
            origen="api",
        )

    def ask_many(
        self, prompts: Sequence[PromptInstance], *, repeticiones: int, study_id: str
    ) -> list[Run | BaseException]:
        """Todas las combinaciones prompt × repetición en paralelo (máximo `engine_concurrency`).

        Devuelve, en el orden de entrada, la `Run` o la excepción de cada combinación, para que un
        fallo aislado no tire el resto.
        """
        jobs = [(p, r) for p in prompts for r in range(1, repeticiones + 1)]

        def one(job: tuple[PromptInstance, int]) -> Run | BaseException:
            try:
                return self.ask(job[0], repeticion=job[1], study_id=study_id)
            except Exception as exc:
                return exc

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            return list(pool.map(one, jobs))

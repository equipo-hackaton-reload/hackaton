"""Cuentas de usuario, sesiones y propiedad de los estudios (ADR 0015).

Contrato propio, fuera de `ports.py` y de `domain/schemas.py`: el modelo `Study` no cambia; la
propiedad vive en una tabla aparte (`study_id → user_id`). `AccountService` aplica las reglas
(registro, verificación por código, login, sesiones) sobre un `AccountRepo`; la API solo traduce
sus errores a códigos HTTP.

No hay proveedor de correo: el código de verificación se escribe en el log del servidor y, con
`Settings.auth_dev_codes` activo, se devuelve también en la respuesta (`codigo_dev`).
"""

import logging
import re
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Annotated, Protocol
from uuid import uuid4

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from posiq.application.security import (
    ScryptParams,
    hash_secret,
    new_code,
    new_token,
    token_hash,
    verify_secret,
)
from posiq.settings import Settings

log = logging.getLogger(__name__)

CODIGO_TTL = timedelta(minutes=15)
CODIGO_MAX_INTENTOS = 5
PASSWORD_MIN = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def now_utc() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """SQLite devuelve fechas sin zona: se interpretan como UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


# --- Modelos --------------------------------------------------------------------------------------


class Usuario(BaseModel):
    """Lo que la API enseña de un usuario."""

    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    nombre: str | None = None
    verificado: bool = False


class UsuarioGuardado(Usuario):
    password_hash: str
    creado_en: datetime

    def publico(self) -> Usuario:
        return Usuario(id=self.id, email=self.email, nombre=self.nombre, verificado=self.verificado)


class Verificacion(BaseModel):
    """Código pendiente de un correo (solo su hash). Uno por correo: pedir otro lo sustituye."""

    email: str
    codigo_hash: str
    expira_en: datetime
    intentos: int = 0


class Sesion(BaseModel):
    token_hash: str
    user_id: str
    expira_en: datetime


class SesionNueva(BaseModel):
    token: str
    expira_en: datetime
    user: Usuario


class Registro(BaseModel):
    user: Usuario
    codigo: str


Email = Annotated[str, AfterValidator(normalize_email), Field(max_length=254)]


class RegisterBody(BaseModel):
    email: str
    password: str = Field(min_length=PASSWORD_MIN, max_length=1024)
    nombre: str | None = Field(default=None, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        email = normalize_email(value)
        if not EMAIL_RE.match(email) or len(email) > 254:
            raise ValueError("correo no válido")
        return email


class VerifyBody(BaseModel):
    email: Email
    codigo: str = Field(pattern=r"^\d{6}$")


class EmailBody(BaseModel):
    email: Email


class LoginBody(BaseModel):
    email: Email
    password: str = Field(max_length=1024)


# --- Errores --------------------------------------------------------------------------------------


class AccountError(Exception):
    """Error de cuentas con un `codigo` estable que la API usa como `detail`."""

    codigo = "error_de_cuenta"

    def __init__(self, codigo: str | None = None) -> None:
        super().__init__(codigo or self.codigo)
        if codigo:
            self.codigo = codigo


class EmailTaken(AccountError):
    codigo = "correo_ya_registrado"


class InvalidCredentials(AccountError):
    codigo = "credenciales_invalidas"


class NotVerified(AccountError):
    codigo = "correo_no_verificado"


class InvalidCode(AccountError):
    codigo = "codigo_no_valido"


class TooManyAttempts(AccountError):
    codigo = "demasiados_intentos"


# --- Puerto ---------------------------------------------------------------------------------------


class AccountRepo(Protocol):
    """Persistencia de usuarios, verificaciones, sesiones y propiedad de estudios."""

    def add_user(self, user: UsuarioGuardado) -> None:
        """Crea el usuario; `EmailTaken` si el correo ya existe."""
        ...

    def save_user(self, user: UsuarioGuardado) -> None: ...

    def get_user(self, user_id: str) -> UsuarioGuardado | None: ...

    def get_user_by_email(self, email: str) -> UsuarioGuardado | None: ...

    def save_verification(self, verificacion: Verificacion) -> None: ...

    def get_verification(self, email: str) -> Verificacion | None: ...

    def delete_verification(self, email: str) -> None: ...

    def add_session(self, sesion: Sesion) -> None: ...

    def get_session(self, token_hash: str) -> Sesion | None: ...

    def delete_session(self, token_hash: str) -> None: ...

    def set_owner(self, study_id: str, user_id: str) -> None: ...

    def owner_of(self, study_id: str) -> str | None: ...

    def owners(self) -> dict[str, str]:
        """`study_id → user_id` de todos los estudios con propietario."""
        ...


# --- Servicio -------------------------------------------------------------------------------------


def dev_codes(settings: Settings) -> bool:
    """`auth_dev_codes` explícito o, si no se ha fijado, activo solo con `LLM_PROVIDER=fixture`."""
    if settings.auth_dev_codes is not None:
        return settings.auth_dev_codes
    return settings.llm_provider == "fixture"


class AccountService:
    def __init__(self, repo: AccountRepo, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings
        self.params = ScryptParams(
            settings.auth_scrypt_n, settings.auth_scrypt_r, settings.auth_scrypt_p
        )
        self.dev_codes = dev_codes(settings)
        self.limiter = RateLimiter(settings.auth_rate_limit_por_min)
        # Hash de relleno: un login con un correo inexistente tarda lo mismo que uno real.
        self._dummy_hash = hash_secret(new_token(), self.params)

    # Registro y verificación

    def register(self, body: RegisterBody) -> Registro:
        if self.repo.get_user_by_email(body.email) is not None:
            raise EmailTaken()
        user = UsuarioGuardado(
            id=uuid4().hex,
            email=body.email,
            nombre=(body.nombre or "").strip() or None,
            verificado=False,
            password_hash=hash_secret(body.password, self.params),
            creado_en=now_utc(),
        )
        self.repo.add_user(user)
        return Registro(user=user.publico(), codigo=self._issue_code(user.email))

    def resend(self, email: str) -> str | None:
        """Código nuevo si el correo existe y no está verificado; si no, None (sin revelarlo)."""
        user = self.repo.get_user_by_email(email)
        if user is None or user.verificado:
            return None
        return self._issue_code(email)

    def verify(self, email: str, codigo: str) -> Usuario:
        pendiente = self.repo.get_verification(email)
        user = self.repo.get_user_by_email(email)
        if pendiente is None or user is None:
            raise InvalidCode()
        if pendiente.intentos >= CODIGO_MAX_INTENTOS:
            raise TooManyAttempts()
        if as_utc(pendiente.expira_en) <= now_utc():
            raise InvalidCode("codigo_caducado")
        if not verify_secret(codigo, pendiente.codigo_hash):
            self.repo.save_verification(
                pendiente.model_copy(update={"intentos": pendiente.intentos + 1})
            )
            raise InvalidCode()
        self.repo.delete_verification(email)
        verificado = user.model_copy(update={"verificado": True})
        self.repo.save_user(verificado)
        return verificado.publico()

    def _issue_code(self, email: str) -> str:
        codigo = new_code()
        self.repo.save_verification(
            Verificacion(
                email=email,
                codigo_hash=hash_secret(codigo, self.params),
                expira_en=now_utc() + CODIGO_TTL,
            )
        )
        # Sin proveedor de correo: el código va al log del servidor (ADR 0015).
        log.warning("posiq. código de verificación para %s: %s", email, codigo)
        return codigo

    # Sesiones

    def login(self, email: str, password: str) -> SesionNueva:
        user = self.repo.get_user_by_email(email)
        if user is None:
            verify_secret(password, self._dummy_hash)
            raise InvalidCredentials()
        if not verify_secret(password, user.password_hash):
            raise InvalidCredentials()
        if not user.verificado:
            raise NotVerified()
        token = new_token()
        expira = now_utc() + timedelta(hours=self.settings.auth_token_ttl_h)
        sesion = Sesion(token_hash=token_hash(token), user_id=user.id, expira_en=expira)
        self.repo.add_session(sesion)
        return SesionNueva(token=token, expira_en=expira, user=user.publico())

    def user_for_token(self, token: str) -> Usuario | None:
        clave = token_hash(token)
        sesion = self.repo.get_session(clave)
        if sesion is None:
            return None
        if as_utc(sesion.expira_en) <= now_utc():
            self.repo.delete_session(clave)
            return None
        user = self.repo.get_user(sesion.user_id)
        return user.publico() if user is not None and user.verificado else None

    def logout(self, token: str) -> None:
        self.repo.delete_session(token_hash(token))

    # Propiedad de estudios

    def is_demo(self, user: Usuario) -> bool:
        demo = normalize_email(self.settings.auth_demo_user)
        return bool(demo) and user.email == demo

    def can_access(self, user: Usuario, study_id: str) -> bool:
        """Del usuario; o, sin propietario (estudios anteriores a las cuentas), del usuario demo."""
        owner = self.repo.owner_of(study_id)
        return owner == user.id or (owner is None and self.is_demo(user))

    def visible_ids(self, user: Usuario, study_ids: list[str]) -> list[str]:
        owners = self.repo.owners()
        demo = self.is_demo(user)
        return [
            sid for sid in study_ids if owners.get(sid) == user.id or (demo and sid not in owners)
        ]


class RateLimiter:
    """Límite de intentos por clave y minuto, en memoria del proceso.

    Limitación conocida: se pierde al reiniciar y no se comparte entre procesos; vale para un
    solo worker (ver README, limitaciones).
    """

    def __init__(self, por_minuto: int, ventana_s: float = 60.0) -> None:
        self.por_minuto = por_minuto
        self.ventana_s = ventana_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, clave: str) -> bool:
        """Apunta un intento; False si `clave` ya agotó los de la ventana."""
        ahora = time.monotonic()
        hits = self._hits[clave]
        while hits and ahora - hits[0] >= self.ventana_s:
            hits.popleft()
        if len(hits) >= self.por_minuto:
            return False
        hits.append(ahora)
        return True

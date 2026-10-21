"""Rutas `/auth/*` y dependencias de autenticación de la API (ADR 0015).

- `POST /auth/register {email, password, nombre?}` → 201 `{user, verificacion}`; 409 si el correo
  existe (revela que está registrado: riesgo aceptado en el ADR 0015, la web lo usa para ofrecer
  el login); 422 si la contraseña tiene menos de 8 caracteres.
- `POST /auth/verify {email, codigo}` → 200 `{user}`; 400 código no válido o caducado; 429 tras 5
  intentos (hay que pedir otro con `POST /auth/verify/reenviar {email}` → 202, como mucho 3 por
  correo y hora; el cuarto, 429).
- `POST /auth/login {email, password}` → 200 `{token, expira_en, user}`; 401 credenciales
  incorrectas (mismo mensaje si el correo no existe); 403 `correo_no_verificado`.
- `POST /auth/logout` (Bearer) → 204. `GET /auth/me` (Bearer) → 200 `{user}`.
- La cuenta de demo (`demo@posiq.local`, contraseña en `scripts/demo_kit.py`) y `AUTH_DEMO_USER`
  fuera del modo demo → 403 `cuenta_demo_desactivada`.

Los POST con cuerpo exigen `Content-Type: application/json` (415). Login, verificación, registro y
reenvío tienen un límite de intentos por minuto y cliente, en memoria (429). Login, verificación y
reenvío cuentan además por correo: verificar y reenviar comparten esa clave, así que repartir los
intentos entre varias IP o entre las dos rutas no da más intentos sobre el mismo correo.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from posiq.application.accounts import (
    AccountError,
    AccountService,
    DemoDisabled,
    EmailBody,
    EmailTaken,
    InvalidCode,
    InvalidCredentials,
    LoginBody,
    NotVerified,
    RegisterBody,
    SesionNueva,
    TooManyAttempts,
    Usuario,
    VerifyBody,
)

CODIGOS_HTTP: dict[type[AccountError], int] = {
    EmailTaken: status.HTTP_409_CONFLICT,
    InvalidCredentials: status.HTTP_401_UNAUTHORIZED,
    NotVerified: status.HTTP_403_FORBIDDEN,
    DemoDisabled: status.HTTP_403_FORBIDDEN,
    InvalidCode: status.HTTP_400_BAD_REQUEST,
    TooManyAttempts: status.HTTP_429_TOO_MANY_REQUESTS,
}


class UserResponse(BaseModel):
    user: Usuario


def get_accounts(request: Request) -> AccountService:
    accounts: AccountService | None = getattr(request.app.state, "accounts", None)
    if accounts is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "la API aún no ha arrancado")
    return accounts


Accounts = Annotated[AccountService, Depends(get_accounts)]


def require_json(request: Request) -> None:
    """415 si un POST con cuerpo JSON no declara `Content-Type: application/json`."""
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "se espera Content-Type: application/json"
        )


def bearer_token(request: Request) -> str | None:
    esquema, _, token = request.headers.get("authorization", "").partition(" ")
    if esquema.lower() != "bearer":
        return None
    return token.strip() or None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "no_autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user(request: Request, accounts: Accounts) -> Usuario:
    """Usuario del token Bearer; 401 sin token, con uno desconocido, caducado o cerrado."""
    token = bearer_token(request)
    user = accounts.user_for_token(token) if token else None
    if user is None:
        raise _unauthorized()
    return user


CurrentUser = Annotated[Usuario, Depends(current_user)]


def _cliente(request: Request) -> str:
    return request.client.host if request.client else "?"


def _limit(request: Request, accounts: AccountService, correo: str | None = None) -> None:
    """429 si el cliente agotó sus intentos en la ruta o, con `correo`, para ese correo.

    Con `correo` hay tres claves, de la más estrecha a la más ancha: IP y ruta, IP y correo, y el
    correo desde cualquier IP (con un umbral `FACTOR_LIMITE_CORREO` veces mayor). Se cortocircuita:
    una petición ya rechazada no se apunta en las claves siguientes, así que un cliente limitado
    no crea claves nuevas (memoria) ni gasta el cupo global del correo (bloqueo de cuentas ajenas).
    """
    cliente = _cliente(request)
    claves = [(accounts.limiter, f"ip:{cliente}:{request.url.path}")]
    if correo is not None:
        claves.append((accounts.limiter, f"ip-correo:{cliente}:{correo}"))
        claves.append((accounts.limiter_correo, f"correo:{correo}"))
    for limiter, clave in claves:
        if not limiter.hit(clave):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "demasiados_intentos")


def correo_clave(ruta: str, email: str) -> str:
    """Clave por correo: verificar y reenviar la comparten; login tiene la suya."""
    return f"{'login' if ruta == 'login' else 'verificacion'}:{email}"


def _http(exc: AccountError) -> HTTPException:
    return HTTPException(CODIGOS_HTTP.get(type(exc), status.HTTP_400_BAD_REQUEST), exc.codigo)


def _verificacion(accounts: AccountService, codigo: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {"enviado": True}
    if accounts.dev_codes and codigo is not None:
        body["codigo_dev"] = codigo
    return body


router = APIRouter(prefix="/auth", tags=["auth"])
JSON_ONLY = [Depends(require_json)]


@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=JSON_ONLY)
def register(request: Request, body: RegisterBody, accounts: Accounts) -> JSONResponse:
    _limit(request, accounts)
    try:
        registro = accounts.register(body)
    except AccountError as exc:
        raise _http(exc) from exc
    return JSONResponse(
        {
            "user": registro.user.model_dump(mode="json"),
            "verificacion": _verificacion(accounts, registro.codigo),
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/verify", dependencies=JSON_ONLY)
def verify(request: Request, body: VerifyBody, accounts: Accounts) -> UserResponse:
    _limit(request, accounts, correo_clave("verify", body.email))
    try:
        return UserResponse(user=accounts.verify(body.email, body.codigo))
    except AccountError as exc:
        raise _http(exc) from exc


@router.post("/verify/reenviar", status_code=status.HTTP_202_ACCEPTED, dependencies=JSON_ONLY)
def resend(request: Request, body: EmailBody, accounts: Accounts) -> JSONResponse:
    """202 exista o no el correo, para no revelar qué correos están registrados.

    429 si este cliente pidió ya 3 códigos para el correo en la última hora, o el correo 10 en
    total (también si no existe).
    """
    _limit(request, accounts, correo_clave("reenviar", body.email))
    try:
        codigo = accounts.resend(body.email, _cliente(request))
    except AccountError as exc:
        raise _http(exc) from exc
    return JSONResponse(_verificacion(accounts, codigo), status_code=status.HTTP_202_ACCEPTED)


@router.post("/login", dependencies=JSON_ONLY)
def login(request: Request, body: LoginBody, accounts: Accounts) -> SesionNueva:
    _limit(request, accounts, correo_clave("login", body.email))
    try:
        return accounts.login(body.email, body.password)
    except AccountError as exc:
        raise _http(exc) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, user: CurrentUser, accounts: Accounts) -> Response:
    token = bearer_token(request)
    if token:
        accounts.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser) -> UserResponse:
    return UserResponse(user=user)

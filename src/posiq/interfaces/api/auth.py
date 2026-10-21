"""Rutas `/auth/*` y dependencias de autenticación de la API (ADR 0015).

- `POST /auth/register {email, password, nombre?}` → 201 `{user, verificacion}`; 409 si el correo
  existe; 422 si la contraseña tiene menos de 8 caracteres.
- `POST /auth/verify {email, codigo}` → 200 `{user}`; 400 código no válido o caducado; 429 tras 5
  intentos fallidos (hay que pedir otro con `POST /auth/verify/reenviar {email}` → 202).
- `POST /auth/login {email, password}` → 200 `{token, expira_en, user}`; 401 credenciales
  incorrectas (mismo mensaje si el correo no existe); 403 `correo_no_verificado`.
- `POST /auth/logout` (Bearer) → 204. `GET /auth/me` (Bearer) → 200 `{user}`.

Los POST con cuerpo exigen `Content-Type: application/json` (415). Login, verificación, registro y
reenvío tienen un límite de intentos por minuto y cliente, en memoria (429).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from posiq.application.accounts import (
    AccountError,
    AccountService,
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


def _limit(request: Request, accounts: AccountService) -> None:
    cliente = request.client.host if request.client else "?"
    if not accounts.limiter.hit(f"{cliente}:{request.url.path}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "demasiados_intentos")


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
    _limit(request, accounts)
    try:
        return UserResponse(user=accounts.verify(body.email, body.codigo))
    except AccountError as exc:
        raise _http(exc) from exc


@router.post("/verify/reenviar", status_code=status.HTTP_202_ACCEPTED, dependencies=JSON_ONLY)
def resend(request: Request, body: EmailBody, accounts: Accounts) -> JSONResponse:
    """Siempre 202, exista o no el correo, para no revelar qué correos están registrados."""
    _limit(request, accounts)
    codigo = accounts.resend(body.email)
    return JSONResponse(_verificacion(accounts, codigo), status_code=status.HTTP_202_ACCEPTED)


@router.post("/login", dependencies=JSON_ONLY)
def login(request: Request, body: LoginBody, accounts: Accounts) -> SesionNueva:
    _limit(request, accounts)
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

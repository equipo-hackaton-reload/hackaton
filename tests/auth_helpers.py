"""Usuario de test para las pruebas de la API: registro, verificación con `codigo_dev` y login.

El cliente queda con `Authorization: Bearer <token>` en sus cabeceras. Requiere
`auth_dev_codes` activo (por defecto con `LLM_PROVIDER=fixture`).
"""

from typing import Any

import httpx

TEST_EMAIL = "test@posiq.local"
TEST_PASSWORD = "contraseña-de-test"


def _registro(email: str, password: str) -> dict[str, Any]:
    return {"email": email, "password": password, "nombre": "Test"}


def _check(response: httpx.Response, code: int) -> dict[str, Any]:
    assert response.status_code == code, response.text
    return dict(response.json()) if response.content else {}


def authenticate(
    client: httpx.Client, email: str = TEST_EMAIL, password: str = TEST_PASSWORD
) -> str:
    registro = _check(client.post("/auth/register", json=_registro(email, password)), 201)
    codigo = registro["verificacion"]["codigo_dev"]
    _check(client.post("/auth/verify", json={"email": email, "codigo": codigo}), 200)
    sesion = _check(client.post("/auth/login", json={"email": email, "password": password}), 200)
    token = str(sesion["token"])
    client.headers["Authorization"] = f"Bearer {token}"
    return token


async def authenticate_async(
    client: httpx.AsyncClient, email: str = TEST_EMAIL, password: str = TEST_PASSWORD
) -> str:
    response = await client.post("/auth/register", json=_registro(email, password))
    codigo = _check(response, 201)["verificacion"]["codigo_dev"]
    _check(await client.post("/auth/verify", json={"email": email, "codigo": codigo}), 200)
    response = await client.post("/auth/login", json={"email": email, "password": password})
    token = str(_check(response, 200)["token"])
    client.headers["Authorization"] = f"Bearer {token}"
    return token

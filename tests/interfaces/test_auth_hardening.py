"""Revisión de #36 por la API: límites por correo, contrato del 409, demo, brief sin
Content-Length y aviso del modo kit."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.accounts import DEMO_EMAIL
from posiq.interfaces.api.main import create_app
from posiq.interfaces.api.schemas import AVISO_KIT, StudyCreated
from tests.auth_helpers import authenticate_async
from tests.interfaces.test_api import BRIEF, build_runner
from tests.interfaces.test_auth_api import BASE, settings

pytestmark = pytest.mark.anyio


def client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)


async def test_verify_and_resend_share_a_per_email_limit(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings(auth_rate_limit_por_min=3))
    async with client(app) as c:
        malo = {"email": "a@b.es", "codigo": "000000"}
        # Dos rutas (cada una con su propia clave por IP): la clave por correo es común.
        assert (await c.post("/auth/verify", json=malo)).status_code == 400
        assert (await c.post("/auth/verify/reenviar", json={"email": "a@b.es"})).status_code == 202
        assert (await c.post("/auth/verify", json=malo)).status_code == 400
        assert (await c.post("/auth/verify/reenviar", json={"email": "a@b.es"})).status_code == 429
        # Otro correo no está afectado por la clave de a@b.es (sí por la de IP de la ruta).
        r = await c.post("/auth/verify/reenviar", json={"email": "otro@b.es"})
        assert r.status_code == 202


async def test_per_email_limit_holds_across_client_ips(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings(auth_rate_limit_por_min=2))
    codigos = []
    for ip in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
        transport = httpx.ASGITransport(app=app, client=(ip, 1234))
        async with httpx.AsyncClient(transport=transport, base_url=BASE) as c:
            r = await c.post("/auth/login", json={"email": "a@b.es", "password": "x"})
            codigos.append(r.status_code)
    assert codigos == [401, 401, 429]


async def test_resend_is_limited_per_hour_with_429(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings())
    async with client(app) as c:
        await c.post("/auth/register", json={"email": "a@b.es", "password": "12345678"})
        codigos = [
            (await c.post("/auth/verify/reenviar", json={"email": "a@b.es"})).status_code
            for _ in range(4)
        ]
    assert codigos == [202, 202, 202, 429]


async def test_register_keeps_the_409_contract_the_web_uses(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings())
    async with client(app) as c:
        body = {"email": "a@b.es", "password": "12345678"}
        assert (await c.post("/auth/register", json=body)).status_code == 201
        r = await c.post("/auth/register", json=body)
    assert r.status_code == 409 and r.json() == {"detail": "correo_ya_registrado"}


async def test_demo_account_is_refused_outside_demo_mode(repo: SqlStudyRepo) -> None:
    real = settings(llm_provider="deepseek", auth_dev_codes=None)
    app = create_app(runner=build_runner(repo), settings=real)
    async with client(app) as c:
        body = {"email": DEMO_EMAIL, "password": "posiq-demo-alborada"}
        r = await c.post("/auth/register", json=body)
        assert r.status_code == 403 and r.json() == {"detail": "cuenta_demo_desactivada"}
        r = await c.post("/auth/login", json=body)
        assert r.status_code == 403 and r.json() == {"detail": "cuenta_demo_desactivada"}


async def chunked(texto: str) -> AsyncIterator[bytes]:
    data = texto.encode()
    for i in range(0, len(data), 256):
        yield data[i : i + 256]


async def test_brief_size_is_limited_without_content_length(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings(brief_max_bytes=1000))
    async with client(app) as c:
        await authenticate_async(c, email="ana@b.es")
        md = {"content-type": "text/markdown"}
        r = await c.post(
            "/studies", content=chunked(BRIEF + "x" * 5000), headers=md, params={"modo": "kit"}
        )
        assert r.request.headers.get("content-length") is None
        assert r.request.headers.get("transfer-encoding") == "chunked"
        assert r.status_code == 413
        json_h = {"content-type": "application/json"}
        grande = '{"brief_texto": "' + "x" * 5000 + '", "modo": "kit"}'
        assert (
            await c.post("/studies", content=chunked(grande), headers=json_h)
        ).status_code == 413
        r = await c.post("/studies", content=chunked(BRIEF), headers=md, params={"modo": "kit"})
        assert r.status_code == 201, r.text


async def test_kit_creation_warns_that_the_data_is_alborada(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings())
    async with client(app) as c:
        await authenticate_async(c, email="ana@b.es")
        r = await c.post("/studies", json={"brief_texto": "# Otra marca", "modo": "kit"})
    assert r.status_code == 201
    body = r.json()
    assert body["aviso"] == AVISO_KIT
    assert "Alborada" in AVISO_KIT and "no cambia las mediciones" in AVISO_KIT
    # El campo es aditivo: en real es null y `study_id` sigue igual.
    assert StudyCreated(study_id="s").aviso is None
    assert set(body) == {"study_id", "aviso"}

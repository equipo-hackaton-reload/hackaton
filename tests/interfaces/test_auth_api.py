"""Cuentas y propiedad por la API: registro → verificación → login → mis estudios → 404 ajenos."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.deps import new_study
from posiq.interfaces.api.main import create_app
from tests.application.fakes import kit_settings
from tests.auth_helpers import authenticate_async
from tests.interfaces.test_api import BRIEF, build_runner, completed_study, create

pytestmark = pytest.mark.anyio

BASE = "http://test"


def settings(**kw: Any) -> Any:
    return kit_settings(**{"auth_dev_codes": True, "auth_scrypt_n": 2**10, **kw})


@pytest.fixture
def app(repo: SqlStudyRepo) -> Any:
    return create_app(runner=build_runner(repo), settings=settings())


@pytest.fixture
async def anon(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as c:
        yield c


async def client_for(app: Any, email: str) -> httpx.AsyncClient:
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)
    await authenticate_async(c, email=email)
    return c


async def test_register_verify_login_me_and_logout(anon: httpx.AsyncClient) -> None:
    body = {"email": "Ana@Ejemplo.ES", "password": "12345678", "nombre": "Ana"}
    response = await anon.post("/auth/register", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    user = data["user"]
    assert user["email"] == "ana@ejemplo.es" and user["nombre"] == "Ana"
    assert user["verificado"] is False and user["id"]
    assert set(user) == {"id", "email", "nombre", "verificado"}
    assert data["verificacion"]["enviado"] is True
    codigo = data["verificacion"]["codigo_dev"]
    assert len(codigo) == 6 and codigo.isdigit()

    assert (await anon.post("/auth/register", json=body)).status_code == 409

    login = {"email": "ana@ejemplo.es", "password": "12345678"}
    response = await anon.post("/auth/login", json=login)
    assert response.status_code == 403 and response.json() == {"detail": "correo_no_verificado"}

    response = await anon.post("/auth/verify", json={"email": "ANA@ejemplo.es", "codigo": codigo})
    assert response.status_code == 200, response.text
    assert response.json()["user"]["verificado"] is True

    response = await anon.post("/auth/login", json=login)
    assert response.status_code == 200, response.text
    sesion = response.json()
    assert sesion["user"]["email"] == "ana@ejemplo.es" and sesion["expira_en"]
    headers = {"Authorization": f"Bearer {sesion['token']}"}

    me = await anon.get("/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["user"]["id"] == user["id"]

    assert (await anon.post("/auth/logout", headers=headers)).status_code == 204
    assert (await anon.get("/auth/me", headers=headers)).status_code == 401
    assert (await anon.get("/studies", headers=headers)).status_code == 401


async def test_bad_credentials_share_the_same_message(anon: httpx.AsyncClient) -> None:
    await authenticate_async(anon, email="a@b.es")
    mala = await anon.post("/auth/login", json={"email": "a@b.es", "password": "incorrecta"})
    nadie = await anon.post("/auth/login", json={"email": "x@b.es", "password": "incorrecta"})
    assert mala.status_code == nadie.status_code == 401
    assert mala.json() == nadie.json() == {"detail": "credenciales_invalidas"}


async def test_register_validates_password_and_email(anon: httpx.AsyncClient) -> None:
    corta = await anon.post("/auth/register", json={"email": "a@b.es", "password": "1234567"})
    assert corta.status_code == 422
    sin_arroba = await anon.post("/auth/register", json={"email": "ab.es", "password": "12345678"})
    assert sin_arroba.status_code == 422


async def test_verify_attempts_then_429_and_resend(anon: httpx.AsyncClient) -> None:
    registro = await anon.post("/auth/register", json={"email": "a@b.es", "password": "12345678"})
    codigo = registro.json()["verificacion"]["codigo_dev"]
    malo = "000000" if codigo != "000000" else "111111"
    for _ in range(5):
        r = await anon.post("/auth/verify", json={"email": "a@b.es", "codigo": malo})
        assert r.status_code == 400
    r = await anon.post("/auth/verify", json={"email": "a@b.es", "codigo": codigo})
    assert r.status_code == 429

    reenvio = await anon.post("/auth/verify/reenviar", json={"email": "a@b.es"})
    assert reenvio.status_code == 202
    nuevo = reenvio.json()["codigo_dev"]
    r = await anon.post("/auth/verify", json={"email": "a@b.es", "codigo": nuevo})
    assert r.status_code == 200
    # Para un correo desconocido también 202, sin revelar nada.
    desconocido = await anon.post("/auth/verify/reenviar", json={"email": "nadie@b.es"})
    assert desconocido.status_code == 202 and "codigo_dev" not in desconocido.json()
    assert (
        await anon.post("/auth/verify", json={"email": "a@b.es", "codigo": "12345"})
    ).status_code == 422


async def test_without_dev_codes_the_code_is_not_returned(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings(auth_dev_codes=False))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/auth/register", json={"email": "a@b.es", "password": "12345678"})
    assert r.status_code == 201 and r.json()["verificacion"] == {"enviado": True}


async def test_login_is_rate_limited(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings(auth_rate_limit_por_min=3))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as c:
        codes = [
            (await c.post("/auth/login", json={"email": "a@b.es", "password": "x"})).status_code
            for _ in range(4)
        ]
    assert codes == [401, 401, 401, 429]


async def test_another_ip_cannot_lock_the_owner_out_of_login(repo: SqlStudyRepo) -> None:
    """El cupo de un correo se cuenta por IP: un atacante agota el suyo, no el del dueño."""
    app = create_app(runner=build_runner(repo), settings=settings(auth_rate_limit_por_min=3))
    atacante = httpx.ASGITransport(app=app, client=("6.6.6.6", 1))
    dueno = httpx.ASGITransport(app=app, client=("2.2.2.2", 1))
    login = {"email": "a@b.es", "password": "x"}
    async with httpx.AsyncClient(transport=atacante, base_url=BASE) as c:
        codes = [(await c.post("/auth/login", json=login)).status_code for _ in range(6)]
    assert codes == [401, 401, 401, 429, 429, 429]
    async with httpx.AsyncClient(transport=dueno, base_url=BASE) as c:
        assert (await c.post("/auth/login", json=login)).status_code == 401


async def test_rejected_requests_do_not_store_per_email_keys(repo: SqlStudyRepo) -> None:
    """Rechazada por la clave de IP, la petición no crea claves por correo (memoria acotada)."""
    app = create_app(runner=build_runner(repo), settings=settings(auth_rate_limit_por_min=3))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as c:
        for n in range(20):
            await c.post("/auth/login", json={"email": f"u{n}@b.es", "password": "x"})
    accounts = app.state.accounts
    assert len(accounts.limiter_correo) == 3
    assert len(accounts.limiter) == 1 + 3  # la clave de IP y ruta y 3 de IP y correo


async def test_every_protected_route_needs_a_token(anon: httpx.AsyncClient) -> None:
    assert (await anon.get("/health")).status_code == 200
    rutas = [
        ("GET", "/studies"),
        ("POST", "/studies"),
        ("GET", "/studies/x"),
        ("POST", "/studies/x/resume"),
        ("POST", "/studies/x/remeasure"),
        ("GET", "/studies/x/evaluations"),
        ("GET", "/studies/x/traces"),
        ("GET", "/studies/x/export"),
        ("GET", "/estimate?modo=kit"),
        ("GET", "/auth/me"),
        ("POST", "/auth/logout"),
    ]
    for metodo, ruta in rutas:
        response = await anon.request(metodo, ruta, json={})
        assert response.status_code == 401, (metodo, ruta, response.text)
        assert response.headers["www-authenticate"] == "Bearer"
    malo = {"Authorization": "Bearer no-es-un-token"}
    assert (await anon.get("/studies", headers=malo)).status_code == 401
    assert (await anon.get("/studies", headers={"Authorization": "Basic abc"})).status_code == 401


async def test_each_user_only_sees_their_own_studies(app: Any) -> None:
    ana = await client_for(app, "ana@b.es")
    luis = await client_for(app, "luis@b.es")
    try:
        sid = await completed_study(ana)
        otro = await create(luis)

        assert [s["id"] for s in (await ana.get("/studies")).json()] == [sid]
        assert [s["id"] for s in (await luis.get("/studies")).json()] == [otro]

        for metodo, ruta, body in [
            ("GET", f"/studies/{sid}", None),
            ("POST", f"/studies/{sid}/resume", {"revision": "plan", "payload": None}),
            ("POST", f"/studies/{sid}/remeasure", None),
            ("GET", f"/studies/{sid}/evaluations?ids=a", None),
            ("GET", f"/studies/{sid}/traces", None),
            ("GET", f"/studies/{sid}/export", None),
        ]:
            response = await luis.request(metodo, ruta, json=body)
            assert response.status_code == 404, (ruta, response.text)
            assert response.json()["detail"] == f"no existe el estudio {sid}"
        assert (await ana.get(f"/studies/{sid}/export")).status_code == 200

        # La re-medición hereda el propietario del original.
        nuevo = (await ana.post(f"/studies/{sid}/remeasure")).json()["study_id"]
        assert {s["id"] for s in (await ana.get("/studies")).json()} == {sid, nuevo}
        assert (await luis.get(f"/studies/{nuevo}")).status_code == 404
    finally:
        await ana.aclose()
        await luis.aclose()


async def test_legacy_studies_are_hidden_unless_demo_user(repo: SqlStudyRepo) -> None:
    antiguo = new_study("kit")
    repo.save_study(antiguo)  # estudio de una base anterior a las cuentas: sin propietario
    app = create_app(
        runner=build_runner(repo), settings=settings(auth_demo_user="demo@posiq.local")
    )
    demo = await client_for(app, "demo@posiq.local")
    ana = await client_for(app, "ana@b.es")
    try:
        assert [s["id"] for s in (await demo.get("/studies")).json()] == [antiguo.id]
        assert (await demo.get(f"/studies/{antiguo.id}/traces")).status_code == 200
        assert (await ana.get("/studies")).json() == []
        assert (await ana.get(f"/studies/{antiguo.id}")).status_code == 404
    finally:
        await demo.aclose()
        await ana.aclose()


async def test_json_posts_require_json_content_type(app: Any) -> None:
    c = await client_for(app, "ana@b.es")
    try:
        sid = await create(c)
        texto = {"content-type": "text/plain"}
        body = b'{"revision": "competidores", "payload": {"aprobado": true}}'
        r = await c.post(f"/studies/{sid}/resume", content=body, headers=texto)
        assert r.status_code == 415
        r = await c.post(
            "/auth/login", content=b'{"email": "a@b.es", "password": "x"}', headers=texto
        )
        assert r.status_code == 415
    finally:
        await c.aclose()


async def test_brief_size_is_limited(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=settings(brief_max_bytes=1000))
    c = await client_for(app, "ana@b.es")
    try:
        grande = BRIEF + "x" * 1000
        assert (
            await c.post("/studies", json={"brief_texto": grande, "modo": "kit"})
        ).status_code == 413
        r = await c.post(
            "/studies",
            content=grande.encode(),
            headers={"content-type": "text/markdown"},
            params={"modo": "kit"},
        )
        assert r.status_code == 413
        r = await c.post(
            "/studies", files={"fichero": ("b.md", grande, "text/markdown")}, data={"modo": "kit"}
        )
        assert r.status_code == 413
        assert (await c.post("/studies", json={"brief_texto": BRIEF})).status_code == 201
    finally:
        await c.aclose()

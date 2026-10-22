"""API de seguimiento (A2): marcas, serie temporal y re-medición con coste confirmado, modo kit."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.interfaces.api.main import create_app
from tests.auth_helpers import authenticate_async
from tests.interfaces.test_api import api_settings, build_runner, completed_study, create

pytestmark = pytest.mark.anyio

FOCO = "clinica-alborada-vision"
BASE = "http://test"


async def client_for(app: Any, email: str) -> httpx.AsyncClient:
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)
    await authenticate_async(c, email=email)
    return c


@pytest.fixture
async def client(repo: SqlStudyRepo) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(runner=build_runner(repo), settings=api_settings())
    c = await client_for(app, "ana@b.es")
    yield c
    await c.aclose()


async def test_brands_and_series_follow_the_measurements(client: httpx.AsyncClient) -> None:
    assert (await client.get("/brands")).json() == []
    # En revisión de competidores ya tiene marca: aparece, pero sin mediciones completadas.
    pendiente = await create(client)
    [marca] = (await client.get("/brands")).json()
    assert (marca["brand_id"], marca["n_mediciones"], marca["ultima_medicion"]) == (FOCO, 0, None)
    assert (await client.get(f"/brands/{FOCO}/serie")).status_code == 404

    sid = await completed_study(client)
    [marca] = (await client.get("/brands")).json()
    assert (marca["brand_id"], marca["nombre"], marca["n_mediciones"]) == (
        FOCO,
        "Clínica Alborada Visión",
        1,
    )
    assert marca["ultima_medicion"] is not None

    serie = (await client.get(f"/brands/{FOCO}/serie")).json()
    assert [p["study_id"] for p in serie["puntos"]] == [sid]
    assert serie["puntos"][0]["comparable_con_anterior"] is False  # línea base

    # Segunda medición: el kit da las mismas respuestas → comparable y sin cambios.
    nuevo = (await client.post(f"/studies/{sid}/remeasure")).json()["study_id"]
    response = await client.post(
        f"/studies/{nuevo}/resume", json={"revision": "plan", "payload": {"aprobado": True}}
    )
    assert response.status_code == 202, response.text
    assert (await client.get("/brands")).json()[0]["n_mediciones"] == 2

    serie = (await client.get(f"/brands/{FOCO}/serie")).json()
    assert [p["study_id"] for p in serie["puntos"]] == [sid, nuevo]
    assert serie["puntos"][1]["comparable_con_anterior"] is True
    assert serie["cambios_significativos"] == []
    assert any("Sin cambios fuera del margen de error" in r for r in serie["resumen"])
    assert pendiente not in [p["study_id"] for p in serie["puntos"]]


async def test_brands_and_series_are_private_to_each_user(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=api_settings())
    ana, luis = await client_for(app, "ana@b.es"), await client_for(app, "luis@b.es")
    try:
        await completed_study(ana)
        assert [m["brand_id"] for m in (await ana.get("/brands")).json()] == [FOCO]
        assert (await luis.get("/brands")).json() == []
        assert (await luis.get(f"/brands/{FOCO}/serie")).status_code == 404
    finally:
        await ana.aclose()
        await luis.aclose()


async def test_kit_remeasure_is_free_and_needs_no_confirmation(client: httpx.AsyncClient) -> None:
    sid = await completed_study(client)
    estimate = (await client.get(f"/studies/{sid}/remeasure/estimate")).json()
    assert estimate["coste_estimado_eur"] == 0 and estimate["llamadas"] > 0
    assert (await client.post(f"/studies/{sid}/remeasure")).status_code == 201


async def test_paid_remeasure_requires_a_matching_confirmation(repo: SqlStudyRepo) -> None:
    # KIT_IA_REAL con clave: la re-medición cuesta (LLM y juez de pago), aunque el runner del test
    # use dobles sin red. La API no debe gastar sin una confirmación que cubra la estimación.
    settings = api_settings().model_copy(
        update={"kit_ia_real": True, "deepseek_api_key": SecretStr("k")}
    )
    app = create_app(runner=build_runner(repo), settings=settings)
    c = await client_for(app, "ana@b.es")
    try:
        sid = await completed_study(c)
        coste = (await c.get(f"/studies/{sid}/remeasure/estimate")).json()["coste_estimado_eur"]
        assert coste > 0

        sin = await c.post(f"/studies/{sid}/remeasure")
        assert sin.status_code == 409 and "confirma" in sin.json()["detail"]
        corta = await c.post(
            f"/studies/{sid}/remeasure", json={"confirmado": True, "coste_estimado_eur": coste / 2}
        )
        assert corta.status_code == 409 and "ha subido" in corta.json()["detail"]
        falso = await c.post(
            f"/studies/{sid}/remeasure", json={"confirmado": False, "coste_estimado_eur": coste}
        )
        assert falso.status_code == 422

        ok = await c.post(
            f"/studies/{sid}/remeasure", json={"confirmado": True, "coste_estimado_eur": coste}
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["remedicion_de"] == sid
    finally:
        await c.aclose()


async def test_remeasure_estimate_of_someone_elses_study_is_404(repo: SqlStudyRepo) -> None:
    app = create_app(runner=build_runner(repo), settings=api_settings())
    ana, luis = await client_for(app, "ana@b.es"), await client_for(app, "luis@b.es")
    try:
        sid = await completed_study(ana)
        assert (await luis.get(f"/studies/{sid}/remeasure/estimate")).status_code == 404
    finally:
        await ana.aclose()
        await luis.aclose()

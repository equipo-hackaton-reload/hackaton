"""Configuración versionada en la API: perfil y mercado por marca, re-medición con la vigente y
estado de las acciones (modo kit, LLM falso, juez por detección).

Cada usuario ve solo sus marcas: lo ajeno responde 404, como los estudios (ADR 0015).
"""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.interfaces.api.main import create_app
from tests.auth_helpers import authenticate_async
from tests.interfaces.test_api import CONFIRMA, api_settings, build_runner, completed_study

pytestmark = pytest.mark.anyio

BASE = "http://test"


@pytest.fixture
def app(repo: SqlStudyRepo) -> Any:
    return create_app(runner=build_runner(repo), settings=api_settings())


async def client_for(app: Any, email: str) -> httpx.AsyncClient:
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)
    await authenticate_async(c, email=email)
    return c


@pytest.fixture
async def ana(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    c = await client_for(app, "ana@b.es")
    yield c
    await c.aclose()


@pytest.fixture
async def luis(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    c = await client_for(app, "luis@b.es")
    yield c
    await c.aclose()


async def brand_of(client: httpx.AsyncClient, sid: str) -> str:
    return str((await client.get(f"/studies/{sid}")).json()["study"]["brand_id"])


async def remeasure(client: httpx.AsyncClient, sid: str) -> str:
    """Re-mide `sid` con el coste confirmado y aprueba el plan: estudio nuevo completado."""
    estimate = (await client.get(f"/studies/{sid}/remeasure/estimate")).json()
    body = {"confirmado": True, "coste_estimado_eur": estimate["coste_estimado_eur"]}
    response = await client.post(f"/studies/{sid}/remeasure", json=body)
    assert response.status_code == 201, response.text
    nuevo = str(response.json()["study_id"])
    response = await client.post(
        f"/studies/{nuevo}/resume", json={"revision": "plan", "payload": {"aprobado": True}}
    )
    assert response.status_code == 202, response.text
    assert (await client.get(f"/studies/{nuevo}")).json()["estado"] == "completado"
    return nuevo


async def test_remeasure_saves_the_config_versions(ana: httpx.AsyncClient) -> None:
    original = await completed_study(ana)
    vista = (await ana.get(f"/studies/{original}")).json()
    assert vista["datos_sinteticos"] is True and vista["configuracion"] is None

    nuevo = await remeasure(ana, original)
    vista = (await ana.get(f"/studies/{nuevo}")).json()
    assert vista["datos_sinteticos"] is True
    assert vista["configuracion"] == {
        "version_perfil": "v1",
        "version_mercado": "v1",
        "remedicion_de": original,
    }


async def test_a_second_remeasure_in_progress_is_409(ana: httpx.AsyncClient) -> None:
    original = await completed_study(ana)
    response = await ana.post(f"/studies/{original}/remeasure", json=CONFIRMA)
    assert response.status_code == 201, response.text
    nuevo = response.json()["study_id"]

    # La primera re-medición espera la revisión del plan: una segunda del mismo estudio es 409.
    response = await ana.post(f"/studies/{original}/remeasure", json=CONFIRMA)
    assert response.status_code == 409 and "en curso" in response.json()["detail"]
    await ana.post(
        f"/studies/{nuevo}/resume", json={"revision": "plan", "payload": {"aprobado": True}}
    )
    response = await ana.post(f"/studies/{original}/remeasure", json=CONFIRMA)
    assert response.status_code == 201, response.text


async def test_profile_versions_and_remeasure_with_the_current_one(
    ana: httpx.AsyncClient,
) -> None:
    original = await completed_study(ana)
    marca = await brand_of(ana, original)
    brief = (await ana.get(f"/studies/{original}")).json()["brief"]

    v1 = (await ana.get(f"/brands/{marca}/perfil")).json()
    assert v1["version"] == "v1"
    assert v1["perfil"]["ciudades"] == brief["ciudades"]
    assert v1["perfil"]["servicios"] == brief["servicios_prioritarios"]

    perfil = {**v1["perfil"], "ciudades": [*v1["perfil"]["ciudades"], "Bilbao"]}
    response = await ana.put(f"/brands/{marca}/perfil", json={"perfil": perfil})
    assert response.status_code == 201, response.text
    creada = response.json()
    assert creada["version"] == "v2" and creada["vigente_desde"] > v1["vigente_desde"]
    avisos = " ".join(creada["aviso_impacto"])
    assert "Añades ciudades (Bilbao)" in avisos and "núcleo común" in avisos
    assert "Caso sintético" in avisos

    perfil_identidad = {**perfil, "posicionamiento_deseado": "Referente en cirugía refractiva"}
    response = await ana.put(f"/brands/{marca}/perfil", json={"perfil": perfil_identidad})
    assert any("no afectan al score" in a for a in response.json()["aviso_impacto"])

    historial = (await ana.get(f"/brands/{marca}/perfil", params={"historial": 1})).json()
    assert [v["version"] for v in historial] == ["v1", "v2", "v3"]
    assert historial[0] == v1  # nunca se sobrescribe
    assert (await ana.get(f"/brands/{marca}/perfil")).json()["version"] == "v3"

    nuevo = await remeasure(ana, original)
    vista = (await ana.get(f"/studies/{nuevo}")).json()
    assert vista["configuracion"]["version_perfil"] == "v3"
    assert "Bilbao" in vista["brief"]["ciudades"]
    assert vista["brief"]["posicionamiento_deseado"] == "Referente en cirugía refractiva"


async def test_market_versions_and_their_effect_on_the_series(ana: httpx.AsyncClient) -> None:
    original = await completed_study(ana)
    marca = await brand_of(ana, original)

    v1 = (await ana.get(f"/brands/{marca}/mercado")).json()
    assert v1["version"] == "v1" and marca in {b["id"] for b in v1["marcas"]}
    sin_foco = [b for b in v1["marcas"] if b["id"] != marca]
    response = await ana.put(f"/brands/{marca}/mercado", json={"marcas": sin_foco})
    assert response.status_code == 422

    sale = next(b for b in v1["marcas"] if b["id"] != marca)
    marcas = [b for b in v1["marcas"] if b["id"] != sale["id"]]
    response = await ana.put(f"/brands/{marca}/mercado", json={"marcas": marcas})
    assert response.status_code == 201, response.text
    creada = response.json()
    assert creada["version"] == "v2"
    assert any(
        f"salen {sale['nombre']}" in a and "no se compararán" in a for a in creada["aviso_impacto"]
    )
    historial = (await ana.get(f"/brands/{marca}/mercado", params={"historial": "1"})).json()
    assert [v["version"] for v in historial] == ["v1", "v2"]

    nuevo = await remeasure(ana, original)
    vista = (await ana.get(f"/studies/{nuevo}")).json()
    assert vista["configuracion"]["version_mercado"] == "v2"
    assert sale["id"] not in {b["id"] for b in vista["market"]["marcas"]}


async def test_action_status_with_history(ana: httpx.AsyncClient) -> None:
    sid = await completed_study(ana)
    vista = (await ana.get(f"/studies/{sid}")).json()
    assert vista["acciones_estado"] == {}
    accion = vista["plan"]["fases"][0]["acciones"][0]["id"]

    response = await ana.patch(f"/studies/{sid}/acciones/{accion}", json={"estado": "en_curso"})
    assert response.status_code == 200, response.text
    assert response.json()["estado"] == "en_curso" and response.json()["action_id"] == accion
    body = {"estado": "hecha", "nota": "Publicada la ficha"}
    response = await ana.patch(f"/studies/{sid}/acciones/{accion}", json=body)
    assert response.status_code == 200

    estado = (await ana.get(f"/studies/{sid}")).json()["acciones_estado"]
    assert set(estado) == {accion}
    assert (estado[accion]["estado"], estado[accion]["nota"]) == ("hecha", "Publicada la ficha")
    assert estado[accion]["actualizado_en"]

    malo = {"estado": "terminada"}
    assert (await ana.patch(f"/studies/{sid}/acciones/{accion}", json=malo)).status_code == 422
    ruta = f"/studies/{sid}/acciones/A-no-existe"
    assert (await ana.patch(ruta, json={"estado": "hecha"})).status_code == 404


async def test_brands_are_isolated_between_users(
    ana: httpx.AsyncClient, luis: httpx.AsyncClient
) -> None:
    sid = await completed_study(ana)
    marca = await brand_of(ana, sid)
    accion = (await ana.get(f"/studies/{sid}")).json()["plan"]["fases"][0]["acciones"][0]["id"]
    perfil = (await ana.get(f"/brands/{marca}/perfil")).json()["perfil"]
    await ana.put(f"/brands/{marca}/perfil", json={"perfil": {**perfil, "ciudades": ["Soria"]}})

    assert (await luis.get("/brands")).json() == []
    for metodo, ruta, body in [
        ("GET", f"/brands/{marca}/serie", None),
        ("GET", f"/brands/{marca}/perfil", None),
        ("GET", f"/brands/{marca}/mercado", None),
        ("PUT", f"/brands/{marca}/perfil", {"perfil": perfil}),
        ("GET", f"/studies/{sid}/remeasure/estimate", None),
        ("POST", f"/studies/{sid}/remeasure", CONFIRMA),
        ("PATCH", f"/studies/{sid}/acciones/{accion}", {"estado": "hecha"}),
    ]:
        response = await luis.request(metodo, ruta, json=body)
        assert response.status_code == 404, (ruta, response.text)

    # Luis mide la misma marca: sus versiones y su serie son suyas, no las de Ana.
    suyo = await completed_study(luis)
    assert await brand_of(luis, suyo) == marca
    historial = (await luis.get(f"/brands/{marca}/perfil", params={"historial": 1})).json()
    assert [v["version"] for v in historial] == ["v1"]
    assert "Soria" not in historial[0]["perfil"]["ciudades"]
    serie = (await luis.get(f"/brands/{marca}/serie")).json()
    assert [p["study_id"] for p in serie["puntos"]] == [suyo]
    vista = (await luis.get(f"/studies/{suyo}")).json()
    assert vista["metrics"]["comparado_con"] is None  # no se compara con el estudio de Ana
    assert vista["acciones_estado"] == {}

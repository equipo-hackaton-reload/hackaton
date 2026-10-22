"""Elegir escenario por la API: preajustes, escenario del consultor y propuesta recortada (kit)."""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.interfaces.api.main import create_app
from tests.auth_helpers import authenticate_async
from tests.interfaces.test_api import (
    api_settings,
    approve_competitors,
    build_runner,
    completed_study,
    create,
)

pytestmark = pytest.mark.anyio
APROBAR = {"revision": "plan", "payload": {"aprobado": True}}


@pytest.fixture
async def client(repo: SqlStudyRepo) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(runner=build_runner(repo), settings=api_settings())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        await authenticate_async(c)
        yield c


def acciones(plan: dict[str, Any]) -> list[str]:
    return [a["id"] for f in plan["fases"] for a in f["acciones"]]


async def test_presets_come_with_the_plan_and_completo_is_chosen(
    client: httpx.AsyncClient,
) -> None:
    sid = await create(client)
    view = await approve_competitors(client, sid)
    listed = (await client.get(f"/studies/{sid}/scenarios")).json()
    assert [g["id"] for g in listed] == ["minimo_viable", "equilibrado", "completo"]
    assert [g["id"] for g in listed if g["elegido"]] == ["completo"]
    assert listed == view["escenarios"]


async def test_custom_scenario_chosen_drives_the_proposal(client: httpx.AsyncClient) -> None:
    sid = await create(client)
    plan = (await approve_competitors(client, sid))["plan"]
    todas = acciones(plan)
    assert len(todas) > 1

    # Capacidad 2 puntos y acciones de esfuerzo M (2) en el plan de prueba: solo cabe la primera.
    response = await client.post(f"/studies/{sid}/scenarios", json={"capacidad": 2})
    assert response.status_code == 201, response.text
    p1 = response.json()
    assert p1["id"] == "P1" and p1["escenario"]["mantenidas"] == todas[:1]
    assert {a["motivo"] for a in p1["escenario"]["aplazadas"]} == {"capacidad"}

    elegidos = (await client.post(f"/studies/{sid}/scenarios/P1/elegir")).json()
    assert [g["id"] for g in elegidos if g["elegido"]] == ["P1"]

    # El plan sigue en revisión y se reanuda con normalidad tras escribir los escenarios.
    assert (await client.post(f"/studies/{sid}/resume", json=APROBAR)).status_code == 202
    view = (await client.get(f"/studies/{sid}")).json()
    assert view["estado"] == "completado", view["errores"]
    assert acciones(view["proposal"]["plan"]) == todas[:1]
    assert acciones(view["plan"]) == todas, "el plan aprobado del estudio no cambia"
    nota = view["proposal"]["contexto"]["limitaciones"][0]
    assert nota.startswith(f"Propuesta con el escenario «P1»: 1 de {len(todas)} acciones")

    # Con la propuesta redactada, elegir otro escenario ya no tendría efecto.
    assert (await client.post(f"/studies/{sid}/scenarios/completo/elegir")).status_code == 409


async def test_with_completo_the_proposal_is_unchanged(client: httpx.AsyncClient) -> None:
    sid = await completed_study(client)
    view = (await client.get(f"/studies/{sid}")).json()
    assert view["proposal"]["plan"] == view["plan"]
    limitaciones = view["proposal"]["contexto"]["limitaciones"]
    assert not any(lim.startswith("Propuesta con el escenario") for lim in limitaciones)


async def test_scenario_errors(client: httpx.AsyncClient) -> None:
    sid = await create(client)
    assert (await client.post(f"/studies/{sid}/scenarios", json={})).status_code == 409  # sin plan
    assert (await client.get(f"/studies/{sid}/scenarios")).json() == []

    await approve_competitors(client, sid)
    bad = await client.post(f"/studies/{sid}/scenarios", json={"acciones_activas": ["NOPE"]})
    assert bad.status_code == 422
    assert (
        await client.post(f"/studies/{sid}/scenarios", json={"capacidad": -1})
    ).status_code == 422
    assert (await client.post(f"/studies/{sid}/scenarios/NOPE/elegir")).status_code == 404
    assert (await client.get("/studies/nope/scenarios")).status_code == 404

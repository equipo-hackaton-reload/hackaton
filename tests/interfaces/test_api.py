"""API con `httpx.AsyncClient` sobre la app ASGI, con el grafo en modo kit y LLM y juez falsos.

`ASGITransport` espera a que terminen las tareas en segundo plano antes de devolver la respuesta,
así que tras un `POST` el grafo ya está parado en la siguiente revisión.
"""

import io
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from docx import Document
from langgraph.checkpoint.memory import InMemorySaver

from posiq.adapters.engines.kit import KitEngine
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.graph import serializer
from posiq.application.runner import StudyRunner
from posiq.interfaces.api.main import DOCX, create_app
from tests.application.fakes import KIT_DIR, FakeLLM, kit_llm, make_deps

pytestmark = pytest.mark.anyio

BRIEF = "# Brief\n\n**Marca:** Clínica Alborada Visión"


def build_runner(repo: SqlStudyRepo, llm: FakeLLM | None = None) -> StudyRunner:
    deps = make_deps(llm or kit_llm(), KitEngine.all_motors(KIT_DIR), repo)
    return StudyRunner({"kit": deps}, InMemorySaver(serde=serializer()), repo)


@pytest.fixture
async def client(repo: SqlStudyRepo) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(runner=build_runner(repo))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def create(client: httpx.AsyncClient, **body: Any) -> str:
    response = await client.post("/studies", json={"brief_texto": BRIEF, "modo": "kit", **body})
    assert response.status_code == 201, response.text
    return str(response.json()["study_id"])


async def test_health(client: httpx.AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}


async def test_full_flow_with_both_reviews(client: httpx.AsyncClient) -> None:
    sid = await create(client)

    view = (await client.get(f"/studies/{sid}")).json()
    assert view["estado"] == "esperando_revision_competidores"
    assert view["revision_pendiente"] == "competidores"
    assert view["brief"]["marca"] == "Clínica Alborada Visión"
    assert view["market"]["confirmado_por_humano"] is False
    assert view["metrics"] is None and view["proposal"] is None

    market = view["market"]
    market["marcas"] = market["marcas"][:6]
    response = await client.post(
        f"/studies/{sid}/resume", json={"revision": "competidores", "payload": market}
    )
    assert response.status_code == 202, response.text

    view = (await client.get(f"/studies/{sid}")).json()
    assert view["estado"] == "esperando_revision_plan"
    assert view["revision_pendiente"] == "plan"
    assert view["market"]["confirmado_por_humano"] is True
    assert len(view["market"]["marcas"]) == 6
    assert view["metrics"]["study_id"] == sid
    assert view["findings"] and view["plan"]["study_id"] == sid

    response = await client.post(
        f"/studies/{sid}/resume", json={"revision": "plan", "payload": {"aprobado": True}}
    )
    assert response.status_code == 202

    view = (await client.get(f"/studies/{sid}")).json()
    assert view["estado"] == "completado"
    assert view["revision_pendiente"] == "none"
    assert view["coste_acumulado_eur"] == 0
    assert view["errores"] == []
    assert view["proposal"]["study_id"] == sid

    listed = (await client.get("/studies", params={"brand_id": "clinica-alborada-vision"})).json()
    assert [s["id"] for s in listed] == [sid]
    assert (await client.get("/studies", params={"brand_id": "otra"})).json() == []


async def test_resume_rejects_the_wrong_revision_and_invalid_payloads(
    client: httpx.AsyncClient,
) -> None:
    sid = await create(client)
    wrong = await client.post(f"/studies/{sid}/resume", json={"revision": "plan", "payload": None})
    assert wrong.status_code == 409
    assert "competidores" in wrong.json()["detail"]

    invalid = await client.post(
        f"/studies/{sid}/resume",
        json={"revision": "competidores", "payload": {"marcas": [{"id": "x"}]}},
    )
    assert invalid.status_code == 422

    sin_foco = {"marcas": [{"id": "otra", "nombre": "Otra", "rol": "foco"}]}
    response = await client.post(
        f"/studies/{sid}/resume", json={"revision": "competidores", "payload": sin_foco}
    )
    assert response.status_code == 422
    assert "no está en el mercado" in response.json()["detail"]

    bad_revision = await client.post(f"/studies/{sid}/resume", json={"revision": "otra"})
    assert bad_revision.status_code == 422


async def test_unknown_study_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.get("/studies/nope")).status_code == 404
    assert (await client.post("/studies/nope/resume", json={"revision": "plan"})).status_code == 404
    assert (await client.get("/studies/nope/export")).status_code == 404


async def test_export_requires_completed_proposal(client: httpx.AsyncClient) -> None:
    sid = await create(client)
    response = await client.get(f"/studies/{sid}/export", params={"formato": "pdf"})
    assert response.status_code == 409
    assert "completada" in response.json()["detail"]
    assert (await client.get(f"/studies/{sid}/export?formato=odt")).status_code == 422


async def test_create_validates_the_body(client: httpx.AsyncClient) -> None:
    assert (await client.post("/studies", json={"brief_texto": ""})).status_code == 422
    assert (
        await client.post("/studies", json={"brief_texto": BRIEF, "modo": "otro"})
    ).status_code == 422
    # El modo real no está montado en este runner.
    assert (
        await client.post("/studies", json={"brief_texto": BRIEF, "modo": "real"})
    ).status_code == 422


async def test_create_from_uploaded_markdown_and_docx(
    client: httpx.AsyncClient, repo: SqlStudyRepo
) -> None:
    response = await client.post(
        "/studies",
        params={"modo": "kit", "nombre": "brief.md"},
        content=BRIEF.encode("utf-8"),
        headers={"content-type": "text/markdown"},
    )
    assert response.status_code == 201, response.text

    buffer = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Marca: Clínica Alborada Visión")
    doc.save(buffer)
    response = await client.post(
        "/studies", content=buffer.getvalue(), headers={"content-type": DOCX}
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/studies", content=b"%PDF", headers={"content-type": "application/pdf"}
    )
    assert response.status_code == 415


async def test_graph_failure_is_reported_as_error(repo: SqlStudyRepo) -> None:
    def boom(_: dict[str, Any]) -> Any:
        raise RuntimeError("LLM caído")

    app = create_app(runner=build_runner(repo, FakeLLM({"intake.v1": boom})))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        sid = await create(c)
        view = (await c.get(f"/studies/{sid}")).json()
    assert view["estado"] == "error"
    assert any("LLM caído" in e for e in view["errores"])


async def test_cors_allows_localhost(client: httpx.AsyncClient) -> None:
    response = await client.options(
        "/studies",
        headers={
            "origin": "http://localhost:5173",
            "access-control-request-method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

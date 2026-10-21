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
from tests.application.fakes import KIT_DIR, FakeLLM, kit_llm, kit_settings, make_deps

pytestmark = pytest.mark.anyio

BRIEF = "# Brief\n\n**Marca:** Clínica Alborada Visión"


def build_runner(repo: SqlStudyRepo, llm: FakeLLM | None = None) -> StudyRunner:
    deps = make_deps(llm or kit_llm(), KitEngine.all_motors(KIT_DIR), repo)
    return StudyRunner({"kit": deps}, InMemorySaver(serde=serializer()), repo)


@pytest.fixture
async def client(repo: SqlStudyRepo) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(runner=build_runner(repo), settings=kit_settings())
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
    assert view["simulacion"]["study_id"] == sid
    assert len(view["simulacion"]["proyecciones"]) == len(view["plan"]["fases"])
    assert view["calidad_plan"] is None

    response = await client.post(
        f"/studies/{sid}/resume", json={"revision": "plan", "payload": {"aprobado": True}}
    )
    assert response.status_code == 202

    view = (await client.get(f"/studies/{sid}")).json()
    assert view["estado"] == "completado"
    assert view["revision_pendiente"] is None
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
    assert response.json()["detail"] == "la propuesta aún no está completada"
    assert (await client.get(f"/studies/{sid}/export?formato=odt")).status_code == 422


async def approve_competitors(client: httpx.AsyncClient, sid: str) -> dict[str, Any]:
    response = await client.post(
        f"/studies/{sid}/resume", json={"revision": "competidores", "payload": {"aprobado": True}}
    )
    assert response.status_code == 202, response.text
    return dict((await client.get(f"/studies/{sid}")).json())


async def completed_study(client: httpx.AsyncClient) -> str:
    sid = await create(client)
    await approve_competitors(client, sid)
    response = await client.post(
        f"/studies/{sid}/resume", json={"revision": "plan", "payload": {"aprobado": True}}
    )
    assert response.status_code == 202, response.text
    assert (await client.get(f"/studies/{sid}")).json()["estado"] == "completado"
    return sid


async def test_remeasure_reuses_the_confirmed_market_and_compares(
    client: httpx.AsyncClient,
) -> None:
    original = await completed_study(client)
    before = (await client.get(f"/studies/{original}")).json()

    response = await client.post(f"/studies/{original}/remeasure")
    assert response.status_code == 201, response.text
    body = response.json()
    nuevo = body["study_id"]
    assert nuevo != original and body["remedicion_de"] == original

    view = (await client.get(f"/studies/{nuevo}")).json()
    # Sin repetir intake ni la revisión de competidores: va directo a la revisión del plan.
    assert view["estado"] == "esperando_revision_plan", view["errores"]
    assert view["market"] == before["market"]
    assert view["brief"] == before["brief"]
    assert view["metrics"]["comparado_con"] == original
    delta = view["metrics_delta"]
    assert delta["comparado_con"] == original and delta["study_id"] == nuevo
    # El kit da las mismas respuestas: la re-medición mide repetibilidad, no una mejora.
    assert delta["score_delta"] == 0
    nodos = {t["nodo"] for t in (await client.get(f"/studies/{nuevo}/traces")).json()}
    assert "intake.v1" not in nodos and "market.v1" not in nodos

    response = await client.post(
        f"/studies/{nuevo}/resume", json={"revision": "plan", "payload": {"aprobado": True}}
    )
    assert response.status_code == 202
    assert (await client.get(f"/studies/{nuevo}")).json()["estado"] == "completado"

    marca = before["study"]["brand_id"]
    listed = (await client.get("/studies", params={"brand_id": marca})).json()
    assert [s["id"] for s in listed] == [nuevo, original]


async def test_remeasure_requires_a_completed_study(client: httpx.AsyncClient) -> None:
    sid = await create(client)
    response = await client.post(f"/studies/{sid}/remeasure")
    assert response.status_code == 409
    assert "completado" in response.json()["detail"]
    assert (await client.post("/studies/nope/remeasure")).status_code == 404


async def test_first_measurement_has_no_delta(client: httpx.AsyncClient) -> None:
    sid = await create(client)
    view = await approve_competitors(client, sid)
    assert view["metrics"]["comparado_con"] is None
    assert view["metrics_delta"] is None


async def test_editing_the_plan_recomputes_the_simulation(client: httpx.AsyncClient) -> None:
    sid = await create(client)
    view = await approve_competitors(client, sid)
    plan = view["plan"]
    assert [p["fase"] for p in view["simulacion"]["proyecciones"]] == ["Fase 1"]
    fase = plan["fases"][0]
    segunda = {
        **fase,
        "nombre": "Fase 2",
        "acciones": [{**a, "id": f"{a['id']}-bis"} for a in fase["acciones"]],
    }
    editado = {**plan, "fases": [fase, segunda]}

    response = await client.post(
        f"/studies/{sid}/resume", json={"revision": "plan", "payload": editado}
    )
    assert response.status_code == 202, response.text

    view = (await client.get(f"/studies/{sid}")).json()
    assert view["estado"] == "completado", view["errores"]
    assert [p["fase"] for p in view["simulacion"]["proyecciones"]] == ["Fase 1", "Fase 2"]


async def test_traces_lists_the_traces_of_the_study(client: httpx.AsyncClient) -> None:
    sid = await create(client)
    traces = (await client.get(f"/studies/{sid}/traces")).json()
    assert {t["study_id"] for t in traces} == {sid}
    assert {"intake.v1", "market.v1"} <= {t["nodo"] for t in traces}

    view = await approve_competitors(client, sid)
    after = (await client.get(f"/studies/{sid}/traces")).json()
    assert len(after) > len(traces)
    assert sum(t["coste_eur"] for t in after) == view["coste_acumulado_eur"]


async def test_evaluations_returns_evidence_in_the_requested_order(
    client: httpx.AsyncClient,
) -> None:
    sid = await create(client)
    before = await client.get(f"/studies/{sid}/evaluations", params={"ids": "x"})
    assert before.status_code == 200 and before.json() == []

    view = await approve_competitors(client, sid)
    ids = list(reversed(view["findings"][0]["evaluation_ids"][:3]))
    response = await client.get(
        f"/studies/{sid}/evaluations", params={"ids": ",".join([*ids, "no-existe"])}
    )
    assert response.status_code == 200, response.text
    evidence = response.json()
    assert [e["evaluation"]["id"] for e in evidence] == ids
    first = evidence[0]
    assert first["motor"] in {"ChatGPT", "Gemini", "Perplexity", "Claude"}
    assert first["prompt"] and first["texto_respuesta"]
    assert len(first["texto_respuesta"]) <= 2000
    assert all(isinstance(f, str) for f in first["fuentes"])
    assert (await client.get(f"/studies/{sid}/evaluations")).json() == []


async def test_estimate_kit_is_free_and_real_prices_the_engines(
    client: httpx.AsyncClient,
) -> None:
    kit = (await client.get("/estimate", params={"modo": "kit"})).json()
    assert kit["llamadas"] == 624
    assert kit["coste_estimado_eur"] == 0
    assert kit["presupuesto_max_eur"] == 5.0

    real = (await client.get("/estimate", params={"modo": "real"})).json()
    assert real["llamadas"] == 624 and real["coste_estimado_eur"] > 0

    small = await client.get(
        "/estimate", params={"modo": "real", "n_prompts": 10, "n_motores": 2, "repeticiones": 1}
    )
    assert small.json()["llamadas"] == 20
    assert small.json()["coste_estimado_eur"] < real["coste_estimado_eur"]

    assert (
        await client.get("/estimate", params={"modo": "real", "n_prompts": 0})
    ).status_code == 422
    assert (await client.get("/estimate", params={"modo": "otro"})).status_code == 422


async def test_web_endpoints_of_an_unknown_study_are_404(client: httpx.AsyncClient) -> None:
    for path in ("/studies/nope/traces", "/studies/nope/evaluations?ids=a"):
        response = await client.get(path)
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]


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

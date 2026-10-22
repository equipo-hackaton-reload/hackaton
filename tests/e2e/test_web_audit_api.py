"""Auditoría técnica de la web (ADR 0019) en la demo: API, `LLM_PROVIDER=fixture`, modo kit y
`WEB_AUDIT=fixture` (`FixtureWebFetcher`, CASO SINTÉTICO, sin red).

La auditoría sale en `GET /studies/{id}` como ejemplo (`origen="fixture"`) y sus hallazgos viajan
aparte (`hallazgos_web`): las cifras canónicas no cambian (25,93; 8.ª de 10; 25,9 → 30,8; 7
hallazgos; 9 acciones). Con la auditoría apagada (por defecto) `auditoria_web` es null: lo
comprueba `test_diferencial_api.py`.
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from posiq.interfaces.api.main import create_app
from posiq.settings import Settings
from tests.auth_helpers import authenticate

ROOT = Path(__file__).resolve().parents[2]
BRIEF = ROOT / "data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md"
FOCO = "clinica-alborada-vision"


@pytest.fixture(scope="module")
def estudio(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], list[Any]]:
    db = tmp_path_factory.mktemp("web_audit") / "study.db"
    settings = Settings(
        _env_file=None,
        llm_provider="fixture",
        database_url=f"sqlite:///{db.as_posix()}",
        cache_enabled=False,
        web_audit="real",  # en modo kit se degrada a fixture: nada del kit es real
    )
    with TestClient(create_app(settings=settings)) as client:
        authenticate(client)
        response = client.post(
            "/studies", json={"brief_texto": BRIEF.read_text(encoding="utf-8"), "modo": "kit"}
        )
        assert response.status_code == 201, response.text
        sid = response.json()["study_id"]
        for revision in ("competidores", "plan"):
            response = client.post(
                f"/studies/{sid}/resume", json={"revision": revision, "payload": {"aprobado": True}}
            )
            assert response.status_code == 202, response.text
        view: dict[str, Any] = client.get(f"/studies/{sid}").json()
        traces: list[Any] = client.get(f"/studies/{sid}/traces").json()
    assert view["estado"] == "completado", view["errores"]
    return view, traces


def test_cifras_canonicas_intactas_con_la_auditoria(
    estudio: tuple[dict[str, Any], list[Any]],
) -> None:
    view, _ = estudio
    assert view["metrics"]["score_global"]["score"] == 25.93
    assert view["metrics"]["ranking"].index(FOCO) + 1 == 8
    assert len(view["metrics"]["ranking"]) == 10
    final = view["simulacion"]["proyecciones"][-1]["score"]
    assert (round(view["simulacion"]["score_actual"], 1), round(final["esperado"], 1)) == (
        25.9,
        30.8,
    )
    assert len(view["findings"]) == 7
    assert not [f for f in view["findings"] if f["id"].startswith("F-web-")]
    acciones = [a for fase in view["plan"]["fases"] for a in fase["acciones"]]
    assert len(acciones) == 9
    assert not [a for a in acciones if a["palanca"] == "tecnico"]


def test_auditoria_de_ejemplo_en_la_vista(estudio: tuple[dict[str, Any], list[Any]]) -> None:
    view, _ = estudio
    auditoria = view["auditoria_web"]
    assert auditoria["origen"] == "fixture" and auditoria["fetcher"] == "fixture"
    assert auditoria["dominio"] == "alboradavision.example"
    assert auditoria["brand_id"] == FOCO and auditoria["study_id"] == view["study"]["id"]
    assert auditoria["puntuacion"] is not None
    assert {b["bloque"] for b in auditoria["bloques"]} == {
        "descubrimiento",
        "contenido",
        "acceso_bots",
        "agentes_api",
        "rendimiento",
    }
    gptbot = next(a for a in auditoria["accesos_bots"] if a["bot"] == "GPTBot")
    assert gptbot["permitido"] is False and gptbot["motor"] == "ChatGPT"
    hallazgos = view["hallazgos_web"]
    assert "F-web-bots-bloqueados" in {f["id"] for f in hallazgos}
    assert auditoria["finding_ids"] == [f["id"] for f in hallazgos]


def test_trazas_http_sin_coste(estudio: tuple[dict[str, Any], list[Any]]) -> None:
    view, traces = estudio
    web = [t for t in traces if t["nodo"] == "web_audit"]
    assert len(web) == len(view["auditoria_web"]["recursos"])
    assert {(t["modelo"], t["prompt_version"]) for t in web} == {("http:fixture", "web_audit.v1")}
    assert all(t["coste_eur"] == 0 and t["tokens_in"] == t["tokens_out"] == 0 for t in web)

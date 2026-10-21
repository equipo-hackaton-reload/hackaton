"""El diferencial de la demo (API, LLM_PROVIDER=fixture, modo kit) en `GET /studies/{id}`.

Mismo camino que `test_demo_canonica_api.py`: en fixture el juez da las etiquetas del kit, así que
los bloques coinciden con los golden del dominio (`tests/golden/test_rigor_alborada.py`,
`test_competitor_gap_golden.py`, `test_source_map_golden.py`, `test_accuracy_golden.py`,
`test_scenarios_golden.py`). Las cifras canónicas no cambian: 25,93, 8.º de 10 y 25,9 → 30,8.
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
def view(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    db = tmp_path_factory.mktemp("diferencial") / "study.db"
    settings = Settings(
        _env_file=None,
        llm_provider="fixture",
        database_url=f"sqlite:///{db.as_posix()}",
        cache_enabled=False,
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
        out: dict[str, Any] = client.get(f"/studies/{sid}").json()
    assert out["estado"] == "completado", out["errores"]
    return out


def test_cifras_canonicas_intactas(view: dict[str, Any]) -> None:
    assert view["metrics"]["score_global"]["score"] == 25.93
    assert view["metrics"]["ranking"].index(FOCO) + 1 == 8
    assert len(view["metrics"]["ranking"]) == 10
    final = view["simulacion"]["proyecciones"][-1]["score"]
    assert (round(view["simulacion"]["score_actual"], 1), round(final["esperado"], 1)) == (
        25.9,
        30.8,
    )
    assert len(view["findings"]) == 7
    assert not [e for e in view["errores"] if e.startswith("diferencial")]


def test_rigor_score_con_su_intervalo(view: dict[str, Any]) -> None:
    rigor = view["rigor"]
    score = rigor["score_global"]
    # «25,9 [21,6–30,1]» del ADR 0008: bootstrap sembrado, 2000 réplicas, 240 ejecuciones.
    assert (score["valor"], score["inf"], score["sup"], score["n"]) == (25.93, 21.6, 30.15, 240)
    assert score["metodo"] == "bootstrap"
    assert (rigor["replicas_bootstrap"], rigor["semilla_bootstrap"]) == (2000, 20261021)
    assert set(rigor["score_por_motor"]) == {"ChatGPT", "Claude", "Gemini", "Perplexity"}
    assert set(rigor["aparicion_por_motor"]) == {"ChatGPT", "Claude", "Gemini", "Perplexity"}
    assert rigor["deltas"] == {}


def test_rigor_dice_que_hallazgos_no_admiten_contraste(view: dict[str, Any]) -> None:
    hallazgos = view["rigor"]["hallazgos"]
    assert set(hallazgos) == {f["id"] for f in view["findings"]}
    fuente = hallazgos["F-fuente-lider"]
    assert fuente["significancia"] is None and fuente["sin_contraste"]
    assert hallazgos["F-brecha-lider"]["significancia"]["significativa"] is True


def test_competidores_oftalmos_centro_es_la_sorpresa(view: dict[str, Any]) -> None:
    c = view["competidores"]
    assert (c["marca_foco_id"], c["puesto_foco"], c["n_marcas"], c["score_foco"]) == (
        FOCO,
        8,
        10,
        25.93,
    )
    assert c["sorpresas"] == ["oftalmos-centro"]
    assert [d["brand_id"] for d in c["declarados"]] == [
        "grupo-hospitalario-valdecruz",
        "instituto-oftalmico-tramuntana",
        "laser-nitida",
    ]
    assert [f["id"] for f in c["hallazgos"]] == ["F-competidor-no-declarado"]


def test_oportunidades_de_fuente(view: dict[str, Any]) -> None:
    ops = view["oportunidades_fuente"]
    assert [(o["dominio"], o["valor"], o["puntuacion"]) for o in ops[:3]] == [
        ("wikipedia.org", 0.0031, "Media"),
        ("comparaclinicas.example", 0.0004, "Baja"),
        ("rankingclinicas.example", 0.0002, "Baja"),
    ]
    assert all(o["brand_id"] == FOCO and o["evaluation_ids"] for o in ops)


def test_exactitud_sin_inexactitudes(view: dict[str, Any]) -> None:
    (hallazgo,) = view["exactitud"]
    assert hallazgo["brand_id"] == FOCO
    assert hallazgo["n_incorrectas"] == 0
    assert hallazgo["afirmaciones"]
    assert view["mitigaciones"] == []


def test_tres_escenarios_con_el_completo_elegido(view: dict[str, Any]) -> None:
    escenarios = view["escenarios"]
    assert [e["id"] for e in escenarios] == ["minimo_viable", "equilibrado", "completo"]
    assert [e["id"] for e in escenarios if e["elegido"]] == ["completo"]
    completo = escenarios[-1]["escenario"]
    acciones = [a["id"] for fase in view["plan"]["fases"] for a in fase["acciones"]]
    assert len(acciones) == 9
    assert sorted(completo["mantenidas"]) == sorted(acciones)
    # El escenario completo simula lo mismo que el plan.
    assert completo["simulacion"]["proyecciones"] == view["simulacion"]["proyecciones"]

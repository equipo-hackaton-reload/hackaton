"""La demo en pantalla (API, LLM_PROVIDER=fixture, modo kit) muestra la cifra canónica de Alborada.

En fixture el juez devuelve las etiquetas humanas del kit donde existen, así que la API da lo mismo
que `tests/golden/test_demo_canonico.py`: score 25,93 y proyección esperada 30,8 tras la fase 3.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from posiq.interfaces.api.main import create_app
from posiq.settings import Settings
from tests.auth_helpers import authenticate

ROOT = Path(__file__).resolve().parents[2]
BRIEF = ROOT / "data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md"
FOCO = "clinica-alborada-vision"


def test_api_fixture_muestra_cifra_canonica(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="fixture",
        database_url=f"sqlite:///{(tmp_path / 'study.db').as_posix()}",
        cache_enabled=False,
    )
    with TestClient(create_app(settings=settings)) as client:
        authenticate(client)
        brief = BRIEF.read_text(encoding="utf-8")
        response = client.post("/studies", json={"brief_texto": brief, "modo": "kit"})
        assert response.status_code == 201, response.text
        sid = response.json()["study_id"]
        for revision in ("competidores", "plan"):
            response = client.post(
                f"/studies/{sid}/resume", json={"revision": revision, "payload": {"aprobado": True}}
            )
            assert response.status_code == 202, response.text
        view = client.get(f"/studies/{sid}").json()
        assert view["estado"] == "completado", view["errores"]

    score = view["metrics"]["score_global"]
    assert score["brand_id"] == FOCO
    assert score["score"] == 25.93
    assert (score["aparicion"], score["posicion"], score["fuerza"], score["calidad_fuente"]) == (
        11.62,
        4.72,
        3.92,
        5.67,
    )
    assert view["metrics"]["ranking"].index(FOCO) + 1 == 8
    sim = view["simulacion"]
    assert sim["score_actual"] == 25.93
    final = sim["proyecciones"][-1]["score"]
    assert (round(final["minimo"], 1), round(final["esperado"], 1), round(final["maximo"], 1)) == (
        27.8,
        30.8,
        34.0,
    )

"""Seguimiento de la demo (API, LLM_PROVIDER=fixture, modo kit): línea base y una re-medición.

Caso sintético del reto: el kit responde siempre lo mismo, así que la serie de dos estudios del kit
tiene 2 puntos comparables, las cifras canónicas en los dos (25,93, 8.º de 10) y 0 cambios
significativos («Sin cambios fuera del margen de error»), como el golden del dominio
(`tests/golden/test_serie_alborada.py`).
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
APROBADO = {"aprobado": True}


@pytest.fixture(scope="module")
def seguimiento(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    db = tmp_path_factory.mktemp("seguimiento") / "study.db"
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
        original = response.json()["study_id"]
        for revision in ("competidores", "plan"):
            response = client.post(
                f"/studies/{original}/resume", json={"revision": revision, "payload": APROBADO}
            )
            assert response.status_code == 202, response.text
        estimate = client.get(f"/studies/{original}/remeasure/estimate").json()
        body = {"confirmado": True, "coste_estimado_eur": estimate["coste_estimado_eur"]}
        response = client.post(f"/studies/{original}/remeasure", json=body)
        assert response.status_code == 201, response.text
        nuevo = response.json()["study_id"]
        response = client.post(
            f"/studies/{nuevo}/resume", json={"revision": "plan", "payload": APROBADO}
        )
        assert response.status_code == 202, response.text
        return {
            "estimate": estimate,
            "original": original,
            "nuevo": nuevo,
            "vista": client.get(f"/studies/{nuevo}").json(),
            "brands": client.get("/brands").json(),
            "serie": client.get(f"/brands/{FOCO}/serie").json(),
        }


def test_remedicion_del_kit_gratis_y_completada(seguimiento: dict[str, Any]) -> None:
    assert seguimiento["estimate"]["coste_estimado_eur"] == 0.0
    vista = seguimiento["vista"]
    assert vista["estado"] == "completado", vista["errores"]
    assert vista["datos_sinteticos"] is True
    assert vista["configuracion"]["remedicion_de"] == seguimiento["original"]
    assert vista["metrics"]["score_global"]["score"] == 25.93


def test_serie_de_dos_estudios_kit_comparables_y_sin_cambios(seguimiento: dict[str, Any]) -> None:
    serie = seguimiento["serie"]
    a, b = serie["puntos"]
    assert [a["study_id"], b["study_id"]] == [seguimiento["original"], seguimiento["nuevo"]]
    for p in (a, b):
        assert p["score"] == 25.93
        assert (p["intervalo"]["inf"], p["intervalo"]["sup"]) == (21.6, 30.15)
        assert (p["posicion"], p["n_marcas"]) == (8, 10)
    assert b["comparable_con_anterior"] and b["competidores_comparables"]
    assert len(serie["cambios"]) == 8
    assert all(c["delta"] == 0 for c in serie["cambios"])
    assert serie["cambios_significativos"] == []
    assert serie["resumen"] == ["Sin cambios fuera del margen de error"]


def test_brands_resume_la_marca_del_caso_sintetico(seguimiento: dict[str, Any]) -> None:
    (fila,) = seguimiento["brands"]
    assert fila["brand_id"] == FOCO and fila["nombre"] == "Clínica Alborada Visión"
    assert fila["n_mediciones"] == 2

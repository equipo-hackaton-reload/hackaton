"""API real con wiring de producción y fixtures explícitas, sin claves ni red externa."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from posiq.interfaces.api.main import create_app
from posiq.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
BRIEF = ROOT / "data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md"


@pytest.mark.parametrize("multipart", [False, True])
def test_fixture_wiring_completes_and_exports_word(tmp_path: Path, multipart: bool) -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="fixture",
        database_url=f"sqlite:///{(tmp_path / 'study.db').as_posix()}",
        cache_enabled=False,
    )
    with TestClient(create_app(settings=settings)) as client:
        brief = BRIEF.read_text(encoding="utf-8")
        response = (
            client.post(
                "/studies",
                files={"fichero": ("brief.md", brief, "text/markdown")},
                data={"modo": "kit"},
            )
            if multipart
            else client.post("/studies", json={"brief_texto": brief, "modo": "kit"})
        )
        assert response.status_code == 201, response.text
        sid = response.json()["study_id"]
        assert client.get(f"/studies/{sid}/export").status_code == 409
        for revision in ("competidores", "plan"):
            view = client.get(f"/studies/{sid}").json()
            assert view["revision_pendiente"] == revision, view
            response = client.post(
                f"/studies/{sid}/resume", json={"revision": revision, "payload": {"aprobado": True}}
            )
            assert response.status_code == 202, response.text
        view = client.get(f"/studies/{sid}").json()
        assert view["estado"] == "completado", view["errores"]
        assert view["coste_acumulado_eur"] == 0
        proposal = view["proposal"]
        assert proposal["marcas"] == {b["id"]: b["nombre"] for b in view["market"]["marcas"]}
        assert proposal["diagnostico"]["metrics"] == view["metrics"]
        assert proposal["plan"] == view["plan"]
        assert "DEMO SIN IA" in proposal["resumen_ejecutivo"]
        # Trazabilidad brief → propuesta: todo lo que pidió el cliente está tratado.
        encargo = proposal["encargo"]
        assert encargo["ciudades"] == ["Madrid", "Barcelona"]
        assert len(encargo["cobertura"]) == 16
        assert {p["estado"] for p in encargo["cobertura"]} == {"cubierto"}
        response = client.get(f"/studies/{sid}/export?formato=docx")
        assert response.status_code == 200, response.text
        with ZipFile(BytesIO(response.content)) as doc:
            text = doc.read("word/document.xml").decode()
            assert "Alborada" in text and "sintéticos" in text
            assert "Lo que nos habéis pedido" in text

"""`scripts/smoke_engines.py` de punta a punta con un motor simulado (sin red ni claves)."""

import json
from pathlib import Path
from typing import Any

import pytest
from scripts import smoke_engines

from posiq.adapters.engines import OpenAIEngine
from posiq.settings import Settings
from tests.adapters.test_real_engines import Scripted, openai_client, openai_response


def test_smoke_guarda_las_runs_en_jsonl(
    tmp_path: Path, kit_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    monkeypatch.setenv("KIT_DIR", str(kit_dir))
    monkeypatch.setenv("CACHE_ENABLED", "false")
    create = Scripted(*[openai_response(["https://diariosalud.example/a"]) for _ in range(2)])

    def fake_build(settings: Settings, modo: str, marcas: list[str], **kw: Any) -> list[Any]:
        assert modo == "real" and marcas
        return [OpenAIEngine(settings, marcas, client=openai_client(create), **kw)]

    monkeypatch.setattr(smoke_engines, "build_engines", fake_build)
    code = smoke_engines.main(["-n", "2", "--out", str(tmp_path)])

    assert code == 0 and len(create.calls) == 2
    [path] = list(tmp_path.glob("*.jsonl"))
    runs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [r["motor"] for r in runs] == ["ChatGPT", "ChatGPT"]
    assert runs[0]["fuentes"][0]["tipo"] == "Medio" and runs[0]["origen"] == "api"
    out = capsys.readouterr().out
    assert "diariosalud.example (Medio)" in out and "2 runs guardadas" in out


def test_smoke_sin_claves_sale_con_error(
    tmp_path: Path, kit_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KIT_DIR", str(kit_dir))
    monkeypatch.setattr(smoke_engines, "build_engines", lambda *a, **kw: [])
    assert smoke_engines.main(["--out", str(tmp_path)]) == 1

"""Script de evaluación del sistema, sin red: fixtures del kit y estudio exportado a JSON."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "evaluate_system", ROOT / "scripts" / "evaluate_system.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def sin_claves(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("TYPESAFE_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.setenv(var, "")


def test_evaluacion_con_fixtures(script: ModuleType, tmp_path: Path) -> None:
    calibracion = tmp_path / "cal"
    calibracion.mkdir()
    (calibracion / "README.md").write_text("guía", encoding="utf-8")
    assert script.main(["--out", str(tmp_path / "out"), "--calibracion", str(calibracion)]) == 0
    (informe,) = (tmp_path / "out").glob("*.md")
    text = informe.read_text(encoding="utf-8")
    assert "**PENDIENTE**" in text
    assert "Hallazgos con `evaluation_ids` válidos: 7/7 (100 %)" in text
    assert "Acciones con `finding_ids` válidos: 9/9 (100 %)" in text
    assert "falta DEEPSEEK_API_KEY (ni en el entorno ni en .env)" in text
    assert "| Fase 3 · Optimización y medición |" in text and "no una predicción" in text


def test_ultimo_informe_de_calibracion(script: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "2026-10-20_jev.md").write_text("| total | 133 | 0.990 | 67 | 0.800 |", "utf-8")
    (tmp_path / "2026-10-22_jev.md").write_text("| total | 133 | 1.000 | 67 | 0.851 |", "utf-8")
    nombre, resumen = script.latest_calibration(tmp_path)
    assert nombre == "2026-10-22_jev.md" and "aparece 1.000" in resumen and "0.851" in resumen
    (tmp_path / "2026-10-23_llm.md").write_text("sin tabla", "utf-8")
    assert script.latest_calibration(tmp_path)[1] == "formato no reconocido"


def test_estudio_desde_json(script: ModuleType, tmp_path: Path) -> None:
    from posiq.domain.findings import detect_findings
    from tests.golden.conftest import (
        STUDY_ID,
        alborada_brief_summary,
        alborada_metrics,
        example_plan,
        load_kit,
    )

    kit = load_kit()
    brief = alborada_brief_summary()
    findings = detect_findings(alborada_metrics(kit, brief), brief)
    data = {
        "study_id": STUDY_ID,
        "brief": brief.model_dump(mode="json"),
        "marcas": [b.model_dump(mode="json") for b in kit.brands],
        "prompts": [p.model_dump(mode="json", exclude={"tipo"}) for p in kit.prompts],
        "runs": [r.model_dump(mode="json") for r in kit.runs],
        "evaluations": [
            e.model_dump(mode="json", exclude={"peso_posicion", "por_desconocimiento"})
            for e in kit.evaluations()
        ],
        "sources": [s.model_dump(mode="json") for s in kit.sources],
        "plan": example_plan(findings, brief).model_dump(mode="json"),
    }
    path = tmp_path / "estudio.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "out"
    assert script.main(["--study", str(path), "--out", str(out), "--no-plan-guard"]) == 0
    text = next(out.glob("*.md")).read_text(encoding="utf-8")
    assert "desactivado con --no-plan-guard" in text and STUDY_ID in text

from pathlib import Path
from typing import Any

import pytest

from posiq.adapters.judge.calibration import (
    agreement,
    calibrate,
    render_markdown,
    splits,
)
from posiq.adapters.judge.jev import JevJudge
from posiq.domain import kit_loader as kl
from posiq.settings import Settings
from tests.adapters.judge_fakes import FakeSystemOneClient, sdk_answers

STUDY = "S-cal"


@pytest.fixture(scope="module")
def kit(kit_dir: Path) -> dict[str, Any]:
    brands = kl.load_brands(kit_dir / "marcas.csv")
    sources = kl.load_sources(kit_dir / "fuentes_catalogo.csv")
    return {
        "brands": brands,
        "runs": kl.load_runs(kit_dir / "ejecuciones.csv", brands, sources, STUDY),
        "sample": kl.load_evaluated_sample(kit_dir / "muestra_evaluada.csv", brands, STUDY),
    }


def test_split_por_ejecucion(kit: dict[str, Any]) -> None:
    split = splits(kit["sample"])
    assert len(split) == 15
    assert sum(v == "reserva" for v in split.values()) == 5


def test_calibracion_con_juez_falso(settings: Settings, kit: dict[str, Any]) -> None:
    # Juez que siempre dice «Comparación neutra», fuerza 1, neutro, confianza 0,7.
    fake = FakeSystemOneClient(
        sdk_answers(mention="comparacion_neutra", level=1, sentiment="neutro", confidence=0.7)
    )
    judge = JevJudge(settings, kit["brands"], client_factory=lambda: fake)
    report = calibrate(judge, kit["sample"], kit["runs"], kit["brands"])

    assert report.total.n == 133 and len(fake.calls) == 133
    # La aparición la fija la detección por reglas: coincide al 100 % con la muestra.
    assert report.total.aparece == 1.0
    labels_seen = [e for e in kit["sample"] if e.aparece]
    neutras = sum(e.tipo_mencion == "Comparación neutra" for e in labels_seen)
    assert report.total.tipo_mencion == pytest.approx(neutras / len(labels_seen))
    assert report.total.fuerza_pm1 is not None and report.total.fuerza_exacta is not None
    assert report.total.fuerza_pm1 >= report.total.fuerza_exacta
    # Presentes: confianza 0,7 (a revisión). Ausentes: el juez dice «mencionada» y las reglas no,
    # así que la discrepancia limita la confianza a 0,5 (a fallback).
    assert report.a_revision == len(labels_seen)
    assert report.a_fallback == 133 - len(labels_seen) and report.aceptadas == 0
    assert report.tokens_in == 133 * 1000 and report.coste_eur > 0
    assert set(report.por_split) == {"calibracion", "reserva"}

    md = render_markdown(report)
    assert "| total | 133 | 1.000 |" in md and "a revisión" in md


def test_acuerdo_vacio() -> None:
    a = agreement([])
    assert a.n == 0 and a.aparece is None and a.fuerza_mae is None

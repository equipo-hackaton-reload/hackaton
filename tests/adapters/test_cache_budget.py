from datetime import datetime
from pathlib import Path

import pytest

from posiq.adapters.budget import Budget, BudgetExceeded, estimate_judge_cost
from posiq.adapters.cache import DiskCache, stable_hash
from posiq.domain.schemas import Trace
from posiq.settings import Settings


def trace(coste: float, study_id: str = "S-1", nodo: str = "judge") -> Trace:
    return Trace(
        study_id=study_id,
        nodo=nodo,
        modelo="m",
        prompt_version="v",
        tokens_in=1,
        tokens_out=1,
        coste_eur=coste,
        duracion_ms=1,
        fecha=datetime(2026, 10, 21),
    )


def test_cache_guarda_y_recupera(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path / "c.sqlite")
    key = DiskCache.key("jev", "jev-latest", {"b": 1, "a": [1, "á"]}, 2)
    assert key == DiskCache.key("jev", "jev-latest", {"a": [1, "á"], "b": 1}, 2)
    assert key != DiskCache.key("jev", "jev-latest", {"a": [1, "á"], "b": 1}, 3)
    assert cache.get(key) is None
    cache.set(key, {"noul": 0.9})
    assert cache.get(key) == {"noul": 0.9}
    cache.close()
    assert DiskCache(tmp_path / "c.sqlite").get(key) == {"noul": 0.9}


def test_cache_desactivada(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path / "off.sqlite", enabled=False)
    cache.set("k", 1)
    assert cache.get("k") is None and not (tmp_path / "off.sqlite").exists()
    cache.close()


def test_cache_from_settings(settings: Settings) -> None:
    cache = DiskCache.from_settings(settings)
    assert cache.enabled
    assert stable_hash({"a": 1}) == stable_hash({"a": 1})


def test_budget_acumula_y_corta() -> None:
    budget = Budget(max_eur=0.10, study_id="S-1")
    budget.record(trace(0.06, nodo="jev"))
    budget.record(trace(0.04, nodo="intake.v1"))
    assert budget.total_eur == pytest.approx(0.10) and budget.remaining_eur == pytest.approx(0)
    with pytest.raises(BudgetExceeded):
        budget.record(trace(0.01))
    assert len(budget.traces) == 3
    assert budget.by_node() == pytest.approx({"jev": 0.06, "intake.v1": 0.04, "judge": 0.01})


def test_budget_rechaza_otro_estudio(settings: Settings) -> None:
    budget = Budget.from_settings(settings, study_id="S-1")
    assert budget.max_eur == 5.0
    with pytest.raises(ValueError, match="S-2"):
        budget.record(trace(0.01, study_id="S-2"))


def test_estimacion_del_juez(settings: Settings) -> None:
    # 624 ejecuciones × 10 marcas × 1.000 tokens × 0,04 $/M × 0,86 €/$ ≈ 0,21 €
    assert estimate_judge_cost(624, 10, settings) == pytest.approx(624 * 10 * 1000 * 0.04e-6 * 0.86)
    assert estimate_judge_cost(0, 10, settings) == 0
    assert estimate_judge_cost(1, 1) >= 0

from pathlib import Path

import pytest

from posiq.adapters.engines.kit import KitEngine, KitMissError
from posiq.domain import kit_loader as kl
from posiq.domain.schemas import PromptInstance
from posiq.ports import Engine
from posiq.settings import Settings


@pytest.fixture(scope="module")
def prompts(kit_dir: Path) -> dict[str, PromptInstance]:
    brands = kl.load_brands(kit_dir / "marcas.csv")
    templates = kl.load_prompt_bank(kit_dir / "banco_prompts.csv")
    instances = kl.load_prompt_instances(kit_dir / "ejecuciones.csv", templates, brands)
    return {p.id: p for p in instances}


def test_cuatro_motores_como_engines(kit_dir: Path) -> None:
    engines: list[Engine] = list(KitEngine.all_motors(kit_dir))
    assert [e.name for e in engines] == [
        "kit:ChatGPT",
        "kit:Gemini",
        "kit:Perplexity",
        "kit:Claude",
    ]


def test_devuelve_la_ejecucion_con_el_estudio(
    kit_dir: Path, prompts: dict[str, PromptInstance]
) -> None:
    run = KitEngine(kit_dir, "Gemini").ask(prompts["OFT-DG-01-01"], repeticion=1, study_id="S-9")
    assert (run.id, run.motor, run.repeticion) == ("EJ-0002", "Gemini", 1)
    assert run.study_id == "S-9" and run.origen == "kit"
    again = KitEngine(kit_dir, "Gemini", name="kit").ask(
        prompts["OFT-DG-01-01"], repeticion=1, study_id="S-10"
    )
    assert again.study_id == "S-10" and again.texto_respuesta == run.texto_respuesta


def test_todas_las_combinaciones_del_kit(kit_dir: Path, prompts: dict[str, PromptInstance]) -> None:
    engines = KitEngine.all_motors(kit_dir)
    runs = [
        e.ask(p, repeticion=r, study_id="S")
        for p in prompts.values()
        for e in engines
        for r in (1, 2, 3)
    ]
    assert len({r.id for r in runs}) == 624


def test_combinacion_inexistente(kit_dir: Path, prompts: dict[str, PromptInstance]) -> None:
    with pytest.raises(KitMissError, match="OFT-DG-01-01") as exc:
        KitEngine(kit_dir, "Claude").ask(prompts["OFT-DG-01-01"], repeticion=4, study_id="S")
    assert exc.value.prompt_id == "OFT-DG-01-01"


def test_desde_settings(settings: Settings) -> None:
    assert len(KitEngine.from_settings(settings)) == 4

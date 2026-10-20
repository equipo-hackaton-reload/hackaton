from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from posiq.domain import kit_loader as kl


@pytest.fixture(scope="module")
def kit(kit_dir: Path) -> dict[str, list]:  # type: ignore[type-arg]
    brands = kl.load_brands(kit_dir / "marcas.csv")
    templates = kl.load_prompt_bank(kit_dir / "banco_prompts.csv")
    sources = kl.load_sources(kit_dir / "fuentes_catalogo.csv")
    return {
        "brands": brands,
        "templates": templates,
        "sources": sources,
        "instances": kl.load_prompt_instances(kit_dir / "ejecuciones.csv", templates, brands),
        "runs": kl.load_runs(kit_dir / "ejecuciones.csv", brands, sources, "S-kit"),
        "sample": kl.load_evaluated_sample(kit_dir / "muestra_evaluada.csv", brands, "S-kit"),
    }


def test_recuentos_del_kit(kit: dict[str, list]) -> None:  # type: ignore[type-arg]
    counts = {k: len(v) for k, v in kit.items()}
    assert counts == {
        "brands": 10,
        "templates": 25,
        "sources": 25,
        "instances": 52,
        "runs": 624,
        "sample": 133,
    }


def test_marcas_y_roles(kit: dict[str, list]) -> None:  # type: ignore[type-arg]
    by_id = {b.id: b for b in kit["brands"]}
    assert by_id["clinica-alborada-vision"].aliases == ["Alborada Visión", "Alborada"]
    assert by_id["clinica-alborada-vision"].rol == "foco"
    assert by_id["grupo-hospitalario-valdecruz"].rol == "lider"
    assert Counter(b.rol for b in kit["brands"]) == {"foco": 4, "contexto": 5, "lider": 1}


def test_instancias(kit: dict[str, list]) -> None:  # type: ignore[type-arg]
    instances = kit["instances"]
    assert {i.ciudad for i in instances} == {None, "Madrid", "Barcelona"}
    par = next(i for i in instances if i.instanciacion == "par")
    assert par.marca_nombrada and par.marca_nombrada_b
    assert Counter(i.tipo for i in instances) == {"espontaneo": 20, "asistido": 32}


def test_runs(kit: dict[str, list]) -> None:  # type: ignore[type-arg]
    runs = kit["runs"]
    instance_ids = {i.id for i in kit["instances"]}
    assert all(r.prompt_id in instance_ids for r in runs)
    assert {r.study_id for r in runs} == {"S-kit"}
    assert sum(1 for r in runs if not r.fuentes) == 57
    assert all(s.tipo is not None for r in runs for s in r.fuentes)
    assert sum(len(r.marcas_a_evaluar) for r in runs) == 2928


def test_muestra(kit: dict[str, list]) -> None:  # type: ignore[type-arg]
    sample = kit["sample"]
    assert len({e.run_id for e in sample}) == 15
    assert all(e.origen == "humano" and e.study_id == "S-kit" for e in sample)
    assert sum(e.fuerza == -1 for e in sample) == 15


def test_columna_que_falta() -> None:
    with pytest.raises(kl.KitFormatError, match="faltan columnas"):
        kl.brands_from_frame(pd.DataFrame({"Marca": ["X"]}))


def test_categoria_invalida_indica_fila() -> None:
    df = pd.DataFrame(
        [{"Dominio": "x.example", "Tipo_de_fuente": "Blog", "Calidad_de_fuente_0_1": "0.5"}]
    )
    with pytest.raises(kl.KitFormatError, match="fila 2"):
        kl.sources_from_frame(df)


def test_marca_desconocida(kit: dict[str, list]) -> None:  # type: ignore[type-arg]
    row = {c: "1" for c in kl.MUESTRA_COLS} | {"Marca": "Clínica Inventada", "Posición": ""}
    with pytest.raises(kl.KitFormatError, match="marca desconocida"):
        kl.evaluated_sample_from_frame(pd.DataFrame([row]), kit["brands"], "S-kit")


def test_intencion_desconocida() -> None:
    row = {c: "x" for c in kl.BANCO_COLS} | {"Intención": "Fidelización"}
    with pytest.raises(kl.KitFormatError, match="intención desconocida"):
        kl.prompt_bank_from_frame(pd.DataFrame([row]))


def test_plantilla_que_no_encaja(kit: dict[str, list]) -> None:  # type: ignore[type-arg]
    row = {c: "" for c in kl.EJECUCIONES_COLS} | {
        "Prompt_ID": "OFT-LO-01",
        "Prompt ejecutado": "Texto que no es la plantilla",
    }
    with pytest.raises(kl.KitFormatError, match="no encaja"):
        kl.prompt_instances_from_frame(pd.DataFrame([row]), kit["templates"], kit["brands"])
    row["Prompt_ID"] = "OFT-ZZ-99"
    with pytest.raises(kl.KitFormatError, match="no está en el banco"):
        kl.prompt_instances_from_frame(pd.DataFrame([row]), kit["templates"], kit["brands"])

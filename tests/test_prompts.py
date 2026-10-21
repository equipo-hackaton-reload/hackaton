"""Los prompts versionados existen, tienen cabecera válida, apuntan a un esquema real y no
interpolan datos."""

import re

import pytest

from posiq.domain import schemas
from posiq.prompts import PROMPTS_DIR, PromptSet, load_prompt, parse_prompt

ESPERADOS = {
    "intake": "BriefSummary",
    "market": "Market",
    "prompts": "PromptSet",
    "plan": "Plan",
    "write": "ProposalDraft",
    "claims": "AfirmacionesLLM",
}
# Esquemas de salida que no viven en `domain/schemas.py`.
FUERA_DE_SCHEMAS = ("PromptSet", "ProposalDraft", "AfirmacionesLLM")
INTERPOLACION = re.compile(r"\{[^{}]*\}")


@pytest.mark.parametrize("nombre", sorted(ESPERADOS))
def test_prompt_valido(nombre: str) -> None:
    assert (PROMPTS_DIR / f"{nombre}.v1.md").is_file()
    spec = load_prompt(nombre)
    assert spec.version_tag == f"{nombre}.v1"
    assert spec.schema_name == ESPERADOS[nombre]
    assert spec.schema_name in FUERA_DE_SCHEMAS or hasattr(schemas, spec.schema_name)
    assert spec.state and all(clave and desc for clave, desc in spec.state.items())
    assert "no inventes cifras" in spec.texto.lower()


@pytest.mark.parametrize("nombre", sorted(ESPERADOS))
def test_sin_llaves_de_interpolacion(nombre: str) -> None:
    contenido = (PROMPTS_DIR / f"{nombre}.v1.md").read_text(encoding="utf-8")
    assert not INTERPOLACION.search(contenido)
    assert "{" not in contenido and "}" not in contenido


def test_todos_los_md_de_prompts_estan_cubiertos() -> None:
    versionados = {p.name.split(".")[0] for p in PROMPTS_DIR.glob("*.v*.md")}
    assert versionados == set(ESPERADOS)


def test_cabecera_obligatoria() -> None:
    with pytest.raises(ValueError, match="cabecera"):
        parse_prompt("sin cabecera")


def test_prompt_set_separa_y_no_repite_ids() -> None:
    base = {
        "template_id": "T",
        "familia": "Descubrimiento genérico",
        "fase_embudo": "descubrimiento",
        "texto": "¿Qué opciones hay?",
        "prioridad": "P1",
    }
    esp = schemas.PromptInstance.model_validate({**base, "id": "a", "instanciacion": "generico"})
    asi = schemas.PromptInstance.model_validate(
        {**base, "id": "b", "instanciacion": "marca", "marca_nombrada": "X"}
    )
    ps = PromptSet(prompts=[esp, asi])
    assert ps.espontaneos == [esp] and ps.asistidos == [asi]
    with pytest.raises(ValueError, match="repetidos"):
        PromptSet(prompts=[esp, esp])


def test_write_v2_enlaza_el_brief() -> None:
    spec = load_prompt("write", 2)
    assert spec.version_tag == "write.v2" and spec.schema_name == "ProposalDraft"
    assert {"puntos_brief", "carencias_cobertura", "borrador_anterior"} <= set(spec.state)
    assert "cobertura_brief" in spec.texto and "no inventes cifras" in spec.texto.lower()
    contenido = (PROMPTS_DIR / "write.v2.md").read_text(encoding="utf-8")
    assert "{" not in contenido and "}" not in contenido


def test_intake_v2_extrae_la_identidad_deseada_sin_inventarla() -> None:
    spec = load_prompt("intake", 2)
    assert spec.version_tag == "intake.v2" and spec.schema_name == "BriefSummary"
    assert set(spec.state) == {"brief"}
    assert {"posicionamiento_deseado", "atributos_deseados"} <= set(
        re.findall(r"`(\w+)`", spec.texto)
    )
    assert "no inventes cifras" in spec.texto.lower() and "nunca los inventes" in spec.texto
    contenido = (PROMPTS_DIR / "intake.v2.md").read_text(encoding="utf-8")
    assert "{" not in contenido and "}" not in contenido

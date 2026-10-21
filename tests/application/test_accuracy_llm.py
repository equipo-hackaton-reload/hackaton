"""Capa opcional con LLM de la exactitud de marca: en fixture es determinista y sin red."""

from typing import Any

from pydantic import BaseModel

from posiq.adapters.llm.fixture import FixtureLLM, fixture_trace
from posiq.application.accuracy import PROMPT_CLAIMS, extraer_afirmaciones_llm
from posiq.application.kit import load_kit
from posiq.domain.accuracy import AfirmacionesLLM, AfirmacionLLM, evaluar_exactitud
from posiq.domain.schemas import Trace
from tests.application.fakes import KIT_DIR, kit_settings
from tests.golden.conftest import alborada_brief_summary

ALBORADA = "clinica-alborada-vision"


def test_fixture_llm_es_determinista_y_no_duplica_las_reglas() -> None:
    kit = load_kit(str(KIT_DIR))
    brand = next(b for b in kit.brands if b.id == ALBORADA)
    runs = kit.runs[:40]
    llm = FixtureLLM(kit_settings())
    primera, trazas = extraer_afirmaciones_llm(llm, runs, brand, study_id="S", marcas=kit.brands)
    segunda, _ = extraer_afirmaciones_llm(llm, runs, brand, study_id="S", marcas=kit.brands)
    assert primera == segunda and primera
    assert all(a.origen == "llm" for a in primera)
    llamadas = [r for r in runs if "Alborada" in r.texto_respuesta]
    assert len(trazas) == len(llamadas)
    assert all(t.nodo == PROMPT_CLAIMS and t.study_id == "S" for t in trazas)

    solo_reglas, _ = evaluar_exactitud(
        "S", brand, alborada_brief_summary(), runs, marcas=kit.brands
    )
    con_llm, _ = evaluar_exactitud(
        "S", brand, alborada_brief_summary(), runs, marcas=kit.brands, afirmaciones_llm=primera
    )
    assert con_llm == solo_reglas


class _LLMInventa:
    """LLM falso que devuelve un fragmento inventado y otro literal; guarda el `state` recibido."""

    def __init__(self) -> None:
        self.estados: list[dict[str, Any]] = []

    def structured[T: BaseModel](
        self, schema: type[T], prompt_name: str, state: dict[str, Any], *, study_id: str
    ) -> tuple[T, Trace]:
        assert schema is AfirmacionesLLM and prompt_name == PROMPT_CLAIMS
        self.estados.append(state)
        primera = state["respuesta"].split(". ")[0]
        salida = AfirmacionesLLM(
            afirmaciones=[
                AfirmacionLLM(texto="Alborada tiene sede en Valencia.", tipo="sede"),
                AfirmacionLLM(texto=primera, tipo="otro"),
            ]
        )
        return schema.model_validate(salida.model_dump()), fixture_trace(study_id, prompt_name)


def test_descarta_lo_que_el_llm_inventa_y_pasa_la_respuesta_como_dato() -> None:
    kit = load_kit(str(KIT_DIR))
    brand = next(b for b in kit.brands if b.id == ALBORADA)
    run = next(r for r in kit.runs if "Clínica Alborada Visión" in r.texto_respuesta)
    llm = _LLMInventa()
    afirmaciones, _ = extraer_afirmaciones_llm(llm, [run], brand, study_id="S")
    assert llm.estados[0]["respuesta"] == run.texto_respuesta
    assert all(a.texto in run.texto_respuesta for a in afirmaciones)
    assert not any("Valencia" in a.texto for a in afirmaciones)

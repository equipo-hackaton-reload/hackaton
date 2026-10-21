"""Proyecciones del estado del grafo que la API sirve a la web."""

from datetime import UTC, datetime

from posiq.domain.schemas import Evaluation, PromptInstance, Run, Source
from posiq.interfaces.api.views import TEXTO_MAX, evidence


def state() -> dict[str, list[object]]:
    prompt = PromptInstance(
        id="OFT-DG-01",
        template_id="OFT-DG-01",
        familia="Descubrimiento genérico",
        fase_embudo="descubrimiento",
        instanciacion="generico",
        texto="¿Cuáles son las mejores clínicas?",
        prioridad="P1",
    )
    run = Run(
        id="EJ-0001",
        study_id="s1",
        prompt_id=prompt.id,
        motor="Gemini",
        repeticion=1,
        fecha=datetime.now(UTC),
        texto_respuesta="x" * (TEXTO_MAX + 500),
        fuentes=[Source(dominio="medio.example", tipo="Medio", calidad=0.9)],
        marcas_a_evaluar=["alborada"],
    )
    evaluation = Evaluation(
        id="EJ-0001:alborada",
        study_id="s1",
        run_id=run.id,
        brand_id="alborada",
        aparece=False,
        fuerza=0,
        confianza=1.0,
        origen="humano",
    )
    return {"prompts": [prompt], "runs": [run], "evaluations": [evaluation]}


def test_evidence_truncates_the_answer_and_flattens_sources() -> None:
    [item] = evidence(state(), ["EJ-0001:alborada"])
    assert item.motor == "Gemini"
    assert item.prompt == "¿Cuáles son las mejores clínicas?"
    assert len(item.texto_respuesta) == TEXTO_MAX
    assert item.fuentes == ["medio.example"]


def test_evidence_skips_unknown_ids_and_empty_state() -> None:
    items = evidence(state(), ["otra", "EJ-0001:alborada"])
    assert [i.evaluation.id for i in items] == ["EJ-0001:alborada"]
    assert evidence({}, ["EJ-0001:alborada"]) == []

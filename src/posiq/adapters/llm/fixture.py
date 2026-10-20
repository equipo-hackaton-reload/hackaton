"""Demo Alborada explícita y sin red; datos de ejemplo derivados de las fixtures golden.

No importa tests ni pytest y no pretende interpretar briefs de otras marcas.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from posiq.adapters.llm._fixture_data import (
    alborada_brief_summary,
    alborada_proposal,
    example_plan,
)
from posiq.application.schemas_draft import ProposalDraft
from posiq.domain.detection import detect_in_run, evaluation_from_detection
from posiq.domain.schemas import Brand, BriefSummary, Evaluation, Finding, Market, Plan, Run, Trace
from posiq.prompts import PromptSet
from posiq.settings import Settings


def fixture_trace(study_id: str, nodo: str) -> Trace:
    return Trace(
        study_id=study_id,
        nodo=nodo,
        modelo="fixture-alborada",
        prompt_version=nodo,
        tokens_in=0,
        tokens_out=0,
        coste_eur=0,
        duracion_ms=0,
        fecha=datetime.now(UTC),
    )


class FixtureLLM:
    """LLM.structured reproducible; habilitar solo con LLM_PROVIDER=fixture."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def structured[T: BaseModel](
        self, schema: type[T], prompt_name: str, state: dict[str, Any], *, study_id: str
    ) -> tuple[T, Trace]:
        from posiq.application.kit import load_kit

        kit = load_kit(str(Path(self.settings.kit_dir).resolve()))
        output: BaseModel
        if schema is BriefSummary:
            if "alborada" not in str(state.get("brief", "")).lower():
                raise ValueError("FixtureLLM solo admite el brief sintético de Alborada")
            output = alborada_brief_summary()
        elif schema is Market:
            output = Market(marcas=kit.brands_in_runs())
        elif schema is PromptSet:
            output = PromptSet(prompts=kit.prompts)
        elif schema is Plan:
            brief = BriefSummary.model_validate(state["brief"])
            findings = [Finding.model_validate(f) for f in state["hallazgos"]]
            output = example_plan(findings, brief, study_id)
            # Las bases proceden de métricas de ESTE estudio; los objetivos son ilustrativos.
            barcelona = next(
                (
                    c["tasa"]
                    for c in state["metricas"]["visibilidad_foco"]
                    if c["dimension"] == "ciudad"
                    and c["valor"] == "Barcelona"
                    and c["tipo"] == "espontaneo"
                ),
                None,
            )
            output = output.model_copy(
                update={
                    "objetivos": [
                        o.model_copy(
                            update={
                                "valor_actual": state["metricas"]["score_global"]["score"] or 0,
                            }
                        )
                        if o.kpi == "Score de Citación espontáneo"
                        else o.model_copy(update={"valor_actual": barcelona or 0})
                        for o in output.objetivos
                    ]
                }
            )
        elif schema is ProposalDraft:
            from posiq.domain.schemas import Metrics

            proposal = alborada_proposal(
                Metrics.model_validate(state["metrics"]),
                [Finding.model_validate(f) for f in state["hallazgos"]],
                Plan.model_validate(state["plan"]),
                BriefSummary.model_validate(state["brief"]),
                Market.model_validate(state["market"]).marcas,
            )
            output = ProposalDraft(
                resumen_ejecutivo="DEMO SIN IA: textos y plan de ejemplo, datos sintéticos. "
                + proposal.resumen_ejecutivo,
                contexto_alcance="Kit Alborada; evaluación por reglas sin juez semántico.",
                diagnostico=proposal.diagnostico.texto,
                competencia=proposal.competencia.texto,
                interpretacion_hallazgos={f.id: f.descripcion for f in proposal.hallazgos},
                estrategia=proposal.estrategia.texto,
                prioridades=proposal.estrategia.prioridades,
                riesgos=proposal.riesgos,
                supuestos=[
                    "Textos, objetivos y plan de ejemplo; no son recomendaciones generadas por IA.",
                    "Todas las evaluaciones se basan en detección; fuerza neutra si aparece.",
                    "Datos sintéticos; ninguna acción garantiza resultados.",
                ],
                hoja_ruta=proposal.hoja_ruta.seguimiento,
            )
        else:
            raise ValueError(f"FixtureLLM no soporta el esquema {schema.__name__}")
        return schema.model_validate(
            output.model_dump(exclude_computed_fields=True)
        ), fixture_trace(study_id, prompt_name)


class FixtureJudge:
    """Suelo por reglas: fuerza 1 si aparece, sin inventar sentimiento o recomendación."""

    name = "fixture-detection"

    def __init__(self, market: Market) -> None:
        self.market = market
        self.traces: list[Trace] = []

    def evaluate(self, run: Run, brand: Brand) -> Evaluation:
        detection = detect_in_run(run, self.market.marcas).get(brand.id)
        return evaluation_from_detection(run, brand, detection)

    async def aevaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        out = [self.evaluate(run, brand) for run, brand in pairs]
        if pairs:
            self.traces.append(fixture_trace(pairs[0][0].study_id, "judge:fixture"))
        return out

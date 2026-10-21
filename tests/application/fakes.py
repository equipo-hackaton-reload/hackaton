"""Dobles sin red de los puertos (`LLM`, `Engine`, juez) y fixtures válidos del caso del kit."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from posiq.adapters.budget import Budget
from posiq.adapters.errors import MissingCredentialError
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.deps import Deps, PlanGuardFactory
from posiq.application.schemas_draft import ProposalDraft
from posiq.domain.detection import detect_in_run, evaluation_from_detection
from posiq.domain.quality_schemas import PlanQuality
from posiq.domain.schemas import (
    Action,
    Brand,
    BriefSummary,
    Evaluation,
    Finding,
    Market,
    Objective,
    Phase,
    Plan,
    PromptInstance,
    Riesgo,
    Run,
    Trace,
)
from posiq.ports import Engine
from posiq.settings import Settings

Handler = Callable[[dict[str, Any]], BaseModel]


def trace(study_id: str, nodo: str, coste: float = 0.0) -> Trace:
    return Trace(
        study_id=study_id,
        nodo=nodo,
        modelo="fake",
        prompt_version="test",
        tokens_in=0,
        tokens_out=0,
        coste_eur=coste,
        duracion_ms=0,
        fecha=datetime.now(UTC),
    )


class FakeLLM:
    """`ports.LLM` que responde con `handlers[prompt_name](state)` y apunta cada llamada."""

    def __init__(self, handlers: dict[str, Handler], coste: float = 0.0) -> None:
        self.handlers = handlers
        self.coste = coste
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def structured[T: BaseModel](
        self, schema: type[T], prompt_name: str, state: dict[str, Any], *, study_id: str
    ) -> tuple[T, Trace]:
        self.calls.append((prompt_name, state))
        output = self.handlers[prompt_name](state)
        assert isinstance(output, schema), f"{prompt_name} devolvió {type(output).__name__}"
        return output, trace(study_id, prompt_name, self.coste)

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


class FakeEngine:
    """`ports.Engine` real (origen `api`) que responde siempre el mismo texto."""

    def __init__(
        self,
        name: str = "fake:ChatGPT",
        texto: str = "",
        coste: float = 0.0,
        motor: str = "ChatGPT",
    ) -> None:
        self.name = name
        self.texto = texto
        self.coste = coste
        self.motor = motor
        self.calls: list[tuple[str, int]] = []

    def ask(self, prompt: PromptInstance, *, repeticion: int, study_id: str) -> Run:
        self.calls.append((prompt.id, repeticion))
        return Run(
            id=f"{self.name}:{prompt.id}:{repeticion}",
            study_id=study_id,
            prompt_id=prompt.id,
            motor=self.motor,  # type: ignore[arg-type]
            modelo="fake-model",
            repeticion=repeticion,
            fecha=datetime.now(UTC),
            texto_respuesta=self.texto,
            marcas_a_evaluar=["pendiente"],
            coste_eur=self.coste,
            tokens=10,
            origen="api",
        )


class DetectionJudge:
    """Juez falso: la detección por reglas del dominio, con las trazas a coste 0."""

    name = "deteccion"

    def __init__(self, market: Market, budget: Budget | None = None) -> None:
        self.market = market
        self.budget = budget
        self.traces: list[Trace] = []
        self.pairs: list[tuple[Run, Brand]] = []

    async def aevaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        self.pairs.extend(pairs)
        out = []
        for run, brand in pairs:
            detection = detect_in_run(run, self.market.marcas).get(brand.id)
            out.append(evaluation_from_detection(run, brand, detection, confianza=0.9))
        if pairs:
            self.traces.append(trace(pairs[0][0].study_id, "judge:deteccion"))
        return out


class FakeGuard:
    """PlanGuard falso: una llamada de coste fijo apuntada en el presupuesto del estudio."""

    def __init__(self, budget: Budget, coste: float = 0.01, *, sin_clave: bool = False) -> None:
        self.budget = budget
        self.coste = coste
        self.sin_clave = sin_clave
        self.planes: list[Plan] = []

    async def aassess(
        self, plan: Plan, findings: Sequence[Finding], brief: BriefSummary
    ) -> PlanQuality:
        if self.sin_clave:
            raise MissingCredentialError("TYPESAFE_API_KEY", "PlanGuard")
        self.planes.append(plan)
        self.budget.record(trace(plan.study_id, "plan_guard:fake", self.coste))
        return PlanQuality(
            study_id=plan.study_id,
            juez="fake",
            modelo="fake",
            acciones=[],
            pct_especificas=None,
            pct_coherentes=None,
            pct_respetan_restricciones=None,
            pct_realistas=None,
            calidad_media=None,
            por_debajo_umbral=[],
            baja_confianza=[],
            nota=f"{len(plan.acciones)} acciones evaluadas",
        )


KIT_DIR = Path(__file__).resolve().parents[2] / "data" / "kit" / "02_Datos" / "caso_oftalmologia"


def kit_settings(**kw: Any) -> Settings:
    return Settings(_env_file=None, kit_dir=str(KIT_DIR), cache_enabled=False, **kw)  # type: ignore[call-arg]


def memory_repo() -> SqlStudyRepo:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    return SqlStudyRepo(engine=engine)


def make_deps(
    llm: FakeLLM,
    engines: Sequence[Engine],
    repo: SqlStudyRepo,
    *,
    settings: Settings | None = None,
    judge_factory: Callable[[Market, Budget], Any] | None = None,
    budget_max: float = 5.0,
    plan_guard_factory: PlanGuardFactory | None = None,
) -> Deps:
    return Deps(
        llm=llm,
        engines=list(engines),
        judge_factory=judge_factory or DetectionJudge,
        repo=repo,
        budget=lambda study_id: Budget(budget_max, study_id),
        settings=settings or kit_settings(),
        plan_guard_factory=plan_guard_factory,
    )


# --- Fixtures del caso Clínica Alborada -----------------------------------------------------------

RESTRICCIONES = [
    "Publicidad sanitaria regulada: no prometer resultados",
    "Sin comparativas denigratorias",
]


def brief_alborada() -> BriefSummary:
    return BriefSummary(
        marca="Clínica Alborada Visión",
        sector="Sanidad privada",
        subsector="Oftalmología (cirugía refractiva y cataratas)",
        servicios_prioritarios=["Cirugía refractiva", "Control de miopía infantil"],
        publicos=["Adultos 25-50 con miopía", "Mayores de 60 con cataratas"],
        ciudades=["Madrid", "Barcelona"],
        competidores_declarados=[
            "Instituto Oftálmico Tramuntana",
            "Láser Nítida",
            "Grupo Hospitalario Valdecruz",
        ],
        presupuesto_anual_eur=(18000, 27000),
        equipo=["Responsable de marketing", "Comunicación a media jornada", "Agencia"],
        restricciones=list(RESTRICCIONES),
        objetivos=["Recomendación espontánea en Madrid y Barcelona"],
        audiencia_del_entregable="Comité de dirección",
        tono="Riguroso, cercano y sin sensacionalismo",
    )


def market_from_candidates(state: dict[str, Any]) -> Market:
    """Lo que haría el LLM con candidatos: proponerlos con el nombre (el id lo pone el código)."""
    marcas = [{**b, "id": f"llm-{i}"} for i, b in enumerate(state["candidatos"])]
    return Market.model_validate({"marcas": marcas})


def plan_from_findings(state: dict[str, Any], *, restricciones: list[str] | None = None) -> Plan:
    findings = [Finding.model_validate(f) for f in state["hallazgos"]]
    revisadas = state["brief"]["restricciones"] if restricciones is None else restricciones
    acciones = [
        Action(
            id=f"A{i + 1}",
            descripcion=f"Atacar: {f.titulo}",
            finding_ids=[f.id],
            palanca="contenido",
            fase_embudo=f.fase_embudo,
            esfuerzo="M",
            impacto=f.impacto,
            responsable="Responsable de marketing",
            entregables=["Plan de contenidos"],
            plazo_semanas=8,
            kpi="Tasa de aparición espontánea",
            restricciones_revisadas=list(revisadas),
        )
        for i, f in enumerate(findings[:3])
    ]
    return Plan(
        study_id="lo-pone-el-codigo",
        objetivos=[
            Objective(kpi="Score de Citación", valor_actual=0, valor_objetivo=0, plazo_semanas=24)
        ],
        fases=[Phase(nombre="Fase 1", semanas=12, objetivo="Visibilidad", acciones=acciones)],
        presupuesto_estimado_eur=20000,
        respeta_restricciones=True,
    )


def proposal_draft(state: dict[str, Any]) -> ProposalDraft:
    return ProposalDraft(
        resumen_ejecutivo="Resumen.",
        contexto_alcance="Muestra pequeña",
        diagnostico="Diagnóstico.",
        competencia="Competencia.",
        interpretacion_hallazgos={f["id"]: f["descripcion"] for f in state["hallazgos"]},
        estrategia="Estrategia.",
        prioridades=["Contenido"],
        riesgos=[Riesgo(riesgo="Cambios de modelo", mitigacion="Re-medir")],
        supuestos=["Muestra pequeña"],
        hoja_ruta="Mensual",
    )


def kit_llm() -> FakeLLM:
    return FakeLLM(
        {
            "intake.v1": lambda _: brief_alborada(),
            "market.v1": market_from_candidates,
            "plan.v1": plan_from_findings,
            "write.v1": proposal_draft,
        }
    )

"""Modo REAL «en seco»: la API recorre estudio → competidores → plan → propuesta con el grafo del
modo real y TODOS sus clientes falsos inyectados (LLM, los 4 motores, juez y PlanGuard).

Sirve para ensayar la medición real sin gastar: comprueba que cada llamada «de pago» deja su
`Trace` con coste, que el coste acumulado del estudio es la suma de esas trazas, que el presupuesto
corta la serie y que no se abre ningún socket. La marca es inventada a propósito: el kit (Clínica
Alborada, caso sintético) no se mezcla con el modo real.
"""

import socket
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from posiq.adapters.budget import Budget
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.deps import Deps
from posiq.application.graph import serializer
from posiq.application.nodes.run import CONCURRENCIA
from posiq.application.runner import StudyRunner
from posiq.domain.schemas import Brand, BriefSummary, Market, PromptInstance, Run, Trace
from posiq.interfaces.api.main import create_app
from posiq.prompts import PromptSet
from tests.application.fakes import (
    DetectionJudge,
    FakeEngine,
    FakeGuard,
    FakeLLM,
    brief_alborada,
    kit_settings,
    plan_from_findings,
    proposal_draft,
    trace,
)
from tests.auth_helpers import authenticate_async

pytestmark = pytest.mark.anyio

MOTORES = ("ChatGPT", "Gemini", "Perplexity", "Claude")
COSTE_LLM = 0.002
COSTE_MOTOR = 0.01
COSTE_JUEZ = 0.001
COSTE_GUARD = 0.003
BRIEF = "# Brief\n\n**Marca:** Ópticas Faro (marca de ensayo, no es del kit)"
FOCO = "Ópticas Faro"
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
CON_FOCO = "En Madrid: Visión Norte y, como alternativa, Ópticas Faro o Lentes Sur."
SIN_FOCO = "Lo más recomendado es Visión Norte; también Lentes Sur."


class RealishEngine(FakeEngine):
    """Motor falso con respuestas distintas por ciudad y motor (Claude nunca nombra el foco): así
    salen hallazgos de verdad (motor débil, ciudad baja, caída de embudo, brecha con el líder)."""

    def ask(self, prompt: PromptInstance, *, repeticion: int, study_id: str) -> Run:
        run = super().ask(prompt, repeticion=repeticion, study_id=study_id)
        foco = prompt.ciudad == "Madrid" and self.motor != "Claude"
        return run.model_copy(update={"texto_respuesta": CON_FOCO if foco else SIN_FOCO})


def brief_real(_: dict[str, Any]) -> BriefSummary:
    return brief_alborada().model_copy(
        update={
            "marca": FOCO,
            "subsector": "Óptica y optometría",
            "competidores_declarados": ["Visión Norte"],
        }
    )


def market_real(_: dict[str, Any]) -> Market:
    return Market(
        marcas=[
            Brand(id="faro", nombre=FOCO, rol="foco"),
            Brand(id="vision-norte", nombre="Visión Norte", rol="lider"),
            Brand(id="lentes-sur", nombre="Lentes Sur", rol="contexto"),
        ]
    )


def prompt(pid: str, ciudad: str, fase: Any) -> PromptInstance:
    return PromptInstance(
        id=pid,
        template_id=f"T-{pid}",
        familia="Localización",
        fase_embudo=fase,
        instanciacion="ciudad",
        ciudad=ciudad,
        texto=f"¿Qué óptica me recomiendas en {ciudad} para graduarme la vista?",
        prioridad="P1",
    )


def prompts_real(_: dict[str, Any]) -> PromptSet:
    # R-3 repite la plantilla de R-1 con prioridad P2: `REAL_MAX_PROMPTS=2` la deja fuera.
    r1 = prompt("R-1", "Madrid", "descubrimiento")
    r3 = r1.model_copy(update={"id": "R-3", "prioridad": "P2", "ciudad": "Barcelona"})
    return PromptSet(prompts=[r1, prompt("R-2", "Barcelona", "decision"), r3])


def real_llm() -> FakeLLM:
    return FakeLLM(
        {
            "intake.v2": brief_real,
            "market.v1": market_real,
            "prompts.v1": prompts_real,
            "plan.v2": plan_from_findings,
            "write.v2": proposal_draft,
        },
        coste=COSTE_LLM,
    )


class PaidJudge(DetectionJudge):
    """Juez falso con coste: detección por reglas y una traza de pago por lote en el presupuesto."""

    name = "juez-falso"

    async def aevaluate_many(self, pairs: Any) -> list[Any]:
        out = await super().aevaluate_many(pairs)
        if pairs:
            self.traces[-1] = trace(pairs[0][0].study_id, "judge:falso", COSTE_JUEZ)
            if self.budget is not None:
                self.budget.record(self.traces[-1])
        return out


class Fakes:
    """Los clientes falsos del modo real y lo que han recibido."""

    def __init__(self) -> None:
        self.llm = real_llm()
        self.engines = [
            RealishEngine(name=f"fake:{m}", coste=COSTE_MOTOR, motor=m) for m in MOTORES
        ]
        self.marcas_motor: list[list[str]] = []
        self.guards: list[FakeGuard] = []

    def engine_factory(self, ids: list[str], _budget: Budget) -> list[Any]:
        self.marcas_motor.append(ids)
        return list(self.engines)

    def guard(self, budget: Budget) -> FakeGuard:
        self.guards.append(FakeGuard(budget, COSTE_GUARD))
        return self.guards[-1]


def build_runner(repo: SqlStudyRepo, fakes: Fakes, budget_max: float) -> StudyRunner:
    settings = kit_settings(llm_provider="fixture", real_max_prompts=2)
    deps = Deps(
        llm=fakes.llm,
        engines=[],
        judge_factory=PaidJudge,
        repo=repo,
        budget=lambda study_id: Budget(budget_max, study_id),
        settings=settings,
        engine_factory=fakes.engine_factory,
        plan_guard_factory=fakes.guard,
    )
    return StudyRunner({"real": deps}, InMemorySaver(serde=serializer()), repo)


@pytest.fixture(autouse=True)
def sin_red(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Cualquier conexión fuera de la máquina falla y queda apuntada. El bucle de asyncio en
    Windows usa un par de sockets en 127.0.0.1 (`socketpair`): el loopback se deja pasar."""
    intentos: list[Any] = []
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def externa(address: Any) -> bool:
        host = address[0] if isinstance(address, tuple) else address
        return host not in LOOPBACK

    def bloquea_connect(self: socket.socket, address: Any) -> None:
        if externa(address):
            intentos.append(address)
            raise OSError(f"red prohibida en el ensayo en seco: {address}")
        connect(self, address)

    def bloquea_connect_ex(self: socket.socket, address: Any) -> int:
        if externa(address):
            intentos.append(address)
            raise OSError(f"red prohibida en el ensayo en seco: {address}")
        return connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", bloquea_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", bloquea_connect_ex)
    return intentos


async def client_for(runner: StudyRunner) -> AsyncIterator[httpx.AsyncClient]:
    settings = kit_settings(auth_dev_codes=True, auth_scrypt_n=2**10)
    app = create_app(runner=runner, settings=settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await authenticate_async(c)
        yield c


async def create_real(client: httpx.AsyncClient) -> str:
    response = await client.post("/studies", json={"brief_texto": BRIEF, "modo": "real"})
    assert response.status_code == 201, response.text
    assert response.json()["aviso"] is None  # el aviso de caso sintético es solo del kit
    return str(response.json()["study_id"])


async def resume(client: httpx.AsyncClient, sid: str, revision: str) -> None:
    response = await client.post(
        f"/studies/{sid}/resume", json={"revision": revision, "payload": {"aprobado": True}}
    )
    assert response.status_code == 202, response.text


async def test_estudio_real_completo_con_trazas_de_coste_y_sin_red(
    repo: SqlStudyRepo, sin_red: list[Any]
) -> None:
    fakes = Fakes()
    async for client in client_for(build_runner(repo, fakes, budget_max=5.0)):
        sid = await create_real(client)
        view = (await client.get(f"/studies/{sid}")).json()
        assert view["estado"] == "esperando_revision_competidores", view["errores"]
        assert view["brief"]["marca"] == FOCO
        assert [m["id"] for m in view["market"]["marcas"]] == ["faro", "vision-norte", "lentes-sur"]

        await resume(client, sid, "competidores")
        view = (await client.get(f"/studies/{sid}")).json()
        assert view["estado"] == "esperando_revision_plan", view["errores"]
        assert view["metrics"]["study_id"] == sid and view["plan"]["study_id"] == sid
        assert view["calidad_plan"] is not None  # PlanGuard (falso) evaluó el plan

        await resume(client, sid, "plan")
        view = (await client.get(f"/studies/{sid}")).json()
        assert view["estado"] == "completado", view["errores"]
        assert view["proposal"]["study_id"] == sid
        assert not [e for e in view["errores"] if "presupuesto" in e]

        traces = [
            Trace.model_validate(t) for t in (await client.get(f"/studies/{sid}/traces")).json()
        ]

    # Motores: 2 prompts × 4 motores × 3 repeticiones, con el mercado confirmado.
    assert fakes.marcas_motor == [["faro", "vision-norte", "lentes-sur"]]
    for engine in fakes.engines:
        assert sorted(engine.calls) == [(p, r) for p in ("R-1", "R-2") for r in (1, 2, 3)]
    assert {"intake.v2", "market.v1", "prompts.v1", "plan.v2", "write.v2"} <= set(fakes.llm.names())
    assert len(fakes.guards) == 1 and len(fakes.guards[0].planes) == 1

    # Trazas: cada llamada de pago con su coste, y el coste del estudio es su suma.
    por_nodo: dict[str, list[Trace]] = {}
    for t in traces:
        assert t.study_id == sid and t.modelo and t.prompt_version and t.coste_eur >= 0
        por_nodo.setdefault(t.nodo.split(":")[0], []).append(t)
    assert len([t for t in traces if t.nodo.startswith("run:")]) == 24
    assert {t.coste_eur for t in por_nodo["run"]} == {COSTE_MOTOR}
    assert any(t.nodo == "judge:falso" and t.coste_eur == COSTE_JUEZ for t in traces)
    assert any(t.nodo == "plan_guard:fake" for t in traces)
    for nodo in ("intake.v2", "market.v1", "prompts.v1", "plan.v2", "write.v2"):
        assert any(t.nodo == nodo and t.coste_eur == COSTE_LLM for t in traces), nodo
    total = sum(t.coste_eur for t in traces)
    assert total >= 24 * COSTE_MOTOR + COSTE_JUEZ + COSTE_GUARD + 5 * COSTE_LLM - 1e-9
    assert view["coste_acumulado_eur"] == pytest.approx(total)
    assert total <= 5.0

    assert sin_red == []


async def test_el_presupuesto_corta_la_medicion_real(
    repo: SqlStudyRepo, sin_red: list[Any]
) -> None:
    fakes = Fakes()
    # Intake, mercado y prompts caben; los motores lo cruzan en cuanto se gastan ~0,05 €.
    async for client in client_for(build_runner(repo, fakes, budget_max=0.05)):
        sid = await create_real(client)
        await resume(client, sid, "competidores")
        view = (await client.get(f"/studies/{sid}")).json()
        traces = (await client.get(f"/studies/{sid}/traces")).json()

    lanzadas = sum(len(e.calls) for e in fakes.engines)
    assert 0 < lanzadas < 24  # no se agota la serie: el presupuesto la para antes
    assert view["estado"] == "error"
    textos = " ".join(view["errores"])
    assert "supera el máximo" in textos, view["errores"]
    # Lo ya gastado queda trazado, incluida la llamada que cruzó el límite. El tope se mira antes
    # de cada llamada, así que el exceso lo acotan las llamadas en vuelo (`CONCURRENCIA`).
    total = sum(t["coste_eur"] for t in traces)
    assert total > 0.05
    assert total <= 0.05 + CONCURRENCIA * COSTE_MOTOR + COSTE_JUEZ + 1e-9
    assert view["coste_acumulado_eur"] == pytest.approx(total)
    assert view["proposal"] is None
    assert sin_red == []

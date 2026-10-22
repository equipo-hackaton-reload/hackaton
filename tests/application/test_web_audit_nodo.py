"""Nodo `web_audit` (ADR 0019) con `FixtureWebFetcher`: CASO SINTÉTICO, sin red."""

from dataclasses import replace

import pytest

from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.adapters.web import FixtureWebFetcher
from posiq.application import nodes
from posiq.application.deps import Deps
from posiq.application.graph import PIPELINE, serializer
from posiq.application.nodes.analyze import hallazgos_tecnicos_del_plan
from posiq.application.state import StudyState
from posiq.domain.schemas import Market
from posiq.domain.web_audit_schemas import (
    CATALOGO,
    RECURSOS,
    AuditoriaWeb,
    Comprobacion,
    RespuestaWeb,
)
from tests.application.fakes import FakeLLM, kit_llm, make_deps
from tests.application.test_nodes import kit_state_until_judge, merge

pytestmark = pytest.mark.anyio

DOMINIO = "alboradavision.example"


class FetcherDePrueba:
    """Fetcher «no fixture» que sirve las mismas respuestas: simula una auditoría real sin red."""

    name = "prueba"

    def __init__(self) -> None:
        self._fixture = FixtureWebFetcher()
        self.urls: list[tuple[str, str | None]] = []

    def get(self, url: str, *, dominio: str, accept: str | None = None) -> RespuestaWeb:
        self.urls.append((url, accept))
        return self._fixture.get(url, dominio=dominio, accept=accept)


def _deps(repo: SqlStudyRepo, fetcher: object | None) -> Deps:
    return replace(make_deps(FakeLLM({}), [], repo), web_fetcher=fetcher)  # type: ignore[arg-type]


async def judged_state(repo: SqlStudyRepo) -> StudyState:
    state = await kit_state_until_judge(repo, n_prompts=25)
    return merge(state, await nodes.judge(state, make_deps(kit_llm(), [], repo)))


def test_web_audit_va_entre_judge_y_analyze_y_es_externo() -> None:
    orden = [name for name, _, _ in PIPELINE]
    assert orden[orden.index("judge") + 1 : orden.index("analyze")] == ["web_audit"]
    assert dict((n, ext) for n, _, ext in PIPELINE)["web_audit"] is True


async def test_apagada_no_descarga_nada(repo: SqlStudyRepo) -> None:
    state = await judged_state(repo)
    update = await nodes.web_audit(state, _deps(repo, None))
    assert update == {"auditoria_web": None, "hallazgos_web": None}


async def test_sin_dominio_no_descarga_nada(repo: SqlStudyRepo) -> None:
    state = await judged_state(repo)
    sin_dominio = [b.model_copy(update={"dominio": None}) for b in state["market"].marcas]
    state = merge(state, {"market": Market(marcas=sin_dominio, confirmado_por_humano=True)})
    fetcher = FetcherDePrueba()
    update = await nodes.web_audit(state, _deps(repo, fetcher))
    assert update["auditoria_web"] is None and fetcher.urls == []


async def test_en_kit_la_auditoria_es_fixture_y_no_entra_en_findings(repo: SqlStudyRepo) -> None:
    state = await judged_state(repo)
    update = await nodes.web_audit(state, _deps(repo, FixtureWebFetcher()))

    auditoria: AuditoriaWeb = update["auditoria_web"]
    assert auditoria.origen == "fixture" and auditoria.fetcher == "fixture"
    assert auditoria.dominio == DOMINIO and auditoria.version == "web_audit.v1"
    assert [c.id for c in auditoria.comprobaciones] == list(CATALOGO)
    assert auditoria.comprobacion("bots_ia_sin_bloqueo").estado == "falla"  # GPTBot bloqueado
    # 12 recursos fijos + 2 páginas del sitemap; el sitemap de robots.txt es el fijo (no se repite).
    assert len(auditoria.recursos) == len(RECURSOS) + 2
    hallazgos = update["hallazgos_web"]
    assert "F-web-bots-bloqueados" in {f.id for f in hallazgos}
    assert auditoria.finding_ids == [f.id for f in hallazgos]
    for f in hallazgos:
        assert f.evaluation_ids, f.id

    traces = update["traces"]
    assert len(traces) == len(auditoria.recursos)
    assert {(t.nodo, t.modelo, t.prompt_version) for t in traces} == {
        ("web_audit", "http:fixture", "web_audit.v1")
    }
    assert all(t.coste_eur == 0 and t.tokens_in == t.tokens_out == 0 for t in traces)
    assert update["coste_acumulado_eur"] == state["coste_acumulado_eur"]

    # El checkpointer la reconstruye entera (modelos de `web_audit_schemas` permitidos).
    s = serializer()
    vuelta = s.loads_typed(s.dumps_typed(auditoria))
    assert vuelta == auditoria and isinstance(vuelta.comprobaciones[0], Comprobacion)

    analizado = merge(state, update)
    assert hallazgos_tecnicos_del_plan(analizado) == []
    tras = await nodes.analyze(analizado, _deps(repo, None))
    assert not [f for f in tras["findings"] if f.id.startswith("F-web-")]


async def test_en_kit_un_fetcher_no_fixture_sigue_siendo_fixture(repo: SqlStudyRepo) -> None:
    """Regla de oro: nada del kit se presenta como real, venga del fetcher que venga."""
    state = await judged_state(repo)
    update = await nodes.web_audit(state, _deps(repo, FetcherDePrueba()))
    assert update["auditoria_web"].origen == "fixture"


async def test_en_real_los_hallazgos_entran_en_findings(repo: SqlStudyRepo) -> None:
    state = merge(await judged_state(repo), {"modo": "real"})
    fetcher = FetcherDePrueba()
    update = await nodes.web_audit(state, _deps(repo, fetcher))

    auditoria = update["auditoria_web"]
    assert auditoria.origen == "real" and auditoria.fetcher == "prueba"
    base = f"https://{DOMINIO}"
    assert (base + "/", "text/markdown") in fetcher.urls
    assert (base + "/robots.txt", None) in fetcher.urls
    assert all(url.startswith(base + "/") for url, _ in fetcher.urls)
    assert {t.modelo for t in update["traces"]} == {"http:prueba"}

    analizado = merge(state, update)
    tecnicos = hallazgos_tecnicos_del_plan(analizado)
    assert tecnicos == update["hallazgos_web"] and tecnicos
    tras = await nodes.analyze(analizado, _deps(repo, None))
    ids = [f.id for f in tras["findings"]]
    assert ids[-len(tecnicos) :] == [f.id for f in tecnicos]
    assert repo.get_findings(state["study_id"]) == tras["findings"]


def test_wiring_del_fetcher_segun_settings() -> None:
    from posiq.adapters.web import HttpxWebFetcher
    from posiq.interfaces.api.wiring import web_fetcher_for
    from tests.application.fakes import kit_settings

    assert kit_settings().web_audit == "off"
    assert web_fetcher_for("kit", kit_settings()) is None
    assert web_fetcher_for("real", kit_settings()) is None
    real = kit_settings(web_audit="real", web_audit_timeout_s=60)
    assert isinstance(web_fetcher_for("kit", real), FixtureWebFetcher)
    fetcher = web_fetcher_for("real", real)
    assert isinstance(fetcher, HttpxWebFetcher) and fetcher.timeout_total_s == 10.0
    corto = web_fetcher_for("real", kit_settings(web_audit="real", web_audit_timeout_s=3))
    assert isinstance(corto, HttpxWebFetcher) and corto.timeout_total_s == 3
    assert isinstance(web_fetcher_for("real", kit_settings(web_audit="fixture")), FixtureWebFetcher)

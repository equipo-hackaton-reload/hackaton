"""Motores reales con cada SDK simulado: fuentes, sin búsqueda, 429 y clave ausente."""

import logging
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest
from google.genai import errors as genai_errors
from openai.types.chat import ChatCompletion

from posiq.adapters.budget import Budget, BudgetExceeded
from posiq.adapters.cache import DiskCache
from posiq.adapters.engines import (
    AnthropicEngine,
    GeminiEngine,
    KitEngine,
    OpenAIEngine,
    PerplexityEngine,
    RealEngine,
    build_engines,
)
from posiq.adapters.engines.base import domain_of, load_catalog, resolve_sources
from posiq.adapters.engines.gemini import chunk_domain
from posiq.adapters.errors import MissingCredentialError
from posiq.domain.schemas import PromptInstance
from posiq.ports import Engine
from posiq.settings import Settings

MARCAS = ["alborada", "vistalia"]
TEXTO = "La mejor opción es Clínica Alborada Visión; también Vistalia."


@pytest.fixture
def settings(tmp_path: Path, kit_dir: Path) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        openai_api_key="sk-test",
        gemini_api_key="g-test",
        perplexity_api_key="pplx-test",
        anthropic_api_key="sk-ant-test",
        cache_enabled=False,
        cache_path=str(tmp_path / "cache.sqlite"),
        kit_dir=str(kit_dir),
        usd_eur=1.0,
    )


@pytest.fixture
def prompt() -> PromptInstance:
    return PromptInstance(
        id="OFT-DG-01-01",
        template_id="OFT-DG-01",
        familia="Descubrimiento genérico",
        fase_embudo="descubrimiento",
        instanciacion="generico",
        texto="¿Cuál es la mejor clínica de cirugía refractiva en Madrid?",
        prioridad="P1",
    )


class Scripted:
    """`create` falso: devuelve (o lanza) cada resultado en orden y guarda los kwargs."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        out = self.outcomes.pop(0)
        if isinstance(out, BaseException):
            raise out
        return out


# --- Respuestas simuladas de cada SDK -------------------------------------------------------------


def openai_response(urls: list[str]) -> Any:
    output: list[Any] = [NS(type="web_search_call")] if urls else []
    annotations = [NS(type="url_citation", url=u) for u in urls]
    output.append(
        NS(type="message", content=[NS(type="output_text", text=TEXTO, annotations=annotations)])
    )
    return NS(
        output=output,
        output_text=TEXTO,
        model="gpt-5-mini-2026-01-01",
        usage=NS(input_tokens=1000, output_tokens=500),
    )


def gemini_response(urls: list[str]) -> Any:
    chunks = [NS(web=NS(domain=None, uri=u, title=None)) for u in urls]
    metadata = NS(grounding_chunks=chunks, web_search_queries=["clínica"] if urls else [])
    return NS(
        text=TEXTO,
        candidates=[NS(grounding_metadata=metadata if urls else None)],
        model_version="gemini-2.5-flash",
        usage_metadata=NS(
            prompt_token_count=1000, candidates_token_count=400, thoughts_token_count=100
        ),
    )


def perplexity_response(urls: list[str]) -> Any:
    return ChatCompletion.model_validate(
        {
            "id": "pplx-1",
            "object": "chat.completion",
            "created": 0,
            "model": "sonar",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": TEXTO},
                }
            ],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
            "citations": urls,
            "search_results": [{"url": u, "title": "t"} for u in urls],
        }
    )


def anthropic_response(
    urls: list[str],
    stop_reason: str = "end_turn",
    texto: str = TEXTO,
    vistas: list[str] | None = None,
) -> Any:
    """Respuesta de Claude que cita `urls`; `vistas` son resultados de búsqueda extra sin citar."""
    resultados = urls + (vistas or [])
    content: list[Any] = []
    if resultados:
        content += [
            NS(type="server_tool_use", name="web_search"),
            NS(
                type="web_search_tool_result",
                content=[NS(type="web_search_result", url=u, title="t") for u in resultados],
            ),
        ]
    citations = [
        NS(type="web_search_result_location", url=u, title="t", cited_text="…") for u in urls
    ]
    content.append(NS(type="text", text=texto, citations=citations or None))
    return NS(
        content=content,
        stop_reason=stop_reason,
        model="claude-opus-5-5",
        usage=NS(
            input_tokens=1000,
            output_tokens=500,
            server_tool_use=NS(web_search_requests=1 if resultados else 0),
        ),
    )


def openai_429() -> Exception:
    request = httpx.Request("POST", "https://api.example/v1")
    return openai.RateLimitError("rate", response=httpx.Response(429, request=request), body=None)


def anthropic_429() -> Exception:
    request = httpx2.Request("POST", "https://api.example/v1")
    return anthropic.RateLimitError(
        "rate", response=httpx2.Response(429, request=request), body=None
    )


def gemini_429() -> Exception:
    return genai_errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )


def openai_client(create: Scripted) -> Any:
    return NS(responses=NS(create=create))


def gemini_client(create: Scripted) -> Any:
    return NS(models=NS(generate_content=create))


def perplexity_client(create: Scripted) -> Any:
    return NS(chat=NS(completions=NS(create=create)))


def anthropic_client(create: Scripted) -> Any:
    return NS(beta=NS(messages=NS(create=create)), messages=NS(create=create))


ENGINES: dict[str, tuple[type[RealEngine], Callable[..., Any], Callable[[Scripted], Any], Any]] = {
    "ChatGPT": (OpenAIEngine, openai_response, openai_client, openai_429),
    "Gemini": (GeminiEngine, gemini_response, gemini_client, gemini_429),
    "Perplexity": (PerplexityEngine, perplexity_response, perplexity_client, openai_429),
    "Claude": (AnthropicEngine, anthropic_response, anthropic_client, anthropic_429),
}
URLS = [
    "https://www.diariosalud.example/ranking-2026?utm_source=x",
    "https://es.wikipedia.org/wiki/Cirug%C3%ADa_refractiva",
    "https://desconocido.es/post",
    "https://diariosalud.example/otra",
]


def make(motor: str, settings: Settings, create: Scripted, **kw: Any) -> RealEngine:
    cls, _, client, _ = ENGINES[motor]
    sleeps: list[float] = kw.pop("sleeps", [])
    return cls(settings, MARCAS, client=client(create), sleep=sleeps.append, **kw)


# --- Tests comunes a los cuatro motores -----------------------------------------------------------


@pytest.mark.parametrize("motor", ENGINES)
def test_respuesta_con_fuentes(motor: str, settings: Settings, prompt: PromptInstance) -> None:
    _, response, _, _ = ENGINES[motor]
    engine = make(motor, settings, Scripted(response(URLS)))
    engine_port: Engine = engine
    run = engine_port.ask(prompt, repeticion=2, study_id="S-1")

    assert engine.name == motor and run.motor == motor
    assert (run.study_id, run.prompt_id, run.repeticion) == ("S-1", prompt.id, 2)
    assert run.origen == "api" and run.marcas_a_evaluar == MARCAS
    assert run.texto_respuesta == TEXTO and run.modelo
    assert run.tokens == 1500
    assert [(s.dominio, s.tipo) for s in run.fuentes] == [
        ("diariosalud.example", "Medio"),
        ("es.wikipedia.org", "Ranking / institución"),
        ("desconocido.es", None),
    ]
    assert run.coste_eur > 0


@pytest.mark.parametrize("motor", ENGINES)
def test_sin_busqueda_no_es_error(
    motor: str, settings: Settings, prompt: PromptInstance, caplog: pytest.LogCaptureFixture
) -> None:
    _, response, _, _ = ENGINES[motor]
    engine = make(motor, settings, Scripted(response([])))
    with caplog.at_level(logging.INFO):
        run = engine.ask(prompt, repeticion=1, study_id="S-1")
    assert run.fuentes == [] and run.texto_respuesta == TEXTO
    assert "sin fuentes" in caplog.text


@pytest.mark.parametrize("motor", ENGINES)
def test_429_reintenta_con_espera(motor: str, settings: Settings, prompt: PromptInstance) -> None:
    _, response, _, error = ENGINES[motor]
    create = Scripted(error(), error(), response(URLS))
    sleeps: list[float] = []
    run = make(motor, settings, create, sleeps=sleeps).ask(prompt, repeticion=1, study_id="S-1")
    assert len(create.calls) == 3 and run.fuentes
    assert len(sleeps) == 2 and sleeps[1] >= 2 * settings.engine_backoff_base_s


@pytest.mark.parametrize("motor", ENGINES)
def test_429_agota_reintentos(motor: str, settings: Settings, prompt: PromptInstance) -> None:
    _, _, _, error = ENGINES[motor]
    attempts = settings.engine_max_retries + 1
    create = Scripted(*[error() for _ in range(attempts)])
    with pytest.raises(Exception) as exc:
        make(motor, settings, create).ask(prompt, repeticion=1, study_id="S-1")
    assert len(create.calls) == attempts
    assert getattr(exc.value, "status_code", getattr(exc.value, "code", None)) == 429


@pytest.mark.parametrize("motor", ENGINES)
def test_clave_ausente_falla_al_llamar(
    motor: str, tmp_path: Path, prompt: PromptInstance, monkeypatch: pytest.MonkeyPatch
) -> None:
    cls, _, _, _ = ENGINES[motor]
    monkeypatch.delenv(cls.key_variable, raising=False)
    sin_claves = Settings(_env_file=None, cache_enabled=False)  # type: ignore[call-arg]
    engine = cls(sin_claves, MARCAS)
    assert not engine.has_key
    with pytest.raises(MissingCredentialError, match=cls.key_variable) as exc:
        engine.ask(prompt, repeticion=1, study_id="S-1")
    assert exc.value.variable == cls.key_variable
    assert f"motor {motor}" in str(exc.value)


@pytest.mark.parametrize("motor", ENGINES)
def test_cache_evita_la_segunda_llamada(
    motor: str, settings: Settings, prompt: PromptInstance, tmp_path: Path
) -> None:
    _, response, _, _ = ENGINES[motor]
    cache = DiskCache(tmp_path / "engines.sqlite")
    create = Scripted(response(URLS), response([]))
    engine = make(motor, settings, create, cache=cache)
    first = engine.ask(prompt, repeticion=1, study_id="S-1")
    again = engine.ask(prompt, repeticion=1, study_id="S-2")
    assert len(create.calls) == 1
    assert again.study_id == "S-2" and again.fuentes == first.fuentes
    assert again.fecha == first.fecha and again.coste_eur == 0.0
    engine.ask(prompt, repeticion=2, study_id="S-1")
    assert len(create.calls) == 2


def test_error_400_no_se_reintenta(settings: Settings, prompt: PromptInstance) -> None:
    request = httpx.Request("POST", "https://api.example/v1")
    bad = openai.BadRequestError("bad", response=httpx.Response(400, request=request), body=None)
    create = Scripted(bad)
    with pytest.raises(openai.BadRequestError):
        make("ChatGPT", settings, create).ask(prompt, repeticion=1, study_id="S-1")
    assert len(create.calls) == 1


def test_error_de_red_se_reintenta(settings: Settings, prompt: PromptInstance) -> None:
    error = openai.APIConnectionError(request=httpx.Request("POST", "https://api.example/v1"))
    create = Scripted(error, openai_response([]))
    make("ChatGPT", settings, create).ask(prompt, repeticion=1, study_id="S-1")
    assert len(create.calls) == 2


# --- Coste y presupuesto --------------------------------------------------------------------------


def test_coste_con_precios_de_settings(settings: Settings, prompt: PromptInstance) -> None:
    run = make("Claude", settings, Scripted(anthropic_response(URLS))).ask(
        prompt, repeticion=1, study_id="S-1"
    )
    esperado = 1000 * 4.0 / 1e6 + 500 * 20.0 / 1e6 + 1 * 0.01
    assert run.coste_eur == pytest.approx(esperado)


def test_budget_registra_traza_y_corta(settings: Settings, prompt: PromptInstance) -> None:
    budget = Budget(max_eur=0.001, study_id="S-1")
    create = Scripted(openai_response(URLS), openai_response(URLS))
    engine = make("ChatGPT", settings, create, budget=budget)
    with pytest.raises(BudgetExceeded):
        engine.ask(prompt, repeticion=1, study_id="S-1")
    trace = budget.traces[0]
    assert (trace.nodo, trace.prompt_version) == ("engine:ChatGPT", prompt.id)
    assert (trace.tokens_in, trace.tokens_out) == (1000, 500)
    with pytest.raises(BudgetExceeded, match="presupuesto agotado"):
        engine.ask(prompt, repeticion=2, study_id="S-1")
    assert len(create.calls) == 1


def test_ask_many_devuelve_runs_y_errores_en_orden(
    settings: Settings, prompt: PromptInstance
) -> None:
    request = httpx.Request("POST", "https://api.example/v1")
    bad = openai.BadRequestError("bad", response=httpx.Response(400, request=request), body=None)
    engine = make("ChatGPT", settings, Scripted(bad, openai_response(URLS)))
    engine.concurrency = 1
    out = engine.ask_many([prompt], repeticiones=2, study_id="S-1")
    assert isinstance(out[0], openai.BadRequestError)
    assert not isinstance(out[1], BaseException) and out[1].repeticion == 2


# --- Detalles de cada proveedor -------------------------------------------------------------------


def test_openai_activa_web_search(settings: Settings, prompt: PromptInstance) -> None:
    create = Scripted(openai_response(URLS))
    make("ChatGPT", settings, create).ask(prompt, repeticion=1, study_id="S-1")
    assert create.calls[0]["tools"] == [{"type": "web_search"}]
    assert create.calls[0]["input"] == prompt.texto


def test_gemini_activa_google_search_y_resuelve_redirecciones(
    settings: Settings, prompt: PromptInstance
) -> None:
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbC"
    response = gemini_response([])
    response.candidates[0].grounding_metadata = NS(
        grounding_chunks=[
            NS(web=NS(domain=None, uri=redirect, title="diariosalud.example")),
            NS(web=NS(domain="reddit.com", uri=redirect, title="Reddit")),
        ],
        web_search_queries=["mejor clínica"],
    )
    create = Scripted(response)
    run = make("Gemini", settings, create).ask(prompt, repeticion=1, study_id="S-1")
    assert [s.dominio for s in run.fuentes] == ["diariosalud.example", "reddit.com"]
    tool = create.calls[0]["config"].tools[0]
    assert tool.google_search is not None


def test_perplexity_usa_search_results_si_no_hay_citations(
    settings: Settings, prompt: PromptInstance
) -> None:
    response = perplexity_response(URLS)
    response.citations = None  # type: ignore[attr-defined]
    run = make("Perplexity", settings, Scripted(response)).ask(prompt, repeticion=1, study_id="S")
    assert [s.dominio for s in run.fuentes][0] == "diariosalud.example"


def test_claude_continua_tras_pause_turn(settings: Settings, prompt: PromptInstance) -> None:
    paused = anthropic_response(URLS[:1], stop_reason="pause_turn", texto="Busco… ")
    final = anthropic_response(URLS[2:3], texto="Respuesta final.")
    create = Scripted(paused, final)
    run = make("Claude", settings, create).ask(prompt, repeticion=1, study_id="S-1")
    assert len(create.calls) == 2
    segundo = create.calls[1]["messages"]
    assert segundo[-1] == {"role": "assistant", "content": paused.content}
    assert len(segundo) == 2  # sin un «continúa» añadido por nosotros
    assert run.texto_respuesta == "Busco… Respuesta final."
    assert [s.dominio for s in run.fuentes] == ["diariosalud.example", "desconocido.es"]
    assert run.tokens == 3000


def test_claude_declara_web_search_y_error_de_herramienta(
    settings: Settings, prompt: PromptInstance, caplog: pytest.LogCaptureFixture
) -> None:
    response = anthropic_response([])
    response.content.insert(
        0, NS(type="web_search_tool_result", content=NS(error_code="max_uses_exceeded"))
    )
    create = Scripted(response)
    with caplog.at_level(logging.WARNING):
        run = make("Claude", settings, create).ask(prompt, repeticion=1, study_id="S-1")
    assert run.fuentes == [] and "max_uses_exceeded" in caplog.text
    tool = create.calls[0]["tools"][0]
    assert tool["name"] == "web_search" and tool["max_uses"] == 5
    assert tool["type"] == "web_search_20260209"


def test_claude_haiku_usa_web_search_basico(settings: Settings) -> None:
    haiku = settings.model_copy(update={"anthropic_engine_model": "claude-haiku-5-5"})
    assert AnthropicEngine(haiku, MARCAS).tool["type"] == "web_search_20250305"


def test_claude_solo_cuenta_fuentes_citadas(settings: Settings, prompt: PromptInstance) -> None:
    response = anthropic_response(URLS[:1], vistas=["https://reddit.com/r/x", URLS[2]])
    response.content[-1].citations.append(NS(type="char_location", cited_text="x"))
    run = make("Claude", settings, Scripted(response)).ask(prompt, repeticion=1, study_id="S-1")
    assert [s.dominio for s in run.fuentes] == ["diariosalud.example"]


def test_claude_busco_sin_citar(
    settings: Settings, prompt: PromptInstance, caplog: pytest.LogCaptureFixture
) -> None:
    response = anthropic_response([], vistas=URLS)
    with caplog.at_level(logging.INFO):
        run = make("Claude", settings, Scripted(response)).ask(prompt, repeticion=1, study_id="S")
    assert run.fuentes == []
    assert "busco_sin_citar=True" in caplog.text
    assert run.coste_eur == pytest.approx(1000 * 4.0 / 1e6 + 500 * 20.0 / 1e6 + 0.01)


def test_claude_sin_fallback_por_defecto(settings: Settings, prompt: PromptInstance) -> None:
    assert settings.anthropic_engine_fallback is False
    create = Scripted(anthropic_response(URLS))
    make("Claude", settings, create).ask(prompt, repeticion=1, study_id="S-1")
    assert "fallbacks" not in create.calls[0] and "betas" not in create.calls[0]


def test_claude_fallback_opt_in_registra_el_modelo(
    settings: Settings, prompt: PromptInstance, caplog: pytest.LogCaptureFixture
) -> None:
    con_fallback = settings.model_copy(update={"anthropic_engine_fallback": True})
    response = anthropic_response(URLS)
    response.model = "claude-opus-4-8"
    create = Scripted(response)
    with caplog.at_level(logging.WARNING):
        run = make("Claude", con_fallback, create).ask(prompt, repeticion=1, study_id="S-1")
    assert create.calls[0]["fallbacks"] == "default"
    assert create.calls[0]["betas"] == ["server-side-fallback-2026-07-01"]
    assert run.modelo == "claude-opus-4-8" and "fallback" in caplog.text


def test_claude_haiku_ignora_el_fallback(settings: Settings) -> None:
    haiku = settings.model_copy(
        update={"anthropic_engine_model": "claude-haiku-5-5", "anthropic_engine_fallback": True}
    )
    assert AnthropicEngine(haiku, MARCAS).fallback is False


# --- Fuentes --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "dominio"),
    [
        ("https://www.Reddit.com/r/x", "reddit.com"),
        ("diariosalud.example", "diariosalud.example"),
        ("http://sub.medio.es:8080/a", "sub.medio.es"),
        ("", None),
        ("Reddit", None),
    ],
)
def test_domain_of(raw: str, dominio: str | None) -> None:
    assert domain_of(raw) == dominio


def test_resolve_sources_hereda_del_dominio_padre(kit_dir: Path) -> None:
    catalog = load_catalog(str(kit_dir.resolve()))
    fuentes = resolve_sources(["https://m.youtube.com/watch", "https://maps.google.com/x"], catalog)
    assert [(f.dominio, f.tipo) for f in fuentes] == [
        ("m.youtube.com", "Red social / foro"),
        ("maps.google.com", "Plataforma de reseñas"),
    ]


def test_chunk_domain_sin_titulo_ni_dominio() -> None:
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbC"
    assert chunk_domain(NS(domain=None, uri=redirect, title=None)) is None
    assert chunk_domain(NS(domain=None, uri="https://medio.es/a", title=None)) == "medio.es"


# --- build_engines --------------------------------------------------------------------------------


def test_build_engines_kit(settings: Settings) -> None:
    engines = build_engines(settings, "kit")
    assert [e.name for e in engines] == [
        "kit:ChatGPT",
        "kit:Gemini",
        "kit:Perplexity",
        "kit:Claude",
    ]
    assert all(isinstance(e, KitEngine) for e in engines)


def test_build_engines_real_con_todas_las_claves(settings: Settings) -> None:
    engines = build_engines(settings, "real", MARCAS)
    assert [e.name for e in engines] == ["ChatGPT", "Gemini", "Perplexity", "Claude"]


def test_build_engines_real_avisa_de_las_claves_que_faltan(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    parcial = settings.model_copy(update={"gemini_api_key": settings.gemini_api_key.__class__("")})
    parcial = parcial.model_copy(update={"anthropic_api_key": parcial.gemini_api_key})
    with caplog.at_level(logging.WARNING):
        engines = build_engines(parcial, "real", MARCAS)
    assert [e.name for e in engines] == ["ChatGPT", "Perplexity"]
    assert "GEMINI_API_KEY" in caplog.text and "ANTHROPIC_API_KEY" in caplog.text


def test_build_engines_real_exige_marcas(settings: Settings) -> None:
    with pytest.raises(ValueError, match="marca"):
        build_engines(settings, "real")

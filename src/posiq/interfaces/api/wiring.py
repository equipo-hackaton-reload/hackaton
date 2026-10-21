"""Raíz de composición: construye `Deps` y el `StudyRunner` reales a partir de `Settings`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.engines import build_engines
from posiq.adapters.judge import build_judge
from posiq.adapters.judge.plan_guard import build_plan_guard
from posiq.adapters.llm.fixture import FixtureJudge, FixtureLLM
from posiq.adapters.llm.openai_compat import OpenAICompatLLM
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.deps import AsyncJudge, Deps, JudgeFactory, PlanGuardFactory
from posiq.application.graph import sqlite_checkpointer
from posiq.application.runner import StudyRunner
from posiq.domain.schemas import Market, ModoEstudio
from posiq.ports import Engine
from posiq.settings import Settings


def judge_factory(settings: Settings, cache: DiskCache) -> JudgeFactory:
    def factory(market: Market, budget: Budget) -> AsyncJudge:
        if (
            settings.llm_provider == "fixture"
            and not settings.typesafe_api_key.get_secret_value()
            and not settings.deepseek_api_key.get_secret_value()
        ):
            return FixtureJudge(market, kit_dir=settings.kit_dir)
        return build_judge(settings, market.marcas, budget=budget, cache=cache)

    return factory


def plan_guard_factory(settings: Settings, cache: DiskCache) -> PlanGuardFactory | None:
    """PlanGuard sobre el juez de `build_judge`; None sin claves de juez (no se evalúa el plan)."""
    if (
        not settings.typesafe_api_key.get_secret_value()
        and not settings.deepseek_api_key.get_secret_value()
    ):
        return None
    return lambda budget: build_plan_guard(settings, budget=budget, cache=cache)


def engines_for(modo: ModoEstudio, settings: Settings) -> list[Engine]:
    """El kit se prepara al arrancar; los motores reales esperan al mercado confirmado."""
    return build_engines(settings, modo) if modo == "kit" else []


def build_deps(settings: Settings, repo: SqlStudyRepo) -> dict[ModoEstudio, Deps]:
    cache = DiskCache.from_settings(settings)
    llm = (
        FixtureLLM(settings)
        if settings.llm_provider == "fixture"
        else OpenAICompatLLM(settings, cache=cache)
    )
    modos: tuple[ModoEstudio, ...] = ("kit", "real")
    return {
        modo: Deps(
            llm=llm,
            engines=engines_for(modo, settings),
            judge_factory=judge_factory(settings, cache),
            repo=repo,
            budget=lambda study_id: Budget.from_settings(settings, study_id),
            settings=settings,
            engine_factory=(
                lambda ids, budget: build_engines(settings, "real", ids, cache=cache, budget=budget)
            )
            if modo == "real"
            else None,
            plan_guard_factory=plan_guard_factory(settings, cache),
        )
        for modo in modos
    }


@asynccontextmanager
async def runner_from_settings(settings: Settings) -> AsyncIterator[StudyRunner]:
    repo = SqlStudyRepo(settings.database_url)
    async with sqlite_checkpointer(settings.database_url) as checkpointer:
        yield StudyRunner(build_deps(settings, repo), checkpointer, repo)

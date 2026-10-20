"""Raíz de composición: construye `Deps` y el `StudyRunner` reales a partir de `Settings`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.engines.kit import KitEngine
from posiq.adapters.judge import build_judge
from posiq.adapters.llm.openai_compat import OpenAICompatLLM
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.deps import AsyncJudge, Deps, JudgeFactory
from posiq.application.graph import sqlite_checkpointer
from posiq.application.runner import StudyRunner
from posiq.domain.schemas import Market, ModoEstudio
from posiq.ports import Engine
from posiq.settings import Settings


def judge_factory(settings: Settings, cache: DiskCache) -> JudgeFactory:
    def factory(market: Market, budget: Budget) -> AsyncJudge:
        return build_judge(settings, market.marcas, budget=budget, cache=cache)

    return factory


def engines_for(modo: ModoEstudio, settings: Settings) -> list[Engine]:
    """Motores del kit en modo kit. Los motores reales aún no están en develop (Zona B)."""
    return list(KitEngine.from_settings(settings)) if modo == "kit" else []


def build_deps(settings: Settings, repo: SqlStudyRepo) -> dict[ModoEstudio, Deps]:
    cache = DiskCache.from_settings(settings)
    llm = OpenAICompatLLM(settings, cache=cache)
    modos: tuple[ModoEstudio, ...] = ("kit", "real")
    return {
        modo: Deps(
            llm=llm,
            engines=engines_for(modo, settings),
            judge_factory=judge_factory(settings, cache),
            repo=repo,
            budget=lambda study_id: Budget.from_settings(settings, study_id),
            settings=settings,
        )
        for modo in modos
    }


@asynccontextmanager
async def runner_from_settings(settings: Settings) -> AsyncIterator[StudyRunner]:
    repo = SqlStudyRepo(settings.database_url)
    async with sqlite_checkpointer(settings.database_url) as checkpointer:
        yield StudyRunner(build_deps(settings, repo), checkpointer, repo)

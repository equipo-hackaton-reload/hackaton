"""Evaluación de la calidad del plan con el juez System One (Nivel 3, N3.5).

`PlanGuard` reutiliza un juez (Jev con fallback, o el LLM): mismo cliente, caché, trazas y
presupuesto. Hace una llamada por acción con `PLAN_QUESTIONS`. Si la confianza de una acción queda
por debajo del umbral de fallback y el juez tiene fallback, se repregunta al fallback.

No bloquea nada: devuelve un `PlanQuality` que el nodo `plan` y la web muestran junto a la
revisión humana.
"""

import asyncio
from collections.abc import Sequence
from typing import Any

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.judge import build_judge
from posiq.adapters.judge.base import SystemOneJudge
from posiq.domain.plan_questions import (
    PLAN_QUESTIONS,
    PLAN_QUESTIONS_VERSION,
    answers_to_quality,
    build_action_state,
    summarize_plan_quality,
)
from posiq.domain.quality_schemas import ActionQuality, PlanQuality
from posiq.domain.schemas import Action, BriefSummary, Finding, Plan
from posiq.settings import Settings

VERSION = f"plan_questions@{PLAN_QUESTIONS_VERSION}"


class PlanGuard:
    def __init__(self, judge: SystemOneJudge) -> None:
        self.judge = judge
        self.name = f"plan_guard:{judge.name}"

    def assess(self, plan: Plan, findings: Sequence[Finding], brief: BriefSummary) -> PlanQuality:
        """Versión síncrona de `aassess` (no usar dentro de un bucle de eventos en marcha)."""
        return asyncio.run(self.aassess(plan, findings, brief))

    async def aassess(
        self, plan: Plan, findings: Sequence[Finding], brief: BriefSummary
    ) -> PlanQuality:
        semaphore = asyncio.Semaphore(self.judge.concurrency)
        async with self.judge._session() as client:

            async def one(action: Action) -> ActionQuality:
                async with semaphore:
                    return await self._assess_action(plan.study_id, action, findings, brief, client)

            qualities = await asyncio.gather(*(one(a) for a in plan.acciones))
        return summarize_plan_quality(plan.study_id, qualities, self.judge.name, self.judge.model)

    async def _assess_action(
        self,
        study_id: str,
        action: Action,
        findings: Sequence[Finding],
        brief: BriefSummary,
        client: Any,
    ) -> ActionQuality:
        state = build_action_state(action, findings, brief)
        quality = await self._ask(self.judge, study_id, state, action.id, client)
        fallback = self.judge.fallback
        if quality.confianza < self.judge.fallback_threshold and fallback is not None:
            quality = await self._ask(fallback, study_id, state, action.id, None)
        return quality

    @staticmethod
    async def _ask(
        judge: SystemOneJudge, study_id: str, state: dict[str, Any], action_id: str, client: Any
    ) -> ActionQuality:
        answers = await judge.ask(
            study_id,
            state,
            questions=PLAN_QUESTIONS,
            version=VERSION,
            nodo=f"plan_guard:{judge.name}",
            client=client,
        )
        return answers_to_quality(answers, action_id)


def build_plan_guard(
    settings: Settings, *, budget: Budget | None = None, cache: DiskCache | None = None
) -> PlanGuard:
    """`PlanGuard` sobre el juez de `build_judge` (Jev con fallback, o solo el LLM)."""
    return PlanGuard(build_judge(settings, budget=budget, cache=cache))

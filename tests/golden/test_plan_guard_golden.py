"""Calidad del plan de ejemplo con el juez real: solo corre si hay TYPESAFE_API_KEY."""

import pytest

from posiq.adapters.budget import Budget
from posiq.adapters.judge.plan_guard import build_plan_guard
from posiq.domain.schemas import BriefSummary, Finding, Metrics, Plan
from posiq.settings import Settings
from tests.golden.conftest import STUDY_ID

SETTINGS = Settings()


@pytest.mark.skipif(not SETTINGS.typesafe_api_key.get_secret_value(), reason="sin TYPESAFE_API_KEY")
def test_calidad_del_plan_de_ejemplo(
    alborada_study: tuple[Metrics, list[Finding], Plan], alborada_brief: BriefSummary
) -> None:
    _, findings, plan = alborada_study
    guard = build_plan_guard(SETTINGS, budget=Budget.from_settings(SETTINGS, STUDY_ID))
    quality = guard.assess(plan, findings, alborada_brief)
    print(quality.model_dump_json(indent=2))
    assert len(quality.acciones) == len(plan.acciones)
    assert quality.pct_respetan_restricciones is not None

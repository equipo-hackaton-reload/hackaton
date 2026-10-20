"""Calibración del juez con red: solo corre si hay TYPESAFE_API_KEY (en entorno o .env)."""

import pytest

from posiq.adapters.budget import Budget
from posiq.adapters.judge import JevJudge
from posiq.adapters.judge.calibration import calibrate, render_markdown
from posiq.settings import Settings
from tests.golden.conftest import STUDY_ID, Kit

SETTINGS = Settings()
MIN_APARECE = 0.9
MIN_TIPO_MENCION = 0.8


@pytest.mark.skipif(not SETTINGS.typesafe_api_key.get_secret_value(), reason="sin TYPESAFE_API_KEY")
def test_calibracion_jev(kit: Kit) -> None:
    judge = JevJudge(SETTINGS, kit.brands, budget=Budget.from_settings(SETTINGS, STUDY_ID))
    report = calibrate(judge, kit.sample, kit.runs, kit.brands)
    print(render_markdown(report))
    assert report.total.aparece is not None and report.total.aparece >= MIN_APARECE
    assert report.total.tipo_mencion is not None and report.total.tipo_mencion >= MIN_TIPO_MENCION

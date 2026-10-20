"""Nodo `analyze`: métricas y hallazgos del dominio; sin LLM.

Si la marca tiene una medición anterior, las métricas se marcan `comparado_con` y se calcula la
diferencia (`diff_metrics`) para la re-medición.
"""

from pathlib import Path
from typing import Any

from posiq.application.deps import Deps, db
from posiq.application.kit import load_sources
from posiq.application.state import StudyState
from posiq.domain.findings import detect_findings
from posiq.domain.metrics import compute_metrics, diff_metrics


async def analyze(state: StudyState, deps: Deps) -> dict[str, Any]:
    sid = state["study_id"]
    study = await db(deps.repo.get_study, sid)
    anterior = await db(deps.repo.latest_metrics, study.brand_id, before=study.creado_en)
    metrics = compute_metrics(
        state["brief"],
        state["market"],
        state["prompts"],
        state["runs"],
        state["evaluations"],
        load_sources(str(Path(deps.settings.kit_dir).resolve())),
        sid,
        comparado_con=anterior.study_id if anterior else None,
    )
    delta = diff_metrics(metrics, anterior) if anterior else None
    findings = detect_findings(metrics, state["brief"])

    await db(deps.repo.save_metrics, sid, metrics, delta)
    await db(deps.repo.save_findings, sid, findings)
    return {"metrics": metrics, "metrics_delta": delta, "findings": findings}

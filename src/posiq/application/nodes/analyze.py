"""Nodo `analyze`: métricas y hallazgos del dominio; sin LLM.

En una re-medición (`medicion_anterior`, sembrada por `prepare_remeasure`), las métricas se marcan
`comparado_con` el estudio re-medido y se calcula la diferencia (`diff_metrics`). Un estudio nuevo
es una línea base: no se compara con otros estudios de la misma marca, que pueden ser de otro
usuario (ADR 0015) o de otra configuración.

Los hallazgos técnicos de la auditoría web (nodo `web_audit`, ADR 0019) se suman a los de
`detect_findings` solo si la auditoría es `origen="real"`: así el plan puede cubrirlos con la
palanca `tecnico`. Los de una auditoría fixture (CASO SINTÉTICO) se quedan en `hallazgos_web`,
fuera del plan, y los 7 hallazgos del golden no cambian.
"""

from pathlib import Path
from typing import Any

from posiq.application.deps import Deps, db
from posiq.application.kit import load_sources
from posiq.application.state import StudyState
from posiq.domain.findings import detect_findings
from posiq.domain.metrics import compute_metrics, diff_metrics
from posiq.domain.schemas import Finding


def hallazgos_tecnicos_del_plan(state: StudyState) -> list[Finding]:
    """Hallazgos técnicos que entran en `findings`: solo los de una auditoría web real."""
    auditoria = state.get("auditoria_web")
    if auditoria is None or auditoria.origen != "real":
        return []
    return list(state.get("hallazgos_web") or [])


async def analyze(state: StudyState, deps: Deps) -> dict[str, Any]:
    sid = state["study_id"]
    medicion_anterior = state.get("medicion_anterior")
    anterior = medicion_anterior["metrics"] if medicion_anterior else None
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
    findings = [*detect_findings(metrics, state["brief"]), *hallazgos_tecnicos_del_plan(state)]

    await db(deps.repo.save_metrics, sid, metrics, delta)
    await db(deps.repo.save_findings, sid, findings)
    return {"metrics": metrics, "metrics_delta": delta, "findings": findings}

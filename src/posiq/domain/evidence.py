"""Cobertura de evidencia del sistema: cada cifra y cada acción deben poder rastrearse.

- Un hallazgo tiene evidencia válida si TODOS sus `evaluation_ids` existen entre las evaluaciones
  del estudio (y hay al menos uno).
- Una acción está justificada si TODOS sus `finding_ids` existen entre los hallazgos válidos.
"""

from collections.abc import Sequence

from posiq.domain.quality_schemas import EvidenceCoverage
from posiq.domain.schemas import Evaluation, Finding, Plan


def _pct(ok: int, total: int) -> float | None:
    return ok / total if total else None


def evidence_coverage(
    findings: Sequence[Finding], plan: Plan | None, evaluations: Sequence[Evaluation]
) -> EvidenceCoverage:
    eval_ids = {e.id for e in evaluations}
    validos = {f.id for f in findings if f.evaluation_ids and set(f.evaluation_ids) <= eval_ids}
    acciones = plan.acciones if plan else []
    justificadas = {a.id for a in acciones if a.finding_ids and set(a.finding_ids) <= validos}
    return EvidenceCoverage(
        n_hallazgos=len(findings),
        hallazgos_con_evidencia=len(validos),
        pct_hallazgos=_pct(len(validos), len(findings)),
        n_acciones=len(acciones),
        acciones_con_hallazgos=len(justificadas),
        pct_acciones=_pct(len(justificadas), len(acciones)),
        hallazgos_sin_evidencia=[f.id for f in findings if f.id not in validos],
        acciones_sin_hallazgos=[a.id for a in acciones if a.id not in justificadas],
    )

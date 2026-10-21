"""Evaluación de calidad del propio sistema (Nivel 3, N3.5) sobre un estudio ya ejecutado.

Uso:
    uv run python scripts/evaluate_system.py [--study estudio.json] [--out docs/evaluacion]
                                             [--no-plan-guard]

Sin `--study`, usa el estudio del kit de Alborada con el plan de ejemplo de los fixtures
(`tests/golden/conftest.py`). Con `--study`, un JSON con las claves: `study_id`, `brief`
(BriefSummary), `marcas` (Brand), `prompts` (PromptInstance), `runs`, `evaluations`, `sources`,
`plan` y, opcionalmente, `findings` (si faltan, se recalculan con las reglas del dominio).

Informa de: acuerdo del juez con la muestra humana (último informe de `docs/calibracion/`),
cobertura de evidencia, calidad del plan según PlanGuard (si hay claves) y simulación del plan.
Guarda `docs/evaluacion/<fecha>.md`.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from posiq.adapters.errors import MissingCredentialError  # noqa: E402
from posiq.adapters.judge.plan_guard import build_plan_guard  # noqa: E402
from posiq.domain.evidence import evidence_coverage  # noqa: E402
from posiq.domain.findings import detect_findings  # noqa: E402
from posiq.domain.metrics import compute_metrics  # noqa: E402
from posiq.domain.quality_schemas import EvidenceCoverage, PlanQuality  # noqa: E402
from posiq.domain.schemas import (  # noqa: E402
    Brand,
    BriefSummary,
    Evaluation,
    Finding,
    Market,
    Metrics,
    Plan,
    PromptInstance,
    Run,
    Source,
)
from posiq.domain.simulation import simulate_plan  # noqa: E402
from posiq.domain.simulation_schemas import SimulationResult  # noqa: E402
from posiq.settings import Settings  # noqa: E402

Study = tuple[str, BriefSummary, Metrics, list[Finding], Plan, list[Evaluation]]


def study_from_fixtures() -> Study:
    from tests.golden.conftest import (
        STUDY_ID,
        alborada_brief_summary,
        alborada_metrics,
        example_plan,
        load_kit,
    )

    kit = load_kit()
    brief = alborada_brief_summary()
    metrics = alborada_metrics(kit, brief)
    findings = detect_findings(metrics, brief)
    return STUDY_ID, brief, metrics, findings, example_plan(findings, brief), kit.evaluations()


def study_from_json(path: Path) -> Study:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    study_id = str(data["study_id"])
    brief = BriefSummary.model_validate(data["brief"])
    market = Market(marcas=[Brand.model_validate(b) for b in data["marcas"]])
    evaluations = [Evaluation.model_validate(e) for e in data["evaluations"]]
    metrics = compute_metrics(
        brief,
        market,
        [PromptInstance.model_validate(p) for p in data["prompts"]],
        [Run.model_validate(r) for r in data["runs"]],
        evaluations,
        [Source.model_validate(s) for s in data["sources"]],
        study_id=study_id,
    )
    findings = (
        [Finding.model_validate(f) for f in data["findings"]]
        if "findings" in data
        else detect_findings(metrics, brief)
    )
    return study_id, brief, metrics, findings, Plan.model_validate(data["plan"]), evaluations


CALIBRATION_ROW = re.compile(r"^\| total \| (\d+) \| ([^|]+) \| (\d+) \| ([^|]+) \|", re.M)


def latest_calibration(directory: Path) -> tuple[str, str] | None:
    """(fichero, resumen) del último informe de calibración, o None si no hay ninguno."""
    reports = sorted(p for p in directory.glob("*.md") if p.name != "README.md")
    if not reports:
        return None
    match = CALIBRATION_ROW.search(reports[-1].read_text(encoding="utf-8"))
    if not match:
        return reports[-1].name, "formato no reconocido"
    n, aparece, n_mencion, tipo = (g.strip() for g in match.groups())
    return reports[-1].name, (
        f"{n} filas · acuerdo en aparece {aparece} · tipo de mención {tipo} ({n_mencion} filas)"
    )


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.0f} %"


def render(
    study_id: str,
    calibration: tuple[str, str] | None,
    coverage: EvidenceCoverage,
    quality: PlanQuality | str,
    simulation: SimulationResult,
) -> str:
    lines = [
        f"# Evaluación del sistema · {date.today().isoformat()} · estudio `{study_id}`",
        "",
        "## 1. Juez frente a la muestra humana",
        "",
        f"- {calibration[0]}: {calibration[1]}"
        if calibration
        else "- **PENDIENTE**: no hay informe de calibración real en `docs/calibracion/`.",
        "",
        "## 2. Cobertura de evidencia",
        "",
        f"- Hallazgos con `evaluation_ids` válidos: {coverage.hallazgos_con_evidencia}/"
        f"{coverage.n_hallazgos} ({_pct(coverage.pct_hallazgos)})"
        + (
            f" · sin evidencia: {', '.join(coverage.hallazgos_sin_evidencia)}"
            if coverage.hallazgos_sin_evidencia
            else ""
        ),
        f"- Acciones con `finding_ids` válidos: {coverage.acciones_con_hallazgos}/"
        f"{coverage.n_acciones} ({_pct(coverage.pct_acciones)})"
        + (
            f" · sin hallazgo: {', '.join(coverage.acciones_sin_hallazgos)}"
            if coverage.acciones_sin_hallazgos
            else ""
        ),
        "",
        "## 3. Calidad del plan (PlanGuard)",
        "",
    ]
    if isinstance(quality, str):
        lines.append(f"- **No disponible**: {quality}")
    else:
        lines += [
            f"- Juez {quality.juez} ({quality.modelo}) sobre {len(quality.acciones)} acciones.",
            f"- Específicas {_pct(quality.pct_especificas)} · coherentes con su hallazgo "
            f"{_pct(quality.pct_coherentes)} · respetan restricciones "
            f"{_pct(quality.pct_respetan_restricciones)} · realistas "
            f"{_pct(quality.pct_realistas)} · calidad media "
            f"{'—' if quality.calidad_media is None else f'{quality.calidad_media:.2f}'} / 3.",
            f"- Por debajo de umbral: {', '.join(quality.por_debajo_umbral) or 'ninguna'} · "
            f"baja confianza: {', '.join(quality.baja_confianza) or 'ninguna'}.",
            f"- {quality.nota}",
        ]
    lines += [
        "",
        "## 4. Simulación del plan",
        "",
        f"Score de Citación actual: {simulation.score_actual} · tasa espontánea "
        f"{_pct(simulation.tasa_espontanea_actual)}.",
        "",
        "| Fase | Acciones simuladas | Score mínimo | Score esperado | Score máximo |",
        "|---|---:|---:|---:|---:|",
        *(
            f"| {p.fase} | {len(p.acciones)} | {p.score.minimo:.1f} | {p.score.esperado:.1f} "
            f"| {p.score.maximo:.1f} |"
            for p in simulation.proyecciones
        ),
        "",
        "Segmentos que más cambian (esperado):",
        "",
        *(
            f"- {s.segmento}: {_pct(s.tasa_actual)} → +{s.delta.esperado * 100:.1f} puntos "
            f"({', '.join(s.acciones)})"
            for s in simulation.segmentos
        ),
        "",
        "Acciones sin efecto simulado: "
        + (
            "; ".join(f"{a.action_id} ({a.motivo})" for a in simulation.acciones_sin_efecto)
            or "ninguna"
        ),
        "",
        "Supuestos:",
        "",
        *(f"- {s}" for s in simulation.supuestos),
        "",
        f"> {simulation.advertencia}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "evaluacion")
    parser.add_argument("--calibracion", type=Path, default=ROOT / "docs" / "calibracion")
    parser.add_argument("--no-plan-guard", action="store_true")
    args = parser.parse_args(argv)

    study_id, brief, metrics, findings, plan, evaluations = (
        study_from_json(args.study) if args.study else study_from_fixtures()
    )
    coverage = evidence_coverage(findings, plan, evaluations)
    quality: PlanQuality | str = "desactivado con --no-plan-guard"
    if not args.no_plan_guard:
        try:
            quality = build_plan_guard(Settings()).assess(plan, findings, brief)
        except MissingCredentialError as exc:
            quality = f"falta {exc.variable} (ni en el entorno ni en .env)"
    simulation = simulate_plan(plan, metrics, findings)

    markdown = render(study_id, latest_calibration(args.calibracion), coverage, quality, simulation)
    print(markdown)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{date.today().isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")
    print(f"Informe guardado en {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

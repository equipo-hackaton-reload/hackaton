"""Informe de rigor estadístico de Alborada (kit, etiquetas del kit como la cifra canónica).

Uso:
    uv run python scripts/informe_rigor.py

Imprime en Markdown: el Score de Citación con su IC bootstrap («25,9 [inf–sup]»), la tasa de
aparición espontánea por motor y ciudad con su margen (Wilson) y la significancia de cada
hallazgo. Sin red y determinista (semilla fija). Las cifras se copian en ADR 0008.
"""

import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from posiq.domain.findings import detect_findings  # noqa: E402
from posiq.domain.schemas import Metrics, Motor  # noqa: E402
from posiq.domain.stats import (  # noqa: E402
    Muestra,
    formato_intervalo,
    formato_margen,
    informe_rigor,
    intervalo_score,
)
from posiq.domain.stats_schemas import InformeRigor  # noqa: E402


def render(informe: InformeRigor, metrics: Metrics, muestra: Muestra) -> str:
    lineas = [f"# Rigor estadístico · {informe.study_id}", ""]
    if informe.score is not None:
        lineas.append(
            f"- Score de Citación: **{formato_intervalo(informe.score)}** "
            f"(IC 95 % bootstrap, {informe.replicas_bootstrap} réplicas, "
            f"semilla {informe.semilla_bootstrap}, n = {informe.score.n} ejecuciones)"
        )
    lineas += [
        "",
        "| Segmento | Aparición espontánea | Margen | Score de Citación |",
        "|---|---|---|---|",
    ]
    for s in informe.aparicion:
        if s.tipo != "espontaneo" or s.dimension not in ("global", "motor", "ciudad"):
            continue
        if s.intervalo is None:
            lineas.append(f"| {s.valor} | sin datos | | |")
            continue
        score = (
            intervalo_score(muestra, metrics.marca_foco_id, cast(Motor, s.valor))
            if s.dimension == "motor"
            else None
        )
        lineas.append(
            f"| {s.valor} (n = {s.intervalo.n}) "
            f"| {formato_intervalo(s.intervalo, 0, porcentaje=True)} "
            f"| {formato_margen(s.intervalo)} "
            f"| {formato_intervalo(score) if score else ''} |"
        )
    lineas += [
        "",
        "| Hallazgo | Contraste | Delta [IC 95 %] | ¿Significativo? |",
        "|---|---|---|---|",
    ]
    for h in informe.hallazgos:
        if h.significancia is None:
            lineas.append(f"| {h.finding_id} | {h.contraste} | — | sin contraste |")
            continue
        i = h.significancia.intervalo
        decimales = 2 if i.metodo == "bootstrap" else 4
        lineas.append(
            f"| {h.finding_id} | {h.contraste} | {formato_intervalo(i, decimales)} "
            f"| {'sí' if h.significativo else 'no'} |"
        )
    return "\n".join(lineas) + "\n"


def main() -> None:
    from tests.golden.conftest import alborada_brief_summary, alborada_metrics, load_kit

    kit = load_kit()
    brief = alborada_brief_summary()
    metrics = alborada_metrics(kit, brief)
    findings = detect_findings(metrics, brief)
    muestra = Muestra(kit.evaluations(), kit.runs, kit.prompts)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    print(render(informe_rigor(metrics, findings, muestra), metrics, muestra))


if __name__ == "__main__":
    main()

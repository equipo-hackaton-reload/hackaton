"""Calibra el juez configurado contra `muestra_evaluada.csv` y guarda el informe.

Uso:
    uv run python scripts/calibrate_judge.py [--judge auto|jev|llm] [--no-cache] [--out DIR]

`auto` usa Jev si hay TYPESAFE_API_KEY y el juez LLM si no. Se mide el juez en bruto (sin
fallback). Imprime la tabla y la guarda en `docs/calibracion/<fecha>_<juez>.md`.
"""

import argparse
import sys
from pathlib import Path

from posiq.adapters.budget import Budget, estimate_judge_cost
from posiq.adapters.cache import DiskCache
from posiq.adapters.judge import JevJudge, LLMJudge, SystemOneJudge
from posiq.adapters.judge.calibration import calibrate, render_markdown
from posiq.domain import kit_loader as kl
from posiq.settings import Settings

STUDY_ID = "calibracion-muestra"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge", choices=["auto", "jev", "llm"], default="auto")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--out", default="docs/calibracion")
    args = parser.parse_args(argv)

    settings = Settings()
    kit = Path(settings.kit_dir)
    brands = kl.load_brands(kit / "marcas.csv")
    sources = kl.load_sources(kit / "fuentes_catalogo.csv")
    runs = kl.load_runs(kit / "ejecuciones.csv", brands, sources, STUDY_ID)
    sample = kl.load_evaluated_sample(kit / "muestra_evaluada.csv", brands, STUDY_ID)

    tiene_typesafe = bool(settings.typesafe_api_key.get_secret_value())
    tipo = args.judge if args.judge != "auto" else ("jev" if tiene_typesafe else "llm")
    cache = DiskCache(settings.cache_path, enabled=settings.cache_enabled and not args.no_cache)
    budget = Budget.from_settings(settings, STUDY_ID)
    judge: SystemOneJudge = (
        JevJudge(settings, brands, budget=budget, cache=cache)
        if tipo == "jev"
        else LLMJudge(settings, brands, budget=budget, cache=cache)
    )

    print(
        f"Juez {judge.name} ({judge.model}) sobre {len(sample)} filas. Coste estimado con Jev: "
        f"{estimate_judge_cost(len(sample), 1, settings):.4f} € · tope {settings.budget_eur_max} €"
    )
    report = calibrate(judge, sample, runs, brands)
    markdown = render_markdown(report)
    print(markdown)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{report.fecha.isoformat()}_{judge.name}.md"
    path.write_text(markdown, encoding="utf-8")
    print(f"Informe guardado en {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

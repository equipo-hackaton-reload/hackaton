"""Regenera `apps/web/src/mocks/fixtures/` ejecutando el dominio sobre el kit (caso Alborada).

Las cifras del mock de la web (score, ranking, visibilidad, hallazgos) son las que calcula
`posiq.domain`, no números escritos a mano. Uso, desde la raíz del repo:

    uv run python apps/web/scripts/gen_mock_fixtures.py
"""

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "apps" / "web" / "src" / "mocks" / "fixtures"
KIT = ROOT / "data" / "kit" / "02_Datos" / "caso_oftalmologia"
# Máximo de ids por lista en las métricas: el mock no necesita las 240 evaluaciones de cada celda.
MAX_IDS = 12
# Evaluaciones con texto que se guardan por hallazgo para el panel de evidencias.
MAX_EVIDENCIAS = 12

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _recortar(o: Any) -> Any:
    if isinstance(o, dict):
        return {
            k: v[:MAX_IDS] if k.endswith("_ids") and isinstance(v, list) else _recortar(v)
            for k, v in o.items()
        }
    if isinstance(o, list):
        return [_recortar(x) for x in o]
    return o


def _escribir(nombre: str, obj: Any) -> None:
    texto = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    (OUT / nombre).write_text(texto, "utf-8")


def main() -> None:
    from tests.golden import conftest as golden

    from posiq.domain import kit_loader as kl
    from posiq.domain.findings import detect_findings
    from posiq.domain.metrics import compute_metrics

    brands = kl.load_brands(KIT / "marcas.csv")
    sources = kl.load_sources(KIT / "fuentes_catalogo.csv")
    templates = kl.load_prompt_bank(KIT / "banco_prompts.csv")
    kit = golden.Kit(
        brands=brands,
        prompts=kl.load_prompt_instances(KIT / "ejecuciones.csv", templates, brands),
        runs=kl.load_runs(KIT / "ejecuciones.csv", brands, sources, golden.STUDY_ID),
        sources=sources,
        sample=kl.load_evaluated_sample(KIT / "muestra_evaluada.csv", brands, golden.STUDY_ID),
    )
    brief = golden.alborada_brief.__wrapped__()  # type: ignore[attr-defined]
    evals = kit.evaluations()
    metrics = compute_metrics(
        brief, kit.market, kit.prompts, kit.runs, evals, kit.sources, study_id=golden.STUDY_ID
    )
    findings = detect_findings(metrics, brief)

    runs = {r.id: r for r in kit.runs}
    prompts = {p.id: p for p in kit.prompts}
    por_id = {e.id: e for e in evals}
    evidencias = {}
    for f in findings:
        for eid in f.evaluation_ids[:MAX_EVIDENCIAS]:
            e = por_id[eid]
            r = runs[e.run_id]
            p = prompts.get(r.prompt_id)
            evidencias[eid] = {
                "evaluation": e.model_dump(mode="json"),
                "motor": r.motor,
                "prompt": p.texto if p else r.prompt_id,
                "texto_respuesta": r.texto_respuesta,
                "fuentes": [s.dominio for s in r.fuentes],
            }

    OUT.mkdir(parents=True, exist_ok=True)
    market = kit.market.model_copy(update={"confirmado_por_humano": False})
    _escribir("brief.json", brief.model_dump(mode="json"))
    _escribir("market.json", market.model_dump(mode="json"))
    _escribir("metrics.json", _recortar(metrics.model_dump(mode="json")))
    _escribir("findings.json", [f.model_dump(mode="json") for f in findings])
    _escribir("evidencias.json", evidencias)

    foco = metrics.score_global.score
    puesto = metrics.ranking.index(metrics.marca_foco_id) + 1
    print(f"score {foco} · puesto {puesto}/{len(metrics.ranking)} · {len(findings)} hallazgos")


if __name__ == "__main__":
    main()

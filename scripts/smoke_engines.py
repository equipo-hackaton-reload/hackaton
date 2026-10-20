"""Prueba de humo de los motores reales con unos pocos prompts del kit.

Uso:
    uv run python scripts/smoke_engines.py [-n 3] [--motores ChatGPT,Claude] [--prompt-ids ID,...]
                                           [--repeticiones 1] [--no-cache] [--out data/smoke]

Lanza N prompts instanciados del kit (uno por plantilla, en orden) contra los motores que tengan
clave en `.env`, muestra el texto truncado, las fuentes y el coste de cada `Run` y las añade a
`<out>/<fecha>.jsonl`. Tope de gasto: `BUDGET_EUR_MAX`; la caché evita repetir llamadas pagadas.
"""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from posiq.adapters.budget import Budget, BudgetExceeded
from posiq.adapters.cache import DiskCache
from posiq.adapters.engines import RealEngine, build_engines
from posiq.domain import kit_loader as kl
from posiq.domain.schemas import PromptInstance, Run
from posiq.settings import Settings

STUDY_ID = "smoke-engines"
TRUNCATE = 300


def pick_prompts(instances: list[PromptInstance], n: int, ids: list[str]) -> list[PromptInstance]:
    if ids:
        by_id = {p.id: p for p in instances}
        faltan = [i for i in ids if i not in by_id]
        if faltan:
            raise SystemExit(f"prompts desconocidos: {faltan}")
        return [by_id[i] for i in ids]
    seen: set[str] = set()
    out: list[PromptInstance] = []
    for p in instances:
        if p.template_id not in seen:
            seen.add(p.template_id)
            out.append(p)
    return out[:n]


def show(run: Run) -> None:
    texto = " ".join(run.texto_respuesta.split())
    if len(texto) > TRUNCATE:
        texto = texto[:TRUNCATE] + "…"
    fuentes = ", ".join(f"{s.dominio} ({s.tipo or '?'})" for s in run.fuentes) or "SIN BÚSQUEDA"
    print(f"  [{run.motor} · {run.modelo}] {run.prompt_id} r{run.repeticion}")
    print(f"    texto:   {texto}")
    print(f"    fuentes: {fuentes}")
    print(f"    tokens:  {run.tokens} · coste: {run.coste_eur:.4f} €")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", type=int, default=3, help="número de prompts (por defecto 3)")
    parser.add_argument("--motores", default="", help="lista separada por comas; vacío = todos")
    parser.add_argument("--prompt-ids", default="", help="ids concretos, separados por comas")
    parser.add_argument("--repeticiones", type=int, default=1)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--out", default="data/smoke")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings()
    kit = Path(settings.kit_dir)
    brands = kl.load_brands(kit / "marcas.csv")
    templates = kl.load_prompt_bank(kit / "banco_prompts.csv")
    instances = kl.load_prompt_instances(kit / "ejecuciones.csv", templates, brands)
    ids = [i.strip() for i in args.prompt_ids.split(",") if i.strip()]
    prompts = pick_prompts(instances, args.n, ids)

    cache = DiskCache(settings.cache_path, enabled=settings.cache_enabled and not args.no_cache)
    budget = Budget.from_settings(settings, STUDY_ID)
    engines = build_engines(settings, "real", [b.id for b in brands], cache=cache, budget=budget)
    motores = {m.strip() for m in args.motores.split(",") if m.strip()}
    if motores:
        engines = [e for e in engines if e.name in motores]
    if not engines:
        print("No hay motores con clave: define OPENAI/GEMINI/PERPLEXITY/ANTHROPIC_API_KEY.")
        return 1

    llamadas = len(prompts) * len(engines) * args.repeticiones
    print(
        f"{len(prompts)} prompts × {len(engines)} motores ({', '.join(e.name for e in engines)}) "
        f"× {args.repeticiones} rep. = {llamadas} llamadas · tope {settings.budget_eur_max} €"
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now(UTC).date().isoformat()}.jsonl"
    ok = errores = 0
    with path.open("a", encoding="utf-8") as fh:
        for engine in engines:
            assert isinstance(engine, RealEngine)
            print(f"\n== {engine.name} ({engine.model}) ==")
            results = engine.ask_many(prompts, repeticiones=args.repeticiones, study_id=STUDY_ID)
            for result in results:
                if isinstance(result, BaseException):
                    errores += 1
                    print(f"  ERROR {type(result).__name__}: {result}")
                    if isinstance(result, BudgetExceeded):
                        break
                    continue
                ok += 1
                show(result)
                fh.write(result.model_dump_json() + "\n")

    print(f"\n{ok} runs guardadas en {path} · {errores} errores")
    print(f"Coste de esta ejecución: {budget.total_eur:.4f} € (las respuestas en caché no cuentan)")
    for nodo, eur in sorted(budget.by_node().items()):
        print(f"  {nodo}: {eur:.4f} €")
    return 0 if errores == 0 else 2


if __name__ == "__main__":
    sys.exit(main())

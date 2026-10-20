"""Métricas del estudio: pandas por dentro, modelos por fuera.

Reglas (metodología §8 y doc 07):
- Espontáneo (`generico`, `ciudad`) y asistido (`marca`, `par`) se calculan SIEMPRE por separado.
- Solo cuentan las evaluaciones de marcas elegibles (`Run.marcas_a_evaluar`); las ausencias
  elegibles cuentan en el denominador.
- Un segmento sin observaciones tiene `tasa` None («sin datos»), nunca 0 %.
- Las fuentes citadas son de la ejecución: «fuentes de una marca» son los dominios citados en las
  ejecuciones espontáneas en las que la marca aparece. Así marca y líder se comparan con la misma
  cobertura.
"""

from collections import Counter
from collections.abc import Sequence
from typing import Any, Final, cast

import pandas as pd

from posiq.domain.schemas import (
    Brand,
    BriefSummary,
    Dimension,
    Evaluation,
    Market,
    MentionQuality,
    Metrics,
    Motor,
    PromptInstance,
    Run,
    ScoreBreakdown,
    Source,
    SourceGap,
    SourceStat,
    TipoVisibilidad,
    VisibilityCell,
)
from posiq.domain.scoring import SCORE_VERSION, score_citacion
from posiq.domain.text import fold

TOP_FUENTES: Final = 10
TIPOS: Final[tuple[TipoVisibilidad, ...]] = ("espontaneo", "asistido")
FASES: Final = ("descubrimiento", "comparacion", "validacion", "decision")
DIMENSIONES: Final[dict[Dimension, str]] = {
    "global": "global",
    "motor": "motor",
    "fase": "fase",
    "ciudad": "ciudad",
    "perfil": "perfil",
    "familia": "familia",
}


def resolve_brand(name: str, market: Market) -> Brand:
    """Marca del mercado cuyo nombre o alias coincide con `name` (sin acentos ni mayúsculas)."""
    for brand in market.marcas:
        if fold(name.strip()) in {fold(n) for n in [brand.nombre, *brand.aliases]}:
            return brand
    raise ValueError(f"la marca del brief «{name}» no está en el mercado")


def _frame(
    evaluations: list[Evaluation], runs: list[Run], prompts: list[PromptInstance]
) -> pd.DataFrame:
    runs_by_id = {r.id: r for r in runs}
    prompts_by_id = {p.id: p for p in prompts}
    rows: list[dict[str, Any]] = []
    for e in evaluations:
        run = runs_by_id.get(e.run_id)
        prompt = prompts_by_id.get(run.prompt_id) if run else None
        if run is None or prompt is None or e.brand_id not in run.marcas_a_evaluar:
            continue
        rows.append(
            {
                "eval_id": e.id,
                "brand_id": e.brand_id,
                "run_id": run.id,
                "aparece": e.aparece,
                "fuerza": e.fuerza,
                "tipo_mencion": e.tipo_mencion,
                "sentimiento": e.sentimiento,
                "desconocimiento": e.por_desconocimiento,
                "global": "global",
                "motor": run.motor,
                "fase": prompt.fase_embudo,
                "ciudad": prompt.ciudad,
                "perfil": prompt.perfil,
                "familia": prompt.familia,
                "tipo": prompt.tipo,
            }
        )
    columns = ["eval_id", "brand_id", "run_id", "aparece", "fuerza", "tipo", *DIMENSIONES.values()]
    df = pd.DataFrame(rows, columns=[*columns, "tipo_mencion", "sentimiento", "desconocimiento"])
    df["aparece"] = df["aparece"].astype(bool)
    df["desconocimiento"] = df["desconocimiento"].astype(bool)
    return df


def _segment_values(
    df: pd.DataFrame, dimension: Dimension, brief: BriefSummary, motores: Sequence[str]
) -> list[str]:
    """Valores de cada dimensión que se publican siempre (con «sin datos» si no hay filas)."""
    present = sorted({str(v) for v in df[DIMENSIONES[dimension]].dropna().unique()})
    if dimension == "motor":
        return sorted(set(motores) | set(present))
    if dimension == "fase":
        return [*FASES, *(v for v in present if v not in FASES)]
    if dimension == "ciudad":
        return [*brief.ciudades, *(v for v in present if v not in brief.ciudades)]
    return present


def _cell(
    group: pd.DataFrame, brand_id: str, tipo: TipoVisibilidad, dimension: Dimension, valor: str
) -> VisibilityCell:
    n = len(group)
    apariciones = int(group["aparece"].sum()) if n else 0
    fuerzas = group.loc[group["aparece"], "fuerza"] if n else pd.Series(dtype=float)
    return VisibilityCell(
        brand_id=brand_id,
        tipo=tipo,
        dimension=dimension,
        valor=valor,
        n=n,
        apariciones=apariciones,
        tasa=apariciones / n if n else None,
        fuerza_media=round(float(fuerzas.mean()), 3) if len(fuerzas) else None,
        evaluation_ids=[str(i) for i in group["eval_id"]],
    )


def _visibility(
    df: pd.DataFrame, brand_ids: list[str], brief: BriefSummary, motores: Sequence[str]
) -> list[VisibilityCell]:
    cells: list[VisibilityCell] = []
    for tipo in TIPOS:
        by_tipo = df[df["tipo"] == tipo]
        for dimension, column in DIMENSIONES.items():
            values = _segment_values(df, dimension, brief, motores)
            for brand_id in brand_ids:
                by_brand = by_tipo[by_tipo["brand_id"] == brand_id]
                for valor in values:
                    group = by_brand[by_brand[column].astype(str) == valor]
                    cells.append(_cell(group, brand_id, tipo, dimension, valor))
    return cells


def _mention_quality(df: pd.DataFrame, brand_ids: list[str]) -> list[MentionQuality]:
    out: list[MentionQuality] = []
    for tipo in TIPOS:
        for brand_id in brand_ids:
            seen = df[(df["tipo"] == tipo) & (df["brand_id"] == brand_id) & df["aparece"]]
            negativas = seen[seen["fuerza"] == -1]
            desconocidas = seen[seen["desconocimiento"]]
            out.append(
                MentionQuality(
                    brand_id=brand_id,
                    tipo=tipo,
                    apariciones=len(seen),
                    fuerza_media=round(float(seen["fuerza"].mean()), 3) if len(seen) else None,
                    por_tipo_mencion=_counts(seen["tipo_mencion"]),
                    por_sentimiento=_counts(seen["sentimiento"]),
                    por_desconocimiento=len(desconocidas),
                    negativas=len(negativas),
                    desconocimiento_ids=[str(i) for i in desconocidas["eval_id"]],
                    negativas_ids=[str(i) for i in negativas["eval_id"]],
                )
            )
    return out


def _counts(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.dropna().value_counts().items()}


def _domains_by_run(runs: list[Run]) -> dict[str, list[str]]:
    return {r.id: sorted({s.dominio for s in r.fuentes}) for r in runs}


def _top_sources(
    df: pd.DataFrame, brand_ids: list[str], runs: list[Run], catalog: dict[str, Source]
) -> list[SourceStat]:
    domains = _domains_by_run(runs)
    spont = df[(df["tipo"] == "espontaneo") & df["aparece"]]
    out: list[SourceStat] = []
    for brand_id in brand_ids:
        counter: Counter[str] = Counter()
        for run_id in spont.loc[spont["brand_id"] == brand_id, "run_id"]:
            counter.update(domains.get(str(run_id), []))
        for dominio, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_FUENTES]:
            src = catalog.get(dominio)
            out.append(
                SourceStat(
                    brand_id=brand_id,
                    dominio=dominio,
                    tipo=src.tipo if src else None,
                    calidad=src.calidad if src else None,
                    apariciones=count,
                )
            )
    return out


def _source_gap(
    df: pd.DataFrame, foco: str, lider: str | None, runs: list[Run], catalog: dict[str, Source]
) -> list[SourceGap]:
    """Dominios citados con el líder más que con la marca foco, en ejecuciones espontáneas."""
    if lider is None:
        return []
    domains = _domains_by_run(runs)
    spont = df[df["tipo"] == "espontaneo"]
    runs_lider = set(spont.loc[(spont["brand_id"] == lider) & spont["aparece"], "run_id"])
    runs_foco = set(spont.loc[(spont["brand_id"] == foco) & spont["aparece"], "run_id"])
    ausente = spont[(spont["brand_id"] == foco) & ~spont["aparece"]]
    ausente_por_run = dict(zip(ausente["run_id"], ausente["eval_id"], strict=True))

    con_lider = Counter(d for r in runs_lider for d in domains.get(str(r), []))
    con_foco = Counter(d for r in runs_foco for d in domains.get(str(r), []))
    gaps: list[SourceGap] = []
    for dominio in sorted(set(con_lider) | set(con_foco)):
        brecha = con_lider[dominio] - con_foco[dominio]
        if brecha <= 0:
            continue
        sin_marca = [
            str(ausente_por_run[r])
            for r in sorted(runs_lider)
            if r in ausente_por_run and dominio in domains.get(str(r), [])
        ]
        src = catalog.get(dominio)
        gaps.append(
            SourceGap(
                dominio=dominio,
                tipo=src.tipo if src else None,
                con_lider=con_lider[dominio],
                con_marca=con_foco[dominio],
                brecha=brecha,
                lider_sin_marca=len(sin_marca),
                evaluation_ids=sin_marca,
            )
        )
    return sorted(gaps, key=lambda g: (-g.brecha, g.dominio))


def _ranking(scores: list[ScoreBreakdown]) -> list[str]:
    con_score = [s for s in scores if s.score is not None]
    sin_score = [s.brand_id for s in scores if s.score is None]
    ordered = sorted(con_score, key=lambda s: (-cast(float, s.score), s.brand_id))
    return [s.brand_id for s in ordered] + sorted(sin_score)


def compute_metrics(
    brief: BriefSummary,
    market: Market,
    prompts: list[PromptInstance],
    runs: list[Run],
    evaluations: list[Evaluation],
    sources: list[Source],
) -> Metrics:
    """Métricas de todas las marcas del mercado, con la marca del brief como foco."""
    foco = resolve_brand(brief.marca, market)
    lider = next((b.id for b in market.marcas if b.rol == "lider"), None)
    brand_ids = [b.id for b in market.marcas]
    catalog = {s.dominio: s for s in sources}
    motores: list[Motor] = sorted({r.motor for r in runs})
    df = _frame(evaluations, runs, prompts)

    scores = [score_citacion(evaluations, runs, prompts, b) for b in brand_ids]
    por_motor = [
        score_citacion(evaluations, runs, prompts, b, motor) for b in brand_ids for motor in motores
    ]
    tipo_por_prompt = {p.id: p.tipo for p in prompts}
    tipos_run = Counter(tipo_por_prompt.get(r.prompt_id, "sin_prompt") for r in runs)

    return Metrics(
        score_version=SCORE_VERSION,
        marca_foco_id=foco.id,
        lider_id=lider,
        score_global=next(s for s in scores if s.brand_id == foco.id),
        scores=scores,
        scores_por_motor=por_motor,
        ranking=_ranking(scores),
        visibilidad=_visibility(df, brand_ids, brief, motores),
        calidad_menciones=_mention_quality(df, brand_ids),
        top_fuentes=_top_sources(df, brand_ids, runs, catalog),
        brecha_fuentes=_source_gap(df, foco.id, lider, runs, catalog),
        n_ejecuciones={"total": len(runs), **tipos_run, "evaluaciones": len(df)},
    )

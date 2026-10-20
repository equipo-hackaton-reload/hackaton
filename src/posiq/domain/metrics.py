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
    MetricsDelta,
    Motor,
    PromptInstance,
    Run,
    ScoreBreakdown,
    Source,
    SourceGap,
    SourceStat,
    TipoVisibilidad,
    VisibilityCell,
    VisibilityDelta,
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
    study_id: str,
    comparado_con: str | None = None,
) -> Metrics:
    """Métricas de todas las marcas del mercado, con la marca del brief como foco.

    Todas las ejecuciones y evaluaciones deben ser de `study_id`: mezclar estudios es un error.
    """
    estudios = {r.study_id for r in runs} | {e.study_id for e in evaluations}
    ajenos = sorted(estudios - {study_id})
    if ajenos:
        raise ValueError(f"ejecuciones o evaluaciones de otros estudios: {ajenos}")
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
        study_id=study_id,
        comparado_con=comparado_con,
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


DELTA_DIMENSIONES: Final[tuple[Dimension, ...]] = ("global", "motor", "fase", "ciudad")


def _delta(a: float | None, b: float | None, digits: int) -> float | None:
    return round(a - b, digits) if a is not None and b is not None else None


def diff_metrics(actual: Metrics, anterior: Metrics) -> MetricsDelta:
    """Cambio de la marca foco entre dos mediciones: score y tasas por motor, fase y ciudad.

    Solo compara la misma marca foco. Si cambia la versión del score, o `actual.comparado_con`
    apunta a otro estudio, el resultado se marca como no comparable y se explica en `avisos`.
    Un segmento presente solo en una medición aparece con el otro lado a None (sin datos).
    """
    if actual.marca_foco_id != anterior.marca_foco_id:
        raise ValueError(
            f"marcas foco distintas: {actual.marca_foco_id} frente a {anterior.marca_foco_id}"
        )
    avisos: list[str] = []
    if actual.score_version != anterior.score_version:
        avisos.append(
            f"versión del score distinta ({actual.score_version} frente a "
            f"{anterior.score_version}): las cifras no son comparables"
        )
    if actual.comparado_con not in (None, anterior.study_id):
        avisos.append(
            f"la medición actual declara compararse con {actual.comparado_con}, "
            f"no con {anterior.study_id}"
        )

    foco = actual.marca_foco_id
    deltas: list[VisibilityDelta] = []
    for tipo in TIPOS:
        for dimension in DELTA_DIMENSIONES:
            ahora = {c.valor: c for c in actual.cells(foco, tipo, dimension)}
            antes = {c.valor: c for c in anterior.cells(foco, tipo, dimension)}
            for valor in [*ahora, *(v for v in antes if v not in ahora)]:
                a, b = ahora.get(valor), antes.get(valor)
                tasa_a = a.tasa if a else None
                tasa_b = b.tasa if b else None
                deltas.append(
                    VisibilityDelta(
                        brand_id=foco,
                        tipo=tipo,
                        dimension=dimension,
                        valor=valor,
                        tasa_actual=tasa_a,
                        tasa_anterior=tasa_b,
                        delta=_delta(tasa_a, tasa_b, 4),
                        n_actual=a.n if a else 0,
                        n_anterior=b.n if b else 0,
                    )
                )

    return MetricsDelta(
        study_id=actual.study_id,
        comparado_con=anterior.study_id,
        marca_foco_id=foco,
        score_actual=actual.score_global.score,
        score_anterior=anterior.score_global.score,
        score_delta=_delta(actual.score_global.score, anterior.score_global.score, 2),
        visibilidad_delta=deltas,
        comparable=not avisos,
        avisos=avisos,
    )

"""Calibración del juez frente a las 133 etiquetas humanas de `muestra_evaluada.csv`.

Se mide el juez EN BRUTO (`ajudge`, sin política ni fallback) para saber cuánto acierta por sí
solo y cuántas filas irían a revisión o a fallback con los umbrales actuales. `discrepancias`
cuenta las filas en las que juez y reglas discrepan sobre la aparición: van a fallback por su
confianza limitada y, además, terminan SIEMPRE en revisión humana (ADR 0014). Las 15 ejecuciones
se separan por `Ejecucion_ID` (doc 07): las 10 primeras son de calibración y las 5 últimas, de
reserva. Las etiquetas humanas nunca se envían al juez.
"""

import asyncio
import statistics
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from posiq.adapters.judge.base import JudgeOutcome, SystemOneJudge
from posiq.domain.schemas import Brand, Evaluation, Run

N_RESERVA = 5


@dataclass(frozen=True)
class Pair:
    label: Evaluation
    outcome: JudgeOutcome
    split: str


@dataclass
class Agreement:
    n: int = 0
    aparece: float | None = None
    n_con_mencion: int = 0
    tipo_mencion: float | None = None
    fuerza_exacta: float | None = None
    fuerza_pm1: float | None = None
    fuerza_mae: float | None = None
    sentimiento: float | None = None


@dataclass
class CalibrationReport:
    judge: str
    model: str
    fecha: date
    accept: float
    fallback_threshold: float
    total: Agreement
    por_split: dict[str, Agreement]
    confianzas: dict[str, float]
    aceptadas: int
    a_revision: int
    a_fallback: int
    discrepancias: int
    matriz_tipo_mencion: dict[tuple[str, str], int]
    fallos: list[tuple[str, str, str, str]] = field(default_factory=list)
    coste_eur: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    duracion_s: float = 0.0


def _rate(hits: Sequence[bool]) -> float | None:
    return sum(hits) / len(hits) if hits else None


def agreement(pairs: Sequence[Pair]) -> Agreement:
    """Acuerdo con las etiquetas. Tipo, fuerza y sentimiento, solo donde la persona vio la marca."""
    seen = [p for p in pairs if p.label.aparece]
    errores = [abs(p.outcome.evaluation.fuerza - p.label.fuerza) for p in seen]
    return Agreement(
        n=len(pairs),
        aparece=_rate([p.outcome.evaluation.aparece == p.label.aparece for p in pairs]),
        n_con_mencion=len(seen),
        tipo_mencion=_rate(
            [p.outcome.evaluation.tipo_mencion == p.label.tipo_mencion for p in seen]
        ),
        fuerza_exacta=_rate([e == 0 for e in errores]),
        fuerza_pm1=_rate([e <= 1 for e in errores]),
        fuerza_mae=statistics.fmean(errores) if errores else None,
        sentimiento=_rate([p.outcome.evaluation.sentimiento == p.label.sentimiento for p in seen]),
    )


def splits(sample: Sequence[Evaluation]) -> dict[str, str]:
    """run_id → «calibracion» (10 primeras) o «reserva» (5 últimas), por Ejecucion_ID."""
    run_ids = sorted({e.run_id for e in sample})
    reserva = set(run_ids[-N_RESERVA:])
    return {r: "reserva" if r in reserva else "calibracion" for r in run_ids}


async def judge_sample(
    judge: SystemOneJudge,
    sample: Sequence[Evaluation],
    runs: dict[str, Run],
    brands: dict[str, Brand],
) -> list[Pair]:
    """Juzga cada fila de la muestra (en bruto) con la concurrencia del juez."""
    split_of = splits(sample)
    semaphore = asyncio.Semaphore(judge.concurrency)
    async with judge._session() as client:

        async def one(label: Evaluation) -> Pair:
            async with semaphore:
                outcome = await judge.ajudge(
                    runs[label.run_id], brands[label.brand_id], client=client
                )
            return Pair(label, outcome, split_of[label.run_id])

        return list(await asyncio.gather(*(one(e) for e in sample)))


def build_report(
    judge: SystemOneJudge, pairs: Sequence[Pair], duracion_s: float
) -> CalibrationReport:
    confs = sorted(p.outcome.confianza for p in pairs)
    quantiles = statistics.quantiles(confs, n=10) if len(confs) >= 2 else confs * 9
    fallos: list[tuple[str, str, str, str]] = []
    matriz: Counter[tuple[str, str]] = Counter()
    for p in pairs:
        pred, label = p.outcome.evaluation, p.label
        if pred.aparece != label.aparece:
            fallos.append((label.id, "aparece", str(label.aparece), str(pred.aparece)))
        if label.aparece:
            matriz[(str(label.tipo_mencion), str(pred.tipo_mencion))] += 1
            for campo in ("tipo_mencion", "fuerza", "sentimiento"):
                if getattr(pred, campo) != getattr(label, campo):
                    fallos.append(
                        (label.id, campo, str(getattr(label, campo)), str(getattr(pred, campo)))
                    )
    return CalibrationReport(
        judge=judge.name,
        model=judge.model,
        fecha=date.today(),
        accept=judge.accept,
        fallback_threshold=judge.fallback_threshold,
        total=agreement(pairs),
        por_split={
            s: agreement([p for p in pairs if p.split == s]) for s in ("calibracion", "reserva")
        },
        confianzas={
            "min": confs[0] if confs else 0.0,
            "p10": quantiles[0] if quantiles else 0.0,
            "mediana": statistics.median(confs) if confs else 0.0,
            "p90": quantiles[-1] if quantiles else 0.0,
            "max": confs[-1] if confs else 0.0,
        },
        aceptadas=sum(p.outcome.confianza >= judge.accept for p in pairs),
        a_revision=sum(
            judge.fallback_threshold <= p.outcome.confianza < judge.accept for p in pairs
        ),
        a_fallback=sum(p.outcome.confianza < judge.fallback_threshold for p in pairs),
        discrepancias=sum(p.outcome.discrepa for p in pairs),
        matriz_tipo_mencion=dict(matriz),
        fallos=fallos,
        coste_eur=sum(t.coste_eur for t in judge.traces),
        tokens_in=sum(t.tokens_in for t in judge.traces),
        tokens_out=sum(t.tokens_out for t in judge.traces),
        duracion_s=duracion_s,
    )


def calibrate(
    judge: SystemOneJudge,
    sample: Sequence[Evaluation],
    runs: Sequence[Run],
    brands: Sequence[Brand],
) -> CalibrationReport:
    start = time.perf_counter()
    pairs = asyncio.run(
        judge_sample(judge, sample, {r.id: r for r in runs}, {b.id: b for b in brands})
    )
    return build_report(judge, pairs, time.perf_counter() - start)


def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


def render_markdown(report: CalibrationReport) -> str:
    rows = [("total", report.total), *report.por_split.items()]
    lines = [
        f"# Calibración del juez `{report.judge}` ({report.model}) · {report.fecha.isoformat()}",
        "",
        "Muestra: 133 filas de `muestra_evaluada.csv` (15 ejecuciones; reserva = 5 últimas por "
        "`Ejecucion_ID`). Juez en bruto, sin fallback. Tipo, fuerza y sentimiento se miden solo "
        "en las filas donde la etiqueta humana dice que la marca aparece.",
        "",
        "| Conjunto | n | aparece | n con mención | tipo_mencion | fuerza exacta | fuerza ±1 "
        "| MAE fuerza | sentimiento |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for nombre, a in rows:
        lines.append(
            f"| {nombre} | {a.n} | {_fmt(a.aparece)} | {a.n_con_mencion} | {_fmt(a.tipo_mencion)} "
            f"| {_fmt(a.fuerza_exacta)} | {_fmt(a.fuerza_pm1)} | {_fmt(a.fuerza_mae)} "
            f"| {_fmt(a.sentimiento)} |"
        )
    c = report.confianzas
    lines += [
        "",
        "## Confianza (mentioned, mention_type, strength)",
        "",
        f"min {c['min']:.3f} · p10 {c['p10']:.3f} · mediana {c['mediana']:.3f} · "
        f"p90 {c['p90']:.3f} · max {c['max']:.3f}",
        "",
        f"Con ACCEPT = {report.accept} y FALLBACK = {report.fallback_threshold}: "
        f"{report.aceptadas} aceptadas · {report.a_revision} a revisión · "
        f"{report.a_fallback} a fallback. De ellas, {report.discrepancias} discrepan con las "
        "reglas sobre la aparición y terminan en revisión humana aunque el fallback acierte.",
        "",
        "## Matriz de tipo de mención (humano → juez)",
        "",
        "| Humano | Juez | n |",
        "|---|---|---:|",
        *(f"| {h} | {j} | {n} |" for (h, j), n in sorted(report.matriz_tipo_mencion.items())),
        "",
        "## Coste",
        "",
        f"{report.tokens_in} tokens de entrada · {report.tokens_out} de salida · "
        f"{report.coste_eur:.4f} € · {report.duracion_s:.1f} s",
        "",
        f"## Discrepancias ({len(report.fallos)})",
        "",
        "| Evaluación | Campo | Humano | Juez |",
        "|---|---|---|---|",
        *(f"| {i} | {campo} | {h} | {j} |" for i, campo, h, j in report.fallos),
        "",
    ]
    return "\n".join(lines)

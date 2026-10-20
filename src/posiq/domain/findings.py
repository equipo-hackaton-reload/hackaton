"""Hallazgos deterministas a partir de las métricas. Cada regla es explícita y documentada.

Todas miran la marca foco del brief y, salvo donde se indica, solo la visibilidad ESPONTÁNEA.
Cada hallazgo lleva `evaluation_ids` reales (las evaluaciones del segmento que respalda la cifra)
y `origen_cifra` con el nombre de la métrica. Se devuelven como máximo `MAX_FINDINGS`, ordenados
por impacto (L > M > S) y, a igualdad, por el orden de las reglas.

Reglas:
1. caida_embudo — mayor caída de la tasa espontánea desde una fase a otra posterior del embudo
   (≥ 10 pp). Impacto L ≥ 25 pp · M ≥ 15 pp · S.
2. motor_debil — diferencia entre el motor con mayor y menor tasa espontánea (≥ 20 pp). Impacto
   L ≥ 40 pp · M ≥ 25 pp · S.
3. fuente_lider — dominio que acompaña al líder en ejecuciones donde la marca foco no aparece
   (≥ 3 ejecuciones; el de mayor brecha). Impacto L si es Ranking / institución o Medio · M.
4. ciudad_baja — ciudad del brief con tasa espontánea < 30 %, o < mitad de la tasa global.
   Impacto L < 10 % · M.
5. brecha_lider — diferencia de Score de Citación con el líder (≥ 15 puntos). Impacto L ≥ 30 · M.
6. asistida_vs_espontanea — tasa asistida − tasa espontánea ≥ 30 pp: el motor la conoce cuando
   se la nombran, pero no la propone por iniciativa propia. Impacto M.
7. recomendacion_debil — fuerza media de sus apariciones espontáneas < 1,5 con ≥ 5 apariciones:
   aparece pero apenas se recomienda. Impacto M.
8. menciones_negativas — apariciones con advertencia (fuerza −1) o por desconocimiento, en
   espontáneo y asistido (≥ 1). Impacto M ≥ 3 · S.

Confianza según el tamaño de la muestra que respalda la cifra: n ≥ 60 → 0,8 · n ≥ 20 → 0,65 ·
resto → 0,45.
"""

from collections.abc import Callable
from typing import Final

from posiq.domain.schemas import BriefSummary, FaseEmbudo, Finding, Metrics, Talla

MAX_FINDINGS: Final = 7
MIN_CAIDA_EMBUDO: Final = 0.10
MIN_GAP_MOTOR: Final = 0.20
MIN_LIDER_SIN_MARCA: Final = 3
MAX_TASA_CIUDAD: Final = 0.30
MIN_GAP_SCORE: Final = 15.0
MIN_GAP_ASISTIDA: Final = 0.30
MAX_FUERZA_DEBIL: Final = 1.5
MIN_APARICIONES_FUERZA: Final = 5

_IMPACT_ORDER: Final[dict[Talla, int]] = {"L": 0, "M": 1, "S": 2}
_FASES: Final[tuple[FaseEmbudo, ...]] = ("descubrimiento", "comparacion", "validacion", "decision")


def confidence_for(n: int) -> float:
    if n >= 60:
        return 0.8
    return 0.65 if n >= 20 else 0.45


def _pct(x: float) -> str:
    return f"{x * 100:.0f} %"


def _caida_embudo(m: Metrics, brief: BriefSummary) -> list[Finding]:
    cells = {
        c.valor: c for c in m.cells(m.marca_foco_id, "espontaneo", "fase") if c.tasa is not None
    }
    fases = [f for f in _FASES if f in cells]
    best: tuple[float, FaseEmbudo, FaseEmbudo] | None = None
    for i, desde in enumerate(fases):
        for hasta in fases[i + 1 :]:
            caida = (cells[desde].tasa or 0) - (cells[hasta].tasa or 0)
            if best is None or caida > best[0]:
                best = (caida, desde, hasta)
    if best is None or best[0] < MIN_CAIDA_EMBUDO:
        return []
    caida, desde, hasta = best
    destino = cells[hasta]
    return [
        Finding(
            id="F-caida-embudo",
            titulo=f"La visibilidad espontánea cae de {desde} a {hasta}",
            descripcion=(
                f"La marca aparece en el {_pct(cells[desde].tasa or 0)} de las respuestas "
                f"espontáneas de {desde} y solo en el {_pct(destino.tasa or 0)} en {hasta} "
                f"({destino.n} evaluaciones)."
            ),
            fase_embudo=hasta,
            impacto="L" if caida >= 0.25 else "M" if caida >= 0.15 else "S",
            confianza=confidence_for(destino.n),
            cifra=round(caida, 4),
            origen_cifra=f"visibilidad espontánea por fase: {desde} − {hasta}",
            evaluation_ids=destino.evaluation_ids,
        )
    ]


def _motor_debil(m: Metrics, brief: BriefSummary) -> list[Finding]:
    cells = [c for c in m.cells(m.marca_foco_id, "espontaneo", "motor") if c.tasa is not None]
    if len(cells) < 2:
        return []
    fuerte = max(cells, key=lambda c: c.tasa or 0)
    debil = min(cells, key=lambda c: c.tasa or 0)
    gap = (fuerte.tasa or 0) - (debil.tasa or 0)
    if gap < MIN_GAP_MOTOR:
        return []
    otros = [
        c.valor for c in cells if c is not debil and (fuerte.tasa or 0) - (c.tasa or 0) >= gap / 2
    ]
    extra = f" También queda lejos en {', '.join(otros)}." if otros else ""
    return [
        Finding(
            id="F-motor-debil",
            titulo=f"{debil.valor} apenas la menciona mientras {fuerte.valor} sí",
            descripcion=(
                f"Visibilidad espontánea del {_pct(debil.tasa or 0)} en {debil.valor} frente al "
                f"{_pct(fuerte.tasa or 0)} en {fuerte.valor}.{extra}"
            ),
            impacto="L" if gap >= 0.40 else "M" if gap >= 0.25 else "S",
            confianza=confidence_for(debil.n),
            cifra=round(debil.tasa or 0, 4),
            origen_cifra=f"visibilidad espontánea por motor: {debil.valor}",
            evaluation_ids=debil.evaluation_ids,
        )
    ]


def _fuente_lider(m: Metrics, brief: BriefSummary) -> list[Finding]:
    gaps = [g for g in m.brecha_fuentes if g.lider_sin_marca >= MIN_LIDER_SIN_MARCA]
    if not gaps or m.lider_id is None:
        return []
    gap = max(gaps, key=lambda g: (g.lider_sin_marca, g.brecha))
    return [
        Finding(
            id="F-fuente-lider",
            titulo=f"{gap.dominio} alimenta al líder y no a la marca",
            descripcion=(
                f"{gap.dominio} ({gap.tipo or 'tipo sin catalogar'}) se cita en "
                f"{gap.lider_sin_marca} respuestas espontáneas donde aparece el líder y la "
                "marca no; "
                f"acompaña al líder {gap.con_lider} veces y a la marca {gap.con_marca}."
            ),
            impacto="L" if gap.tipo in ("Ranking / institución", "Medio") else "M",
            confianza=confidence_for(gap.con_lider),
            cifra=float(gap.lider_sin_marca),
            origen_cifra=f"brecha de fuentes frente al líder: {gap.dominio}",
            evaluation_ids=gap.evaluation_ids,
        )
    ]


def _ciudad_baja(m: Metrics, brief: BriefSummary) -> list[Finding]:
    global_cell = m.cell(m.marca_foco_id, "espontaneo", "global", "global")
    tasa_global = global_cell.tasa if global_cell and global_cell.tasa is not None else None
    out: list[Finding] = []
    for ciudad in brief.ciudades:
        cell = m.cell(m.marca_foco_id, "espontaneo", "ciudad", ciudad)
        if cell is None or cell.tasa is None or not cell.evaluation_ids:
            continue
        baja = cell.tasa < MAX_TASA_CIUDAD or (
            tasa_global is not None and cell.tasa < tasa_global / 2
        )
        if not baja:
            continue
        out.append(
            Finding(
                id=f"F-ciudad-{ciudad.lower()}",
                titulo=f"Baja visibilidad en {ciudad}, ciudad prioritaria del brief",
                descripcion=(
                    f"Ante preguntas que nombran {ciudad}, la marca aparece en el "
                    f"{_pct(cell.tasa)} de las respuestas ({cell.n} evaluaciones)"
                    + (
                        f", frente al {_pct(tasa_global)} global."
                        if tasa_global is not None
                        else "."
                    )
                ),
                fase_embudo="descubrimiento",
                impacto="L" if cell.tasa < 0.10 else "M",
                confianza=confidence_for(cell.n),
                cifra=round(cell.tasa, 4),
                origen_cifra=f"visibilidad espontánea por ciudad: {ciudad}",
                evaluation_ids=cell.evaluation_ids,
            )
        )
    return out


def _brecha_lider(m: Metrics, brief: BriefSummary) -> list[Finding]:
    foco, lider = m.score_global, m.score_of(m.lider_id) if m.lider_id else None
    cell = m.cell(m.marca_foco_id, "espontaneo", "global", "global")
    if lider is None or foco.score is None or lider.score is None or cell is None:
        return []
    gap = lider.score - foco.score
    if gap < MIN_GAP_SCORE or not cell.evaluation_ids:
        return []
    puesto = m.ranking.index(m.marca_foco_id) + 1
    return [
        Finding(
            id="F-brecha-lider",
            titulo=f"{gap:.0f} puntos de Score de Citación por detrás del líder",
            descripcion=(
                f"Score de Citación espontáneo de {foco.score:.1f} frente a {lider.score:.1f} del "
                f"líder; puesto {puesto} de {len(m.ranking)} marcas."
            ),
            impacto="L" if gap >= 30 else "M",
            confianza=confidence_for(foco.n_evaluaciones),
            cifra=round(gap, 2),
            origen_cifra="score de citación: líder − marca foco",
            evaluation_ids=cell.evaluation_ids,
        )
    ]


def _asistida_vs_espontanea(m: Metrics, brief: BriefSummary) -> list[Finding]:
    esp = m.cell(m.marca_foco_id, "espontaneo", "global", "global")
    asi = m.cell(m.marca_foco_id, "asistido", "global", "global")
    if not esp or not asi or esp.tasa is None or asi.tasa is None or not esp.evaluation_ids:
        return []
    gap = asi.tasa - esp.tasa
    if gap < MIN_GAP_ASISTIDA:
        return []
    return [
        Finding(
            id="F-asistida-vs-espontanea",
            titulo="Los motores la conocen, pero no la proponen por iniciativa propia",
            descripcion=(
                f"Aparece en el {_pct(asi.tasa)} de las respuestas cuando la pregunta la nombra, "
                f"pero solo en el {_pct(esp.tasa)} cuando no la nombra."
            ),
            impacto="M",
            confianza=confidence_for(esp.n),
            cifra=round(gap, 4),
            origen_cifra="visibilidad asistida − visibilidad espontánea",
            evaluation_ids=esp.evaluation_ids,
        )
    ]


def _recomendacion_debil(m: Metrics, brief: BriefSummary) -> list[Finding]:
    q = next(
        (
            q
            for q in m.calidad_menciones
            if q.brand_id == m.marca_foco_id and q.tipo == "espontaneo"
        ),
        None,
    )
    cell = m.cell(m.marca_foco_id, "espontaneo", "global", "global")
    if (
        q is None
        or cell is None
        or q.fuerza_media is None
        or q.apariciones < MIN_APARICIONES_FUERZA
        or q.fuerza_media >= MAX_FUERZA_DEBIL
    ):
        return []
    return [
        Finding(
            id="F-recomendacion-debil",
            titulo="Aparece, pero casi nunca como recomendación",
            descripcion=(
                f"Fuerza de recomendación media de {q.fuerza_media:.2f} (escala −1 a 3) en sus "
                f"{q.apariciones} apariciones espontáneas."
            ),
            fase_embudo="decision",
            impacto="M",
            confianza=confidence_for(q.apariciones),
            cifra=q.fuerza_media,
            origen_cifra="fuerza media de las apariciones espontáneas",
            evaluation_ids=cell.evaluation_ids,
        )
    ]


def _menciones_negativas(m: Metrics, brief: BriefSummary) -> list[Finding]:
    qs = [q for q in m.calidad_menciones if q.brand_id == m.marca_foco_id]
    ids = sorted({i for q in qs for i in [*q.negativas_ids, *q.desconocimiento_ids]})
    if not ids:
        return []
    negativas = sum(q.negativas for q in qs)
    desconocimiento = sum(q.por_desconocimiento for q in qs)
    return [
        Finding(
            id="F-menciones-negativas",
            titulo="Menciones con advertencias o por desconocimiento",
            descripcion=(
                f"{negativas} menciones con advertencia o percepción negativa y {desconocimiento} "
                "en las que el motor dice no conocer la marca."
            ),
            fase_embudo="validacion",
            impacto="M" if len(ids) >= 3 else "S",
            confianza=confidence_for(len(ids)),
            cifra=float(len(ids)),
            origen_cifra="calidad de menciones: negativas + por desconocimiento",
            evaluation_ids=ids,
        )
    ]


RULES: Final[list[Callable[[Metrics, BriefSummary], list[Finding]]]] = [
    _caida_embudo,
    _motor_debil,
    _fuente_lider,
    _ciudad_baja,
    _brecha_lider,
    _asistida_vs_espontanea,
    _recomendacion_debil,
    _menciones_negativas,
]


def detect_findings(metrics: Metrics, brief: BriefSummary) -> list[Finding]:
    """Hallazgos de las reglas, ordenados por impacto (y orden de regla), como máximo 7."""
    found = [(i, f) for i, rule in enumerate(RULES) for f in rule(metrics, brief)]
    found.sort(key=lambda item: (_IMPACT_ORDER[item[1].impacto], item[0]))
    return [f for _, f in found[:MAX_FINDINGS]]

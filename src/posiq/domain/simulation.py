"""Simulación del impacto del plan sobre el Score de Citación (Nivel 3, N3.4). Puro.

Es un modelo EXPLÍCITO y CONSERVADOR, no una predicción. No estima visitas ni garantiza nada.

1. Segmentos. La población espontánea de la marca foco (la del score) se reparte en segmentos
   (fase × motor) a partir de las celdas de `Metrics`, suponiendo independencia entre fase y
   motor: n(f, m) = n(f)·n(m)/N y tasa(f, m) = tasa(f)·tasa(m)/tasa global (acotada a [0, 1]).
   Las ciudades son segmentos aparte (sus celdas de `Metrics`).
2. Alcance de una acción. Solo cuentan las acciones enlazadas a hallazgos del estudio y cuya
   palanca no sea `medicion`. Apuntan a:
   - su `fase_embudo`; si no tiene, las fases de sus hallazgos; si tampoco, todas;
   - sus `motores_objetivo`; si no tiene, todos;
   - si su descripción nombra una ciudad con datos, solo el segmento de esa ciudad.
3. Mejora por acción. Cada acción suma a la tasa espontánea de cada segmento al que apunta el
   rango (mínimo, esperado, máximo) de `IMPACTO_POR_PALANCA[palanca][impacto]`, en tanto por uno.
4. Rendimientos decrecientes y tope. En cada segmento, las aportaciones se ordenan de mayor a
   menor y la k-ésima (k = 0, 1, …) se multiplica por `DECAIMIENTO`**k. La suma se limita a
   `TOPE_SEGMENTO` y a que la tasa del segmento no pase de `TASA_MAXIMA`.
5. Score. La tasa global proyectada es la actual más Σ n(s)·Δ(s)/N. El score se recalcula con
   `scoring.score_from_profile`, manteniendo el perfil de las apariciones actuales (peso de
   posición, fuerza y calidad de fuente medios): las apariciones nuevas se parecen a las de hoy.
   Proyectado = actual + (score(tasa proyectada) − score(tasa actual)), acotado a [0, 100].
6. Fases. La proyección es acumulada: tras la fase k cuentan las acciones de las fases 0..k.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Final, Literal

from posiq.domain.schemas import Action, FaseEmbudo, Finding, Metrics, Palanca, Plan, Talla
from posiq.domain.scoring import AppearanceProfile, score_from_profile
from posiq.domain.simulation_schemas import (
    Escenario,
    IgnoredAction,
    PhaseProjection,
    SegmentChange,
    SimulationResult,
)
from posiq.domain.text import fold

SIMULATION_VERSION: Final = "1.0"

Rango = tuple[float, float, float]

# Mejora de la tasa espontánea del segmento (en tanto por uno: 0,04 = +4 puntos) por acción.
# M es la referencia; S = ½ M y L = 1,5 M. Ver docs/adr/0007-simulacion-y-calidad.md.
IMPACTO_POR_PALANCA: Final[dict[Palanca, dict[Talla, Rango]]] = {
    "autoridad_terceros": {
        "S": (0.010, 0.025, 0.040),
        "M": (0.020, 0.050, 0.080),
        "L": (0.030, 0.075, 0.120),
    },
    "contenido": {
        "S": (0.010, 0.020, 0.035),
        "M": (0.020, 0.040, 0.070),
        "L": (0.030, 0.060, 0.105),
    },
    "entidad_datos": {
        "S": (0.005, 0.015, 0.025),
        "M": (0.010, 0.030, 0.050),
        "L": (0.015, 0.045, 0.075),
    },
    "reputacion": {
        "S": (0.005, 0.010, 0.020),
        "M": (0.010, 0.020, 0.040),
        "L": (0.015, 0.030, 0.060),
    },
    "comunidades": {
        "S": (0.000, 0.008, 0.015),
        "M": (0.005, 0.015, 0.030),
        "L": (0.008, 0.023, 0.045),
    },
    "tecnico": {
        "S": (0.000, 0.005, 0.010),
        "M": (0.000, 0.010, 0.020),
        "L": (0.000, 0.015, 0.030),
    },
    "medicion": {"S": (0.0, 0.0, 0.0), "M": (0.0, 0.0, 0.0), "L": (0.0, 0.0, 0.0)},
}
DECAIMIENTO: Final = 0.6
TOPE_SEGMENTO: Final = 0.20
TASA_MAXIMA: Final = 0.95
# Perfil de una aparición nueva cuando hoy la marca no aparece nunca: 4.ª posición o peor,
# mención neutra y sin fuente.
PERFIL_SIN_APARICIONES: Final = AppearanceProfile(
    tasa=0.0, peso_medio=1.0, fuerza_media=1.0, calidad_media=0.2
)
TOP_SEGMENTOS: Final = 5

ADVERTENCIA: Final = (
    "Estimación ilustrativa con supuestos declarados, no una predicción: no garantiza resultados "
    "ni estima visitas o ventas. Los asistentes de IA cambian y la única forma de saber el efecto "
    "real del plan es volver a medir."
)
SUPUESTOS: Final = [
    "Solo se simula la visibilidad espontánea; el perfil de las apariciones (posición, fuerza y "
    "calidad de fuente medias) se mantiene como hoy.",
    "Fase y motor son independientes al repartir la población en segmentos.",
    "Mejora por acción según IMPACTO_POR_PALANCA (palanca × impacto S/M/L), con rangos mínimo, "
    "esperado y máximo; la palanca «medición» no mueve la visibilidad.",
    f"Rendimientos decrecientes: la k-ésima acción sobre un segmento aporta {DECAIMIENTO}^k de su "
    f"mejora; tope de +{TOPE_SEGMENTO * 100:.0f} puntos por segmento y tasa máxima de "
    f"{TASA_MAXIMA * 100:.0f} %.",
    "Las acciones sin hallazgo del estudio no se simulan; la proyección es acumulada por fase.",
    "Datos del kit sintéticos: la simulación ilustra el mecanismo, no el mercado real.",
]


@dataclass(frozen=True)
class _Segment:
    key: str
    dimension: Literal["fase_motor", "ciudad"]
    fase: str | None
    motor: str | None
    ciudad: str | None
    n: float
    tasa: float


def _segments(m: Metrics) -> list[_Segment]:
    foco = m.marca_foco_id
    total = m.cell(foco, "espontaneo", "global", "global")
    if total is None or not total.n or total.tasa is None:
        return []
    fases = [c for c in m.cells(foco, "espontaneo", "fase") if c.n and c.tasa is not None]
    motores = [c for c in m.cells(foco, "espontaneo", "motor") if c.n and c.tasa is not None]
    out: list[_Segment] = []
    for f in fases:
        for mo in motores:
            tasa = (f.tasa or 0) * (mo.tasa or 0) / total.tasa if total.tasa else 0.0
            out.append(
                _Segment(
                    key=f"{f.valor} · {mo.valor}",
                    dimension="fase_motor",
                    fase=f.valor,
                    motor=mo.valor,
                    ciudad=None,
                    n=f.n * mo.n / total.n,
                    tasa=min(max(tasa, 0.0), 1.0),
                )
            )
    for c in m.cells(foco, "espontaneo", "ciudad"):
        if c.n and c.tasa is not None:
            out.append(_Segment(f"ciudad · {c.valor}", "ciudad", None, None, c.valor, c.n, c.tasa))
    return out


def _named_city(action: Action, ciudades: list[str]) -> str | None:
    texto = fold(action.descripcion)
    for ciudad in ciudades:
        if re.search(rf"(?<!\w){re.escape(fold(ciudad))}(?!\w)", texto):
            return ciudad
    return None


def _targets(
    action: Action, findings: dict[str, Finding], segments: list[_Segment]
) -> list[_Segment]:
    ciudades = [s.ciudad for s in segments if s.ciudad]
    ciudad = _named_city(action, ciudades)
    if ciudad:
        return [s for s in segments if s.ciudad == ciudad]
    fases: set[FaseEmbudo] = (
        {action.fase_embudo}
        if action.fase_embudo
        else {
            f.fase_embudo
            for fid in action.finding_ids
            if (f := findings.get(fid)) and f.fase_embudo
        }
    )
    motores = set(action.motores_objetivo)
    return [
        s
        for s in segments
        if s.dimension == "fase_motor"
        and (not fases or s.fase in fases)
        and (not motores or s.motor in motores)
    ]


def _ignored(action: Action, findings: dict[str, Finding]) -> str | None:
    if not any(fid in findings for fid in action.finding_ids):
        return "no enlaza ningún hallazgo del estudio"
    if action.palanca == "medicion":
        return "la palanca «medición» no mueve la visibilidad"
    return None


def _delta(aportaciones: list[float], tasa: float) -> float:
    """Suma con rendimientos decrecientes, acotada por el tope y la tasa máxima."""
    ordenadas = sorted(aportaciones, reverse=True)
    suma = sum(a * DECAIMIENTO**k for k, a in enumerate(ordenadas))
    return max(0.0, min(suma, TOPE_SEGMENTO, TASA_MAXIMA - tasa))


def _profile(m: Metrics) -> AppearanceProfile:
    s = m.score_global
    tasa = (s.aparicion or 0) / 30
    q = next(
        (
            q
            for q in m.calidad_menciones
            if q.brand_id == m.marca_foco_id and q.tipo == "espontaneo"
        ),
        None,
    )
    if tasa <= 0 or q is None or q.fuerza_media is None:
        return PERFIL_SIN_APARICIONES
    return AppearanceProfile(
        tasa=tasa,
        peso_medio=(s.posicion or 0) * 3 / (20 * tasa),
        fuerza_media=q.fuerza_media,
        calidad_media=(s.calidad_fuente or 0) / (20 * tasa),
    )


def _score_at(profile: AppearanceProfile, tasa: float, brand_id: str, n: int) -> float:
    perfil = AppearanceProfile(
        tasa, profile.peso_medio, profile.fuerza_media, profile.calidad_media
    )
    return score_from_profile(brand_id, n, perfil).score or 0.0


def simulate_plan(plan: Plan, metrics: Metrics, findings: list[Finding]) -> SimulationResult:
    """Score de Citación proyectado por fase del plan (mínimo, esperado y máximo).

    Modelo, tabla y supuestos en el docstring del módulo. Determinista: misma entrada, misma
    salida.
    """
    by_id = {f.id: f for f in findings if f.study_id == metrics.study_id}
    segments = _segments(metrics)
    total = metrics.cell(metrics.marca_foco_id, "espontaneo", "global", "global")
    score_actual = metrics.score_global.score

    def result(
        tasa: float | None, proyecciones: list[PhaseProjection], segmentos: list[SegmentChange]
    ) -> SimulationResult:
        return SimulationResult(
            study_id=metrics.study_id,
            marca_foco_id=metrics.marca_foco_id,
            modelo_version=SIMULATION_VERSION,
            score_actual=score_actual,
            tasa_espontanea_actual=tasa,
            proyecciones=proyecciones,
            segmentos=segmentos,
            acciones_sin_efecto=ignoradas,
            supuestos=list(SUPUESTOS),
            advertencia=ADVERTENCIA,
        )

    ignoradas: list[IgnoredAction] = []
    activas: list[tuple[int, Action, list[_Segment]]] = []
    for indice, fase in enumerate(plan.fases):
        for action in fase.acciones:
            motivo = _ignored(action, by_id)
            targets = [] if motivo else _targets(action, by_id, segments)
            if not motivo and not targets:
                motivo = "no apunta a ningún segmento con datos"
            if motivo:
                ignoradas.append(IgnoredAction(action_id=action.id, motivo=motivo))
            else:
                activas.append((indice, action, targets))

    if total is None or total.tasa is None or not total.n or score_actual is None:
        return result(None, [], [])

    profile = _profile(metrics)
    tasa_actual = total.tasa
    score_base = _score_at(profile, tasa_actual, metrics.marca_foco_id, total.n)

    def deltas(hasta: int) -> dict[str, tuple[Rango, list[str]]]:
        aportes: dict[str, list[Rango]] = defaultdict(list)
        acciones: dict[str, list[str]] = defaultdict(list)
        for indice, action, targets in activas:
            if indice > hasta:
                continue
            rango = IMPACTO_POR_PALANCA[action.palanca][action.impacto]
            for seg in targets:
                aportes[seg.key].append(rango)
                acciones[seg.key].append(action.id)
        out: dict[str, tuple[Rango, list[str]]] = {}
        for seg in segments:
            if seg.key in aportes:
                r = aportes[seg.key]
                out[seg.key] = (
                    (
                        _delta([x[0] for x in r], seg.tasa),
                        _delta([x[1] for x in r], seg.tasa),
                        _delta([x[2] for x in r], seg.tasa),
                    ),
                    acciones[seg.key],
                )
        return out

    def escenario(valores: Rango, lo: float, hi: float) -> Escenario:
        a, b, c = (round(min(max(v, lo), hi), 4) for v in valores)
        return Escenario(minimo=a, esperado=b, maximo=c)

    proyecciones: list[PhaseProjection] = []
    finales: dict[str, tuple[Rango, list[str]]] = {}
    for indice, fase in enumerate(plan.fases):
        finales = deltas(indice)
        n_por_key = {s.key: s.n for s in segments}
        tasas = tuple(
            tasa_actual + sum(n_por_key[k] * d[0][i] for k, d in finales.items()) / total.n
            for i in range(3)
        )
        tasas_ok = tuple(min(t, 1.0) for t in tasas)
        scores = tuple(
            score_actual + _score_at(profile, t, metrics.marca_foco_id, total.n) - score_base
            for t in tasas_ok
        )
        proyecciones.append(
            PhaseProjection(
                fase=fase.nombre,
                indice=indice,
                acciones=[a.id for i, a, _ in activas if i <= indice],
                tasa_espontanea=escenario((tasas_ok[0], tasas_ok[1], tasas_ok[2]), 0.0, 1.0),
                score=escenario((scores[0], scores[1], scores[2]), 0.0, 100.0),
            )
        )

    seg_by_key = {s.key: s for s in segments}
    cambios = sorted(finales.items(), key=lambda kv: (-kv[1][0][1], kv[0]))[:TOP_SEGMENTOS]
    return result(
        tasa_actual,
        proyecciones,
        [
            SegmentChange(
                segmento=key,
                dimension=seg_by_key[key].dimension,
                n=round(seg_by_key[key].n, 2),
                tasa_actual=round(seg_by_key[key].tasa, 4),
                delta=escenario(rango, 0.0, 1.0),
                acciones=acciones,
            )
            for key, (rango, acciones) in cambios
        ],
    )

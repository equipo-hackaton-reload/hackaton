"""Rigor estadístico: intervalos de confianza y significancia de diferencias (ADR 0008).

Puro y determinista: sin I/O y con el bootstrap sembrado. Nada de aquí cambia las cifras de
`metrics`, `scoring` ni `findings`; solo les pone su margen de error.

Métodos:
- **Tasa de aparición:** intervalo de Wilson (score interval) al 95 %. Se prefiere a Wald porque
  con tasas pequeñas (Barcelona: 1 de 24) Wald da límites negativos o de amplitud cero.
- **Score de Citación:** bootstrap percentil sobre ejecuciones. Se remuestrean ejecuciones con
  reemplazo y se recalcula el score con `scoring.score_citacion`, la misma función (la fórmula no
  se duplica). `REPLICAS_BOOTSTRAP` réplicas con `SEMILLA_BOOTSTRAP`: mismo resultado siempre.
- **Diferencia de dos tasas:** intervalo de Newcombe (método 10, «hybrid score»), que combina los
  dos intervalos de Wilson. No se usa Wald por el mismo motivo que arriba.
- **Diferencia de scores:** bootstrap percentil. Emparejado (las mismas ejecuciones remuestreadas
  para las dos marcas) si ambas son del mismo estudio; independiente entre dos estudios.

Una diferencia es significativa si y solo si su intervalo al 95 % excluye 0. No se dan p-valores:
el intervalo es la única fuente de la decisión, así que no pueden contradecirse.

Supuesto que hay que tener presente: cada ejecución se trata como una observación independiente.
Las 3 repeticiones de un mismo prompt en un motor están correlacionadas, así que los intervalos
son algo optimistas. `unidad="prompt"` remuestrea prompts enteros (bootstrap por conglomerados)
para medir cuánto.
"""

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import NormalDist, fmean
from typing import Final, Literal

from posiq.domain.findings import MAX_FUERZA_DEBIL, MAX_TASA_CIUDAD
from posiq.domain.metrics import DELTA_DIMENSIONES, TIPOS
from posiq.domain.schemas import (
    Evaluation,
    Finding,
    Metrics,
    Motor,
    PromptInstance,
    Run,
    VisibilityCell,
)
from posiq.domain.scoring import score_citacion, spontaneous_population
from posiq.domain.stats_schemas import (
    InformeRigor,
    Intervalo,
    IntervaloSegmento,
    MetodoIntervalo,
    Significancia,
    SignificanciaHallazgo,
    SignificanciaRemedicion,
    SignificanciaSegmento,
)

NIVEL: Final = 0.95
REPLICAS_BOOTSTRAP: Final = 2000
"""Réplicas del bootstrap. Con 2000, el error de Monte Carlo de los percentiles 2,5/97,5 del
score de Alborada es de unas centésimas de punto: no cambia la primera cifra decimal."""
SEMILLA_BOOTSTRAP: Final = 20261021
"""Semilla fija (fecha del ADR 0008): el mismo estudio da siempre el mismo intervalo."""

UnidadRemuestreo = Literal["ejecucion", "prompt"]
"""`ejecucion`: cada ejecución es una observación (lo que asume Wilson). `prompt`: se remuestrean
prompts enteros con todas sus ejecuciones (motores y repeticiones), para no subestimar el error
cuando las repeticiones se parecen."""


def _z(nivel: float) -> float:
    return NormalDist().inv_cdf(1 - (1 - nivel) / 2)


def _excluye_cero(inf: float, sup: float) -> bool:
    return not inf <= 0 <= sup


# --- Wilson y Newcombe ----------------------------------------------------------------------------


def _wilson_limites(apariciones: int, n: int, nivel: float) -> tuple[float, float]:
    if n <= 0:
        raise ValueError("Wilson necesita n > 0")
    if not 0 <= apariciones <= n:
        raise ValueError(f"apariciones fuera de rango: {apariciones} de {n}")
    z = _z(nivel)
    p = apariciones / n
    denominador = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denominador
    semiamplitud = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominador
    # En los extremos el límite es exacto (0 o 1); se fija para no arrastrar ruido de coma flotante.
    inf = 0.0 if apariciones == 0 else max(0.0, min(p, centro - semiamplitud))
    sup = 1.0 if apariciones == n else min(1.0, max(p, centro + semiamplitud))
    return inf, sup


def wilson(apariciones: int, n: int, nivel: float = NIVEL) -> Intervalo:
    """Intervalo de Wilson de la proporción `apariciones / n` (n > 0)."""
    inf, sup = _wilson_limites(apariciones, n, nivel)
    return Intervalo(valor=apariciones / n, inf=inf, sup=sup, n=n, nivel=nivel, metodo="wilson")


def diferencia_proporciones(
    x1: int, n1: int, x2: int, n2: int, nivel: float = NIVEL
) -> Significancia:
    """Significancia de p1 − p2 (muestras independientes) con el intervalo de Newcombe (método 10).

    Con (l_i, u_i) el intervalo de Wilson de p_i y d = p1 − p2:
        inf = d − √((p1 − l1)² + (u2 − p2)²)
        sup = d + √((u1 − p1)² + (p2 − l2)²)
    El delta se redondea a 4 decimales, como `VisibilityDelta.delta` y las cifras de los hallazgos.
    """
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = _wilson_limites(x1, n1, nivel)
    l2, u2 = _wilson_limites(x2, n2, nivel)
    d = p1 - p2
    inf = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    sup = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return _significancia(
        round(d, 4), round(inf, 4), round(sup, 4), n1 + n2, nivel, "diferencia_proporciones"
    )


def _significancia(
    delta: float, inf: float, sup: float, n: int, nivel: float, metodo: MetodoIntervalo
) -> Significancia:
    inf, sup = min(inf, delta), max(sup, delta)
    intervalo = Intervalo(valor=delta, inf=inf, sup=sup, n=n, nivel=nivel, metodo=metodo)
    return Significancia(delta=delta, intervalo=intervalo, significativa=_excluye_cero(inf, sup))


def _desplazado(intervalo: Intervalo, umbral: float, digits: int) -> Significancia:
    """Significancia de `valor − umbral` (umbral fijo) con el intervalo de `valor` desplazado."""
    delta = round(intervalo.valor - umbral, digits)
    inf = min(round(intervalo.inf - umbral, digits), delta)
    sup = max(round(intervalo.sup - umbral, digits), delta)
    desplazado = Intervalo(
        valor=delta, inf=inf, sup=sup, n=intervalo.n, nivel=intervalo.nivel, metodo=intervalo.metodo
    )
    return Significancia(delta=delta, intervalo=desplazado, significativa=_excluye_cero(inf, sup))


# --- Aparición por segmento -----------------------------------------------------------------------


def _intervalo_celda(cell: VisibilityCell, nivel: float) -> Intervalo | None:
    return wilson(cell.apariciones, cell.n, nivel) if cell.n > 0 else None


def intervalos_aparicion(
    metrics: Metrics, brand_id: str | None = None, nivel: float = NIVEL
) -> list[IntervaloSegmento]:
    """Wilson de la tasa de aparición en cada segmento de `metrics.visibilidad` de la marca.

    Por defecto, la marca foco. Mismos segmentos que las métricas: espontáneo y asistido por
    separado, y en cada uno global, motor, fase, ciudad, perfil y familia.
    """
    marca = brand_id or metrics.marca_foco_id
    return [
        IntervaloSegmento(
            brand_id=c.brand_id,
            tipo=c.tipo,
            dimension=c.dimension,
            valor=c.valor,
            intervalo=_intervalo_celda(c, nivel),
        )
        for c in metrics.visibilidad
        if c.brand_id == marca
    ]


# --- Bootstrap ------------------------------------------------------------------------------------


def _percentil(ordenados: Sequence[float], q: float) -> float:
    """Percentil con interpolación lineal (tipo 7, el de numpy por defecto)."""
    h = (len(ordenados) - 1) * q
    lo = math.floor(h)
    hi = min(lo + 1, len(ordenados) - 1)
    return ordenados[lo] + (h - lo) * (ordenados[hi] - ordenados[lo])


def _conglomerados(runs: Sequence[Run], unidad: UnidadRemuestreo) -> list[list[str]]:
    """Unidades de remuestreo (listas de run ids) en orden determinista."""
    if unidad == "ejecucion":
        return [[r] for r in sorted({r.id for r in runs})]
    grupos: dict[str, set[str]] = {}
    for r in runs:
        grupos.setdefault(r.prompt_id, set()).add(r.id)
    return [sorted(grupos[k]) for k in sorted(grupos)]


def _remuestreo(rng: random.Random, unidades: Sequence[list[str]]) -> list[str]:
    return [run_id for u in rng.choices(unidades, k=len(unidades)) for run_id in u]


def _bootstrap(
    estadistico: Callable[[list[str]], float | None],
    unidades: Sequence[list[str]],
    replicas: int,
    rng: random.Random,
) -> list[float]:
    """Valores del estadístico en cada réplica (ordenados); las réplicas sin datos se descartan."""
    valores = [estadistico(_remuestreo(rng, unidades)) for _ in range(replicas)]
    return sorted(v for v in valores if v is not None)


def _limites_percentil(valores: Sequence[float], nivel: float) -> tuple[float, float]:
    if not valores:
        raise ValueError("el bootstrap no produjo ninguna réplica con datos")
    alfa = 1 - nivel
    return _percentil(valores, alfa / 2), _percentil(valores, 1 - alfa / 2)


@dataclass(frozen=True)
class Muestra:
    """Lo que hace falta para recalcular el score de un estudio: evaluaciones, ejecuciones y
    prompts (los mismos que recibió `compute_metrics`)."""

    evaluations: list[Evaluation]
    runs: list[Run]
    prompts: list[PromptInstance]


class _Poblacion:
    """Población espontánea de una o varias marcas indexada por ejecución, para remuestrear."""

    def __init__(self, muestra: Muestra, brand_ids: Sequence[str], motor: Motor | None) -> None:
        self.prompts = muestra.prompts
        self.motor = motor
        self.por_marca: dict[str, dict[str, Evaluation]] = {}
        runs: dict[str, Run] = {}
        for b in brand_ids:
            evals: dict[str, Evaluation] = {}
            for e, r in spontaneous_population(
                muestra.evaluations, muestra.runs, muestra.prompts, b, motor
            ):
                if r.id in evals:
                    raise ValueError(f"más de una evaluación de {b} en la ejecución {r.id}")
                evals[r.id] = e
                runs[r.id] = r
            self.por_marca[b] = evals
        self.runs = [runs[k] for k in sorted(runs)]

    def score(self, brand_id: str, run_ids: Sequence[str]) -> float | None:
        evals = self.por_marca[brand_id]
        elegidas = [evals[r] for r in run_ids if r in evals]
        return score_citacion(elegidas, self.runs, self.prompts, brand_id, self.motor).score


def intervalo_score(
    muestra: Muestra,
    brand_id: str,
    motor: Motor | None = None,
    *,
    replicas: int = REPLICAS_BOOTSTRAP,
    semilla: int = SEMILLA_BOOTSTRAP,
    unidad: UnidadRemuestreo = "ejecucion",
    nivel: float = NIVEL,
) -> Intervalo | None:
    """IC bootstrap percentil del Score de Citación de `brand_id` (None si no hay población).

    `valor` es el score de `score_citacion` sobre la muestra completa (el mismo de las métricas);
    `n`, el número de ejecuciones de su población.
    """
    poblacion = _Poblacion(muestra, [brand_id], motor)
    valor = poblacion.score(brand_id, [r.id for r in poblacion.runs])
    if valor is None:
        return None
    valores = _bootstrap(
        lambda ids: poblacion.score(brand_id, ids),
        _conglomerados(poblacion.runs, unidad),
        replicas,
        random.Random(semilla),
    )
    inf, sup = _limites_percentil(valores, nivel)
    return Intervalo(
        valor=valor,
        inf=round(min(inf, valor), 2),
        sup=round(max(sup, valor), 2),
        n=len(poblacion.runs),
        nivel=nivel,
        metodo="bootstrap",
    )


def diferencia_scores(
    muestra: Muestra,
    brand_a: str,
    brand_b: str,
    *,
    replicas: int = REPLICAS_BOOTSTRAP,
    semilla: int = SEMILLA_BOOTSTRAP,
    unidad: UnidadRemuestreo = "ejecucion",
    nivel: float = NIVEL,
) -> Significancia | None:
    """Significancia de score(a) − score(b) en el mismo estudio, con bootstrap emparejado.

    Cada réplica remuestrea las ejecuciones espontáneas y recalcula los dos scores sobre las
    mismas ejecuciones (las dos marcas se evalúan en las mismas respuestas).
    """
    poblacion = _Poblacion(muestra, [brand_a, brand_b], None)
    todas = [r.id for r in poblacion.runs]
    a, b = poblacion.score(brand_a, todas), poblacion.score(brand_b, todas)
    if a is None or b is None:
        return None

    def delta(ids: list[str]) -> float | None:
        sa, sb = poblacion.score(brand_a, ids), poblacion.score(brand_b, ids)
        return sa - sb if sa is not None and sb is not None else None

    valores = _bootstrap(
        delta, _conglomerados(poblacion.runs, unidad), replicas, random.Random(semilla)
    )
    inf, sup = _limites_percentil(valores, nivel)
    return _significancia(
        round(a - b, 2), round(inf, 2), round(sup, 2), len(todas), nivel, "bootstrap"
    )


# --- Significancia de hallazgos -------------------------------------------------------------------

SIN_CONTRASTE_FUENTE_LIDER: Final = (
    "Es un recuento de ejecuciones en las que el dominio acompaña al líder y la marca no aparece. "
    "No hay una tasa de referencia con la que compararlo, y las ejecuciones del líder y de la "
    "marca son las mismas (no son muestras independientes)."
)
SIN_CONTRASTE_MENCIONES: Final = (
    "Es un recuento de casos concretos, cada uno con su evaluación: no es una estimación de una "
    "tasa y no hay hipótesis nula que contrastar. Basta con un caso para que exista."
)


def _sufijo(f: Finding) -> str:
    return f.origen_cifra.split(":", 1)[1].strip() if ":" in f.origen_cifra else ""


def _celda(m: Metrics, tipo: str, dimension: str, valor: str) -> VisibilityCell:
    for c in m.visibilidad:
        if (c.brand_id, c.tipo, c.dimension, c.valor) == (m.marca_foco_id, tipo, dimension, valor):
            if c.n == 0:
                raise ValueError(f"segmento sin datos: {tipo}/{dimension}/{valor}")
            return c
    raise ValueError(f"segmento inexistente: {tipo}/{dimension}/{valor}")


def _diferencia_celdas(a: VisibilityCell, b: VisibilityCell, nivel: float) -> Significancia:
    return diferencia_proporciones(a.apariciones, a.n, b.apariciones, b.n, nivel)


def _caida_embudo(f: Finding, m: Metrics, nivel: float) -> SignificanciaHallazgo:
    desde, hasta = (s.strip() for s in _sufijo(f).split("−", 1))
    a = _celda(m, "espontaneo", "fase", desde)
    b = _celda(m, "espontaneo", "fase", hasta)
    return SignificanciaHallazgo(
        finding_id=f.id,
        contraste=f"tasa espontánea en {desde} − tasa en {hasta} (Newcombe)",
        significancia=_diferencia_celdas(a, b, nivel),
    )


def _motor_debil(f: Finding, m: Metrics, nivel: float) -> SignificanciaHallazgo:
    debil = _celda(m, "espontaneo", "motor", _sufijo(f))
    # Mismo criterio que la regla: el motor con mayor tasa entre los que tienen datos.
    fuerte = max(
        (c for c in m.cells(m.marca_foco_id, "espontaneo", "motor") if c.tasa is not None),
        key=lambda c: c.tasa or 0,
    )
    return SignificanciaHallazgo(
        finding_id=f.id,
        contraste=f"tasa espontánea en {fuerte.valor} − tasa en {debil.valor} (Newcombe)",
        significancia=_diferencia_celdas(fuerte, debil, nivel),
    )


def _ciudad_baja(f: Finding, m: Metrics, nivel: float) -> SignificanciaHallazgo:
    ciudad = _sufijo(f)
    cell = _celda(m, "espontaneo", "ciudad", ciudad)
    intervalo = wilson(cell.apariciones, cell.n, nivel)
    if intervalo.valor < MAX_TASA_CIUDAD:
        umbral, texto = MAX_TASA_CIUDAD, f"el umbral del {MAX_TASA_CIUDAD * 100:.0f} %"
    else:
        # La regla también salta con tasa < mitad de la global; se toma esa mitad como fija.
        umbral = _celda(m, "espontaneo", "global", "global").apariciones / (
            2 * _celda(m, "espontaneo", "global", "global").n
        )
        texto = "la mitad de la tasa global"
    return SignificanciaHallazgo(
        finding_id=f.id,
        contraste=f"tasa espontánea en {ciudad} − {texto} (Wilson)",
        significancia=_desplazado(intervalo, umbral, 4),
    )


def _brecha_lider(
    f: Finding, m: Metrics, muestra: Muestra, replicas: int, semilla: int, nivel: float
) -> SignificanciaHallazgo:
    if m.lider_id is None:
        raise ValueError("F-brecha-lider sin líder en las métricas")
    s = diferencia_scores(
        muestra, m.lider_id, m.marca_foco_id, replicas=replicas, semilla=semilla, nivel=nivel
    )
    if s is None:
        raise ValueError("F-brecha-lider sin población espontánea del líder o de la marca")
    return SignificanciaHallazgo(
        finding_id=f.id,
        contraste="score del líder − score de la marca (bootstrap emparejado por ejecuciones)",
        significancia=s,
    )


def _asistida(f: Finding, m: Metrics, nivel: float) -> SignificanciaHallazgo:
    asi = _celda(m, "asistido", "global", "global")
    esp = _celda(m, "espontaneo", "global", "global")
    return SignificanciaHallazgo(
        finding_id=f.id,
        contraste="tasa asistida − tasa espontánea (Newcombe)",
        significancia=_diferencia_celdas(asi, esp, nivel),
    )


def _recomendacion_debil(
    f: Finding, m: Metrics, muestra: Muestra, replicas: int, semilla: int, nivel: float
) -> SignificanciaHallazgo:
    poblacion = _Poblacion(muestra, [m.marca_foco_id], None)
    evals = poblacion.por_marca[m.marca_foco_id]
    apariciones = [r for r in sorted(evals) if evals[r].aparece]
    if not apariciones:
        raise ValueError("F-recomendacion-debil sin apariciones espontáneas")

    def fuerza_media(ids: Sequence[str]) -> float:
        return fmean(evals[r].fuerza for r in ids)

    valor = round(fuerza_media(apariciones), 3)
    valores = _bootstrap(
        lambda ids: fuerza_media(ids), [[r] for r in apariciones], replicas, random.Random(semilla)
    )
    inf, sup = _limites_percentil(valores, nivel)
    intervalo = Intervalo(
        valor=valor,
        inf=min(round(inf, 3), valor),
        sup=max(round(sup, 3), valor),
        n=len(apariciones),
        nivel=nivel,
        metodo="bootstrap",
    )
    return SignificanciaHallazgo(
        finding_id=f.id,
        contraste=(
            f"fuerza media de las apariciones espontáneas − {_es(MAX_FUERZA_DEBIL, 1)} (bootstrap)"
        ),
        significancia=_desplazado(intervalo, MAX_FUERZA_DEBIL, 3),
    )


def significancia_hallazgos(
    findings: Sequence[Finding],
    metrics: Metrics,
    muestra: Muestra,
    *,
    replicas: int = REPLICAS_BOOTSTRAP,
    semilla: int = SEMILLA_BOOTSTRAP,
    nivel: float = NIVEL,
) -> dict[str, SignificanciaHallazgo]:
    """Para cada hallazgo de `detect_findings`, si la diferencia que describe es significativa.

    No toca los hallazgos: devuelve un diccionario `finding_id → SignificanciaHallazgo`.
    - caida_embudo, motor_debil, asistida_vs_espontanea: diferencia de tasas (Newcombe).
    - ciudad_baja: tasa de la ciudad frente al umbral fijo que disparó la regla (Wilson).
    - brecha_lider: diferencia de scores con bootstrap emparejado.
    - recomendacion_debil: fuerza media frente a 1,5 (bootstrap de las apariciones).
    - fuente_lider y menciones_negativas: no admiten contraste (motivo en `sin_contraste`).
    """
    out: dict[str, SignificanciaHallazgo] = {}
    for f in findings:
        if f.id == "F-caida-embudo":
            r = _caida_embudo(f, metrics, nivel)
        elif f.id == "F-motor-debil":
            r = _motor_debil(f, metrics, nivel)
        elif f.id.startswith("F-ciudad-"):
            r = _ciudad_baja(f, metrics, nivel)
        elif f.id == "F-brecha-lider":
            r = _brecha_lider(f, metrics, muestra, replicas, semilla, nivel)
        elif f.id == "F-asistida-vs-espontanea":
            r = _asistida(f, metrics, nivel)
        elif f.id == "F-recomendacion-debil":
            r = _recomendacion_debil(f, metrics, muestra, replicas, semilla, nivel)
        elif f.id == "F-fuente-lider":
            r = SignificanciaHallazgo(
                finding_id=f.id,
                contraste="recuento de ejecuciones del líder con el dominio y sin la marca",
                sin_contraste=SIN_CONTRASTE_FUENTE_LIDER,
            )
        elif f.id == "F-menciones-negativas":
            r = SignificanciaHallazgo(
                finding_id=f.id,
                contraste="recuento de menciones negativas o por desconocimiento",
                sin_contraste=SIN_CONTRASTE_MENCIONES,
            )
        else:
            r = SignificanciaHallazgo(
                finding_id=f.id,
                contraste="regla desconocida",
                sin_contraste=f"No hay contraste definido para el hallazgo {f.id}.",
            )
        out[f.id] = r
    return out


# --- Re-medición ----------------------------------------------------------------------------------


def significancia_remedicion(
    actual: Metrics,
    anterior: Metrics,
    muestra_actual: Muestra,
    muestra_anterior: Muestra,
    *,
    replicas: int = REPLICAS_BOOTSTRAP,
    semilla: int = SEMILLA_BOOTSTRAP,
    nivel: float = NIVEL,
) -> SignificanciaRemedicion:
    """Significancia de cada delta de `diff_metrics(actual, anterior)`, sin cambiarlo.

    - Tasas (mismos segmentos que `VisibilityDelta`): Newcombe; None si un lado no tiene datos.
    - Score de la marca foco: bootstrap independiente (cada estudio se remuestrea por separado).
    Las muestras deben ser las de cada medición: si el score recalculado no coincide con el de las
    métricas, es un error (se estarían comparando datos que no son los medidos).
    """
    if actual.marca_foco_id != anterior.marca_foco_id:
        raise ValueError(
            f"marcas foco distintas: {actual.marca_foco_id} frente a {anterior.marca_foco_id}"
        )
    foco = actual.marca_foco_id
    tasas: list[SignificanciaSegmento] = []
    for tipo in TIPOS:
        for dimension in DELTA_DIMENSIONES:
            ahora = {c.valor: c for c in actual.cells(foco, tipo, dimension)}
            antes = {c.valor: c for c in anterior.cells(foco, tipo, dimension)}
            for valor in [*ahora, *(v for v in antes if v not in ahora)]:
                a, b = ahora.get(valor), antes.get(valor)
                s = _diferencia_celdas(a, b, nivel) if a and b and a.n and b.n else None
                tasas.append(
                    SignificanciaSegmento(
                        tipo=tipo, dimension=dimension, valor=valor, significancia=s
                    )
                )

    pob_a = _Poblacion(muestra_actual, [foco], None)
    pob_b = _Poblacion(muestra_anterior, [foco], None)
    sa = pob_a.score(foco, [r.id for r in pob_a.runs])
    sb = pob_b.score(foco, [r.id for r in pob_b.runs])
    for nombre, recalculado, medido in (
        ("actual", sa, actual.score_global.score),
        ("anterior", sb, anterior.score_global.score),
    ):
        if recalculado != medido:
            raise ValueError(
                f"la muestra {nombre} da score {recalculado}, pero las métricas dicen {medido}"
            )

    score: Significancia | None = None
    if sa is not None and sb is not None:
        rng = random.Random(semilla)
        unidades_a = _conglomerados(pob_a.runs, "ejecucion")
        unidades_b = _conglomerados(pob_b.runs, "ejecucion")
        deltas: list[float] = []
        for _ in range(replicas):
            ra = pob_a.score(foco, _remuestreo(rng, unidades_a))
            rb = pob_b.score(foco, _remuestreo(rng, unidades_b))
            if ra is not None and rb is not None:
                deltas.append(ra - rb)
        inf, sup = _limites_percentil(sorted(deltas), nivel)
        score = _significancia(
            round(sa - sb, 2),
            round(inf, 2),
            round(sup, 2),
            len(pob_a.runs) + len(pob_b.runs),
            nivel,
            "bootstrap",
        )

    return SignificanciaRemedicion(
        study_id=actual.study_id,
        comparado_con=anterior.study_id,
        marca_foco_id=foco,
        score=score,
        tasas=tasas,
    )


# --- Informe --------------------------------------------------------------------------------------


def informe_rigor(
    metrics: Metrics,
    findings: Sequence[Finding],
    muestra: Muestra,
    *,
    replicas: int = REPLICAS_BOOTSTRAP,
    semilla: int = SEMILLA_BOOTSTRAP,
    nivel: float = NIVEL,
) -> InformeRigor:
    """IC del score de la marca foco, Wilson de su aparición por segmento y significancia de los
    hallazgos, todo con la misma semilla y réplicas."""
    hallazgos = significancia_hallazgos(
        findings, metrics, muestra, replicas=replicas, semilla=semilla, nivel=nivel
    )
    return InformeRigor(
        study_id=metrics.study_id,
        marca_foco_id=metrics.marca_foco_id,
        score=intervalo_score(
            muestra, metrics.marca_foco_id, replicas=replicas, semilla=semilla, nivel=nivel
        ),
        aparicion=intervalos_aparicion(metrics, nivel=nivel),
        hallazgos=[hallazgos[f.id] for f in findings],
        replicas_bootstrap=replicas,
        semilla_bootstrap=semilla,
    )


def _es(x: float, decimales: int) -> str:
    """Coma decimal y signo menos tipográfico («−0,26»)."""
    texto = f"{x:.{decimales}f}".replace(".", ",")
    return texto.replace("-", "−") if x < 0 and texto.strip("-0,") else texto.lstrip("-")


def formato_intervalo(intervalo: Intervalo, decimales: int = 1, porcentaje: bool = False) -> str:
    """«25,9 [21,6–30,1]» o, con `porcentaje`, «15 % [8–26 %]» (coma decimal, raya entre límites).

    Si el límite inferior es negativo, los límites se separan con «;» para que el signo no se
    confunda con la raya: «−0,26 [−0,29; −0,10]».
    """
    k = 100 if porcentaje else 1
    valor, inf, sup = (
        _es(x * k, decimales) for x in (intervalo.valor, intervalo.inf, intervalo.sup)
    )
    sep = "; " if inf.startswith("−") else "–"
    return f"{valor} % [{inf}{sep}{sup} %]" if porcentaje else f"{valor} [{inf}{sep}{sup}]"


def formato_margen(intervalo: Intervalo, decimales: int = 0, porcentaje: bool = True) -> str:
    """«± 9 pp» (porcentaje) o «± 1,9»: la semiamplitud mayor del intervalo."""
    if porcentaje:
        return f"± {_es(intervalo.margen * 100, decimales)} pp"
    return f"± {_es(intervalo.margen, decimales)}"

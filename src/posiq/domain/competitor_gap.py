"""Competidores que cree el cliente frente a los que pone la IA (ADR 0012). Puro, sin I/O.

«Creías que tu rival era X, pero la IA te compara con Y.» Cruza
`BriefSummary.competidores_declarados` con lo medido
(`Metrics.ranking`, scores y visibilidad espontánea global):

1. Resuelve cada competidor declarado a un `brand_id` del mercado por nombre, alias o id, sin
   acentos ni mayúsculas (`text.fold`). Si no hay coincidencia exacta, acepta una única marca cuyo
   nombre o alias aparezca como palabras completas dentro del nombre declarado (o al revés):
   «Grupo Valdecruz» → «Grupo Hospitalario Valdecruz» por el alias «Valdecruz». Si casan varias,
   es ambiguo y queda en `no_resueltos`.
2. `no_declarados_por_delante`: marcas por delante de la foco en el ranking que el brief no declara.
   Son «sorpresa» las que le sacan ≥ `MIN_VENTAJA_PUNTOS` de Score de Citación.
3. `declarados_poco_mencionados`: declarados con datos cuya tasa espontánea global es menor que
   `max(MIN_TASA_ABSOLUTA, FRACCION_TASA_FOCO × tasa de la foco)`.

Hallazgos (tipos y campos de `schemas.Finding`, sin cambiar el contrato):
- `F-competidor-no-declarado`: si hay sorpresas. Cifra = mayor ventaja (puntos). Impacto L si esa
  ventaja ≥ `VENTAJA_IMPACTO_L` · M.
- `F-declarado-poco-visible`: si hay declarados poco mencionados. Cifra = la menor tasa espontánea
  (fracción). Impacto S: corrige el radar del cliente, no su visibilidad.
`evaluation_ids` = las evaluaciones espontáneas globales de las marcas que respaldan la cifra.
"""

import re
from typing import Final

from posiq.domain.competitor_gap_schemas import BrechaCompetidores, CompetidorMedido
from posiq.domain.findings import confidence_for
from posiq.domain.schemas import Brand, BriefSummary, Finding, Market, Metrics
from posiq.domain.text import fold, slugify

MIN_VENTAJA_PUNTOS: Final = 5.0
VENTAJA_IMPACTO_L: Final = 10.0
MIN_TASA_ABSOLUTA: Final = 0.10
FRACCION_TASA_FOCO: Final = 0.5


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", fold(text)).split())


def _nombres(brand: Brand) -> set[str]:
    return {n for n in (_norm(x) for x in [brand.nombre, brand.id, *brand.aliases]) if n}


def _contiene(largo: str, corto: str) -> bool:
    return f" {corto} " in f" {largo} "


def resolver_competidor(nombre: str, market: Market) -> Brand | None:
    """Marca del mercado que corresponde a un nombre del brief, o None si no casa o es ambiguo."""
    buscado = _norm(nombre)
    if not buscado:
        return None
    exactas = [b for b in market.marcas if buscado in _nombres(b) or slugify(nombre) == b.id]
    if len(exactas) == 1:
        return exactas[0]
    if exactas:
        return None
    parciales = [
        b
        for b in market.marcas
        if any(_contiene(buscado, n) or _contiene(n, buscado) for n in _nombres(b))
    ]
    return parciales[0] if len(parciales) == 1 else None


def _num(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def _pct(x: float) -> str:
    return f"{x * 100:.0f} %"


def _medido(
    brand: Brand, metrics: Metrics, score_foco: float | None, declarado: str | None
) -> CompetidorMedido:
    s = metrics.score_of(brand.id)
    cell = metrics.cell(brand.id, "espontaneo", "global", "global")
    score = s.score if s else None
    return CompetidorMedido(
        brand_id=brand.id,
        nombre=brand.nombre,
        declarado=declarado is not None,
        nombre_declarado=declarado,
        puesto=metrics.ranking.index(brand.id) + 1 if brand.id in metrics.ranking else None,
        score=score,
        ventaja_puntos=(
            round(score - score_foco, 2) if score is not None and score_foco is not None else None
        ),
        tasa_espontanea=cell.tasa if cell else None,
        n_espontaneo=cell.n if cell else 0,
    )


def _ids(metrics: Metrics, brand_ids: list[str]) -> list[str]:
    out: list[str] = []
    for bid in brand_ids:
        cell = metrics.cell(bid, "espontaneo", "global", "global")
        if cell:
            out.extend(cell.evaluation_ids)
    return out


def _lista(nombres: list[str]) -> str:
    return nombres[0] if len(nombres) == 1 else f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _hallazgo_no_declarados(r: BrechaCompetidores, metrics: Metrics) -> Finding | None:
    sorpresas = [c for c in r.no_declarados_por_delante if c.brand_id in r.sorpresas]
    ids = _ids(metrics, [c.brand_id for c in sorpresas])
    if not sorpresas or not ids:
        return None
    top = max(sorpresas, key=lambda c: c.ventaja_puntos or 0)
    ventaja = top.ventaja_puntos or 0
    detalle = "; ".join(
        f"{c.nombre}, {c.puesto}.ª con {_num(c.score or 0)} puntos (+{_num(c.ventaja_puntos or 0)})"
        for c in sorpresas
    )
    declarados = _lista([c.nombre for c in r.declarados]) if r.declarados else "ninguno"
    return Finding(
        id="F-competidor-no-declarado",
        study_id=metrics.study_id,
        titulo=(
            f"La IA compara a la marca con {_lista([c.nombre for c in sorpresas])}, "
            "que el brief no declara como competidor"
        ),
        descripcion=(
            f"El brief declara como competidores a {declarados}, pero los asistentes ponen por "
            f"delante de la marca ({r.puesto_foco}.ª de {r.n_marcas}, "
            f"{_num(r.score_foco or 0)} puntos) a marcas que no están en ese radar: {detalle}."
        ),
        impacto="L" if ventaja >= VENTAJA_IMPACTO_L else "M",
        confianza=confidence_for(min(c.n_espontaneo for c in sorpresas)),
        cifra=round(ventaja, 2),
        unidad="puntos",
        origen_cifra="score de citación: competidor no declarado − marca foco",
        evaluation_ids=ids,
    )


def _hallazgo_poco_visibles(r: BrechaCompetidores, metrics: Metrics) -> Finding | None:
    flojos = [c for c in r.declarados if c.brand_id in r.declarados_poco_mencionados]
    ids = _ids(metrics, [c.brand_id for c in flojos])
    if not flojos or not ids:
        return None
    menor = min(c.tasa_espontanea or 0 for c in flojos)
    detalle = "; ".join(
        f"{c.nombre}, en el {_pct(c.tasa_espontanea or 0)} de {c.n_espontaneo} respuestas"
        for c in flojos
    )
    return Finding(
        id="F-declarado-poco-visible",
        study_id=metrics.study_id,
        titulo=(
            f"Los asistentes apenas mencionan a {_lista([c.nombre for c in flojos])}, "
            "que el brief declara como competidor"
        ),
        descripcion=(
            f"Visibilidad espontánea de competidores declarados: {detalle}, frente al "
            f"{_pct(r.tasa_foco or 0)} de la marca. "
            "En los asistentes de IA no es el rival a vigilar."
        ),
        impacto="S",
        confianza=confidence_for(min(c.n_espontaneo for c in flojos)),
        cifra=round(menor, 4),
        unidad="fraccion",
        origen_cifra="visibilidad espontánea global del competidor declarado",
        evaluation_ids=ids,
    )


def brecha_competidores(
    brief: BriefSummary, market: Market, metrics: Metrics
) -> BrechaCompetidores:
    """Contrasta los competidores declarados en el brief con el ranking medido."""
    foco_id = metrics.marca_foco_id
    score_foco = metrics.score_global.score
    cell_foco = metrics.cell(foco_id, "espontaneo", "global", "global")
    tasa_foco = cell_foco.tasa if cell_foco else None
    puesto_foco = metrics.ranking.index(foco_id) + 1 if foco_id in metrics.ranking else None

    declarados: dict[str, str] = {}
    no_resueltos: list[str] = []
    for nombre in brief.competidores_declarados:
        brand = resolver_competidor(nombre, market)
        if brand is None:
            if nombre.strip() and nombre not in no_resueltos:
                no_resueltos.append(nombre)
        elif brand.id != foco_id:
            declarados.setdefault(brand.id, nombre)

    marcas = {b.id: b for b in market.marcas}
    orden = {bid: i for i, bid in enumerate(metrics.ranking)}
    medidos_decl = sorted(
        (_medido(marcas[bid], metrics, score_foco, n) for bid, n in declarados.items()),
        key=lambda c: (orden.get(c.brand_id, len(orden)), c.brand_id),
    )
    delante = metrics.ranking[: puesto_foco - 1] if puesto_foco else []
    no_decl = [
        _medido(marcas[bid], metrics, score_foco, None)
        for bid in delante
        if bid in marcas and bid not in declarados
    ]
    sorpresas = [
        c.brand_id
        for c in no_decl
        if c.ventaja_puntos is not None and c.ventaja_puntos >= MIN_VENTAJA_PUNTOS
    ]
    umbral_tasa = max(MIN_TASA_ABSOLUTA, FRACCION_TASA_FOCO * (tasa_foco or 0))
    poco = [
        c.brand_id
        for c in medidos_decl
        if c.n_espontaneo > 0 and c.tasa_espontanea is not None and c.tasa_espontanea < umbral_tasa
    ]
    base = BrechaCompetidores(
        study_id=metrics.study_id,
        marca_foco_id=foco_id,
        puesto_foco=puesto_foco,
        score_foco=score_foco,
        tasa_foco=tasa_foco,
        n_marcas=len(metrics.ranking),
        declarados=medidos_decl,
        no_resueltos=no_resueltos,
        no_declarados_por_delante=no_decl,
        sorpresas=sorpresas,
        declarados_poco_mencionados=poco,
        umbral_ventaja_puntos=MIN_VENTAJA_PUNTOS,
        umbral_tasa=round(umbral_tasa, 4),
    )
    hallazgos = [
        f
        for f in (_hallazgo_no_declarados(base, metrics), _hallazgo_poco_visibles(base, metrics))
        if f is not None
    ]
    return base.model_copy(update={"hallazgos": hallazgos})

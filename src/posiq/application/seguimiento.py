"""Seguimiento por marca: orquestación sobre `domain/tracking.py` (ADR 0016).

La serie (puntos, comparabilidad, cambios significativos, indicadores y resumen) la calcula el
dominio. Aquí solo se reúnen las mediciones de una marca a partir de los estudios completados que
el usuario puede ver, con lo que guardó cada estudio en su checkpoint.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from posiq.application.runner import StudyRunner
from posiq.domain.schemas import Source, Study
from posiq.domain.stats import Muestra
from posiq.domain.tracking import MedicionSerie, construir_serie
from posiq.domain.tracking_schemas import SerieMarca

COMPLETADO = "completado"


@dataclass(frozen=True)
class ResumenMarca:
    brand_id: str
    nombre: str
    n_mediciones: int
    ultima_medicion: datetime | None


def resumen_marcas(studies: Sequence[Study]) -> list[ResumenMarca]:
    """Una entrada por marca con estudios: mediciones completadas y fecha de la última.

    Los estudios que aún no tienen marca (antes de `market`) no cuentan. Orden: la marca con la
    medición más reciente primero; las que aún no tienen ninguna, al final por nombre.
    """
    por_marca: dict[str, list[Study]] = {}
    for s in studies:
        if s.brand_id:
            por_marca.setdefault(s.brand_id, []).append(s)
    out: list[ResumenMarca] = []
    for brand_id, propios in por_marca.items():
        hechos = [s for s in propios if s.estado == COMPLETADO]
        ultimo = max(hechos, key=lambda s: s.creado_en, default=None)
        nombre = (ultimo or max(propios, key=lambda s: s.creado_en)).brief.marca
        out.append(
            ResumenMarca(
                brand_id=brand_id,
                nombre=nombre or brand_id,
                n_mediciones=len(hechos),
                ultima_medicion=ultimo.creado_en if ultimo else None,
            )
        )
    con_fecha = [m for m in out if m.ultima_medicion is not None]
    con_fecha.sort(key=lambda m: m.ultima_medicion.timestamp() if m.ultima_medicion else 0.0)
    sin_fecha = sorted((m for m in out if m.ultima_medicion is None), key=lambda m: m.nombre)
    return [*reversed(con_fecha), *sin_fecha]


async def mediciones(
    runner: StudyRunner, studies: Sequence[Study], catalogo: Sequence[Source]
) -> list[MedicionSerie]:
    """La medición de cada estudio completado, con su muestra, mercado, exactitud y trazas."""
    out: list[MedicionSerie] = []
    for study in studies:
        if study.estado != COMPLETADO:
            continue
        values, _ = await runner.state(study.id)
        metrics = values.get("metrics")
        if metrics is None:
            continue
        exactitud = values.get("exactitud") or []
        out.append(
            MedicionSerie(
                study=study,
                metrics=metrics,
                muestra=Muestra(
                    evaluations=list(values.get("evaluations", [])),
                    runs=list(values.get("runs", [])),
                    prompts=list(values.get("prompts", [])),
                ),
                market=values.get("market"),
                catalogo=tuple(catalogo),
                exactitud=exactitud[0] if exactitud else None,
                trazas=tuple(values.get("traces", [])),
            )
        )
    return out


def serie(brand_id: str, meds: Sequence[MedicionSerie]) -> SerieMarca | None:
    """Serie del dominio (CPU: bootstraps); None si la marca no tiene mediciones completadas."""
    if not meds:
        return None
    ultima = max(meds, key=lambda m: m.study.creado_en)
    return construir_serie(brand_id, ultima.study.brief.marca or brand_id, meds)

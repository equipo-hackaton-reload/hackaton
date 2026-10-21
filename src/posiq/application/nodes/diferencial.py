"""Nodo `diferencial`: rigor, competidores, oportunidades de fuente y exactitud; sin LLM.

Va tras `analyze` y antes de `plan`. Todo lo calcula `domain/` (código determinista, coste 0):

- `rigor`: IC bootstrap del score (global y por motor), Wilson de la aparición por motor,
  significancia de cada hallazgo (`domain.stats`) y, en una re-medición, de cada delta.
- `competidores`: declarados en el brief frente a los que pone la IA (`domain.competitor_gap`).
- `oportunidades_fuente`: mapa de fuentes del sector con este único estudio y las fuentes donde
  la marca está por debajo de sus competidores (`domain.source_map`).
- `exactitud` y `mitigaciones`: lo que dicen los motores de la marca del brief, contrastado con el
  brief, solo por reglas (`domain.accuracy`). Solo para la marca del brief: el brief es la verdad
  con la que se compara.

Los escenarios dependen del plan: los calcula `escenarios_del_plan`, que llaman `plan` y
`review_plan` (si la persona edita el plan).

Coste en tiempo: el bootstrap (2000 réplicas, `REPLICAS_BOOTSTRAP`) es lo caro; con Alborada el
bloque entero tarda de 2 a 4 s según la máquina (≈1,4 s el informe, ≈0,5 s los cuatro motores,
≈0,8 s la exactitud). Se calcula en un hilo (`asyncio.to_thread`) para no bloquear el bucle de
eventos de la API. Un bloque que falla (p. ej. datos insuficientes en modo real) queda en None y
se anota en `errores`; no para el estudio.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from posiq.application.deps import Deps
from posiq.application.diferencial import EscenarioGuardado, MedicionAnterior, Rigor
from posiq.application.kit import load_sources
from posiq.application.state import StudyState
from posiq.domain.accuracy import evaluar_exactitud
from posiq.domain.competitor_gap import brecha_competidores
from posiq.domain.scenarios import build_presets
from posiq.domain.schemas import Finding, Metrics, Plan, Source
from posiq.domain.source_map import DatosEstudio, mapa_fuentes, oportunidades_fuente
from posiq.domain.source_map_schemas import OportunidadFuente
from posiq.domain.stats import (
    REPLICAS_BOOTSTRAP,
    SEMILLA_BOOTSTRAP,
    Muestra,
    aparicion_por_motor,
    informe_rigor,
    intervalos_score_por_motor,
    significancia_remedicion,
)
from posiq.domain.stats_schemas import Significancia

log = logging.getLogger(__name__)

ESCENARIO_ELEGIDO = "completo"
"""El plan aprobado entero: es el escenario que usa la propuesta mientras nadie elija otro."""


def rigor(
    state: StudyState,
    *,
    replicas: int = REPLICAS_BOOTSTRAP,
    semilla: int = SEMILLA_BOOTSTRAP,
) -> Rigor:
    """Intervalos y significancias del estudio (y de sus deltas si es una re-medición)."""
    metrics = state["metrics"]
    muestra = Muestra(state["evaluations"], state["runs"], state["prompts"])
    informe = informe_rigor(metrics, state["findings"], muestra, replicas=replicas, semilla=semilla)
    deltas: dict[str, Significancia] = {}
    anterior: MedicionAnterior | None = state.get("medicion_anterior")
    if anterior is not None and metrics.comparado_con == anterior["study_id"]:
        deltas = significancia_remedicion(
            metrics,
            anterior["metrics"],
            muestra,
            Muestra(anterior["evaluations"], anterior["runs"], anterior["prompts"]),
            replicas=replicas,
            semilla=semilla,
        ).por_clave()
    return Rigor(
        score_global=informe.score,
        score_por_motor=intervalos_score_por_motor(
            muestra, metrics.marca_foco_id, replicas=replicas, semilla=semilla
        ),
        aparicion_por_motor=aparicion_por_motor(metrics),
        hallazgos={h.finding_id: h for h in informe.hallazgos},
        deltas=deltas,
        replicas_bootstrap=informe.replicas_bootstrap,
        semilla_bootstrap=informe.semilla_bootstrap,
    )


def oportunidades(state: StudyState, catalogo: Sequence[Source]) -> list[OportunidadFuente]:
    """Oportunidades de fuente de la marca foco, con el mapa del sector de este único estudio."""
    estudio = DatosEstudio(state["market"], state["prompts"], state["runs"], state["evaluations"])
    mapa = mapa_fuentes(state["brief"].sector, [estudio], catalogo)
    return oportunidades_fuente(mapa, estudio, state["metrics"].marca_foco_id, catalogo)


def exactitud(state: StudyState) -> dict[str, Any]:
    """Exactitud de lo que dicen los motores de la marca del brief, solo por reglas (coste 0)."""
    metrics, market, brief = state["metrics"], state["market"], state["brief"]
    marca = next(b for b in market.marcas if b.id == metrics.marca_foco_id)
    hallazgo, acciones = evaluar_exactitud(
        state["study_id"],
        marca,
        brief,
        state["runs"],
        marcas=market.marcas,
        ciudades=brief.ciudades,
    )
    return {"exactitud": [hallazgo], "mitigaciones": acciones}


def calcular(state: StudyState, catalogo: Sequence[Source]) -> dict[str, Any]:
    """Los bloques del diferencial. Cada uno se calcula por separado: si uno falla, queda en None
    con el motivo en `errores` y los demás siguen."""
    update: dict[str, Any] = {}
    errores: list[str] = []

    def bloque(nombres: tuple[str, ...], fn: Callable[[], dict[str, Any]]) -> None:
        try:
            update.update(fn())
        except (ValueError, KeyError, StopIteration) as exc:
            log.warning("diferencial: %s sin calcular en %s", nombres, state["study_id"])
            update.update(dict.fromkeys(nombres))
            errores.append(f"diferencial: {', '.join(nombres)} sin calcular: {exc}")

    bloque(("rigor",), lambda: {"rigor": rigor(state)})
    bloque(
        ("competidores",),
        lambda: {
            "competidores": brecha_competidores(state["brief"], state["market"], state["metrics"])
        },
    )
    bloque(
        ("oportunidades_fuente",),
        lambda: {"oportunidades_fuente": oportunidades(state, catalogo)},
    )
    bloque(("exactitud", "mitigaciones"), lambda: exactitud(state))
    return {**update, "errores": errores}


async def diferencial(state: StudyState, deps: Deps) -> dict[str, Any]:
    catalogo = load_sources(str(Path(deps.settings.kit_dir).resolve()))
    # El bootstrap tarda segundos: fuera del bucle de eventos, como las llamadas al repositorio.
    return await asyncio.to_thread(calcular, state, catalogo)


def escenarios_del_plan(
    plan: Plan, findings: list[Finding], metrics: Metrics
) -> tuple[list[EscenarioGuardado] | None, list[str]]:
    """Los tres preajustes del plan (`domain.scenarios`), con el completo elegido.

    Devuelve también los errores: un plan que no admite escenarios (ids que no casan) deja
    `escenarios` en None y lo anota, sin parar el estudio.
    """
    try:
        presets = build_presets(plan, findings, metrics)
    except ValueError as exc:
        return None, [f"escenarios sin calcular: {exc}"]
    return [
        EscenarioGuardado(id=e.nombre, elegido=e.nombre == ESCENARIO_ELEGIDO, escenario=e)
        for e in presets
    ], []

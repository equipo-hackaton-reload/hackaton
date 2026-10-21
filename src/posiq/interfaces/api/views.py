"""Proyecciones del estado del grafo para la web: evidencias de los hallazgos."""

from collections.abc import Mapping, Sequence
from typing import Any

from posiq.interfaces.api.schemas import Evidence

# La web enseña un extracto de la respuesta; la respuesta íntegra queda en el repositorio.
TEXTO_MAX = 2000


def evidence(values: Mapping[str, Any], ids: Sequence[str]) -> list[Evidence]:
    """Evaluaciones `ids` (en ese orden) con el motor, el prompt y la respuesta de su ejecución.

    Los ids que no existen en el estudio, o cuya ejecución falta, se omiten.
    """
    evaluations = {e.id: e for e in values.get("evaluations", [])}
    runs = {r.id: r for r in values.get("runs", [])}
    prompts = {p.id: p.texto for p in values.get("prompts", [])}
    out: list[Evidence] = []
    for evaluation_id in ids:
        evaluation = evaluations.get(evaluation_id)
        run = runs.get(evaluation.run_id) if evaluation else None
        if evaluation is None or run is None:
            continue
        out.append(
            Evidence(
                evaluation=evaluation,
                motor=run.motor,
                prompt=prompts.get(run.prompt_id, run.prompt_id),
                texto_respuesta=run.texto_respuesta[:TEXTO_MAX],
                fuentes=[s.dominio for s in run.fuentes],
            )
        )
    return out

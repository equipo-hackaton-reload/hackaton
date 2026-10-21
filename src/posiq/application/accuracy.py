"""Capa opcional con LLM de la exactitud de marca (prompt versionado `claims.v1`).

El LLM solo propone fragmentos literales y su tipo; `domain.accuracy` descarta los que no están en
la respuesta y hace toda la verificación y los recuentos. La respuesta del motor viaja en `state`
(DATO), nunca en las instrucciones. Una llamada por ejecución que nombra la marca; cada llamada deja
su `Trace`.
"""

from collections.abc import Iterable, Sequence

from posiq.domain.accuracy import AfirmacionesLLM, afirmaciones_desde_llm, estado_claims
from posiq.domain.accuracy_schemas import Afirmacion
from posiq.domain.detection import brand_mentions
from posiq.domain.schemas import Brand, Run, Trace
from posiq.ports import LLM

PROMPT_CLAIMS = "claims.v1"


def extraer_afirmaciones_llm(
    llm: LLM,
    runs: Iterable[Run],
    brand: Brand,
    *,
    study_id: str,
    marcas: Sequence[Brand] = (),
) -> tuple[list[Afirmacion], list[Trace]]:
    """Afirmaciones (origen `llm`) de las ejecuciones que nombran `brand`, con sus trazas.

    Combínalas con las de reglas pasándolas a `domain.accuracy.evaluar_exactitud(...,
    afirmaciones_llm=...)`: allí se quitan las repetidas y se verifican igual que las de reglas.
    """
    afirmaciones: list[Afirmacion] = []
    trazas: list[Trace] = []
    for run in runs:
        if brand.id not in run.marcas_a_evaluar or not brand_mentions(run.texto_respuesta, [brand]):
            continue
        salida, traza = llm.structured(
            AfirmacionesLLM, PROMPT_CLAIMS, estado_claims(run, brand, marcas), study_id=study_id
        )
        afirmaciones.extend(afirmaciones_desde_llm(salida, run, brand))
        trazas.append(traza)
    return afirmaciones, trazas

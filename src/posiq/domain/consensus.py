"""Consenso del juez: voto por mayoría sobre N evaluaciones de la misma marca en la misma respuesta.

Puro y determinista. Lo usa `adapters/judge/consensus.ConsensusJudge`, que pide N veces la misma
evaluación y aplica `consenso` (ADR 0008).

Cómo se vota:
1. **Aparición.** Primero se vota `aparece`. Solo las evaluaciones que coinciden con el ganador
   votan el resto de campos, para que el resultado sea coherente (si no aparece, no hay posición ni
   fuerza que votar).
2. **Resto de campos.** Cada campo se vota por separado entre esas evaluaciones.
3. **Empates (regla conservadora).**
   - En los campos que entran en el score gana el valor que MENOS sube el score: `aparece` →
     False; `posicion` → la peor (número mayor); `fuerza` → la menor; `tipo_fuente` → la de menor
     calidad en `QUALITY_BY_TYPE` (sin resolver cuenta como «Sin fuente» y gana a esta).
   - En los demás (`tipo_mencion`, `sentimiento`, `apoyada_en_fuente`, `origen`) gana el valor de
     la evaluación más temprana (orden de llamada).
   Así un empate nunca infla la visibilidad de la marca.
4. **Confianza.** Para cada campo del score, acuerdo = votos del ganador / N (las evaluaciones que
   perdieron en `aparece` cuentan como desacuerdo). La confianza es el MENOR de esos acuerdos,
   como en `adapters/judge/base.score_confidence`, que toma el mínimo de los campos del score.
5. **Revisión.** `necesita_revision` si la confianza es menor que `umbral_revision`.
"""

from collections import Counter
from collections.abc import Callable, Hashable, Sequence
from typing import Final

from posiq.domain.schemas import Evaluation, TipoFuente
from posiq.domain.scoring import QUALITY_BY_TYPE
from posiq.domain.stats_schemas import ConsensoJuez

UMBRAL_REVISION_CONSENSO: Final = 0.75
"""Con N = 3 exige unanimidad para no marcar revisión; con N = 5 basta 4 de 5."""

CAMPOS_SCORE: Final = ("aparece", "posicion", "fuerza", "tipo_fuente")


def _votar[T: Hashable](
    valores: Sequence[T], desempate: Callable[[list[T]], T] | None = None
) -> tuple[T, int, bool]:
    """Ganador, sus votos y si hubo empate. Sin `desempate`, gana el que aparece antes."""
    cuenta = Counter(valores)
    maximo = max(cuenta.values())
    empatados = [v for v in dict.fromkeys(valores) if cuenta[v] == maximo]
    if len(empatados) == 1:
        return empatados[0], maximo, False
    ganador = desempate(empatados) if desempate else empatados[0]
    return ganador, maximo, True


def _calidad(tipo: TipoFuente | None) -> tuple[float, bool]:
    return (QUALITY_BY_TYPE[tipo if tipo is not None else "Sin fuente"], tipo is not None)


def consenso(
    evaluaciones: Sequence[Evaluation], *, umbral_revision: float = UMBRAL_REVISION_CONSENSO
) -> ConsensoJuez:
    """Evaluación de consenso de N evaluaciones de la misma marca en la misma ejecución."""
    if not evaluaciones:
        raise ValueError("el consenso necesita al menos una evaluación")
    claves = {(e.id, e.study_id, e.run_id, e.brand_id) for e in evaluaciones}
    if len(claves) != 1:
        raise ValueError(f"evaluaciones de respuestas o marcas distintas: {sorted(claves)}")
    n = len(evaluaciones)

    aparece, votos_aparece, empate_aparece = _votar(
        [e.aparece for e in evaluaciones], lambda vs: False
    )
    ganadoras = [e for e in evaluaciones if e.aparece == aparece]
    posicion, votos_posicion, empate_posicion = _votar(
        [e.posicion for e in ganadoras], lambda vs: max(vs, key=lambda p: p or 0)
    )
    fuerza, votos_fuerza, empate_fuerza = _votar([e.fuerza for e in ganadoras], min)
    tipo_fuente, votos_fuente, empate_fuente = _votar(
        [e.tipo_fuente for e in ganadoras], lambda vs: min(vs, key=_calidad)
    )
    tipo_mencion, _, empate_mencion = _votar([e.tipo_mencion for e in ganadoras])
    sentimiento, _, empate_sentimiento = _votar([e.sentimiento for e in ganadoras])
    apoyada, _, empate_apoyada = _votar([e.apoyada_en_fuente for e in ganadoras])
    origen, _, _ = _votar([e.origen for e in ganadoras])

    acuerdo_por_campo = {
        "aparece": votos_aparece / n,
        "posicion": votos_posicion / n,
        "fuerza": votos_fuerza / n,
        "tipo_fuente": votos_fuente / n,
    }
    acuerdo = min(acuerdo_por_campo.values())
    empates = [
        campo
        for campo, empate in (
            ("aparece", empate_aparece),
            ("posicion", empate_posicion),
            ("fuerza", empate_fuerza),
            ("tipo_fuente", empate_fuente),
            ("tipo_mencion", empate_mencion),
            ("sentimiento", empate_sentimiento),
            ("apoyada_en_fuente", empate_apoyada),
        )
        if empate
    ]
    # Se revalida el modelo entero: un consenso incoherente no puede salir de aquí.
    evaluacion = Evaluation.model_validate(
        ganadoras[0].model_dump(exclude={"peso_posicion", "por_desconocimiento"})
        | {
            "posicion": posicion,
            "fuerza": fuerza,
            "tipo_fuente": tipo_fuente,
            "tipo_mencion": tipo_mencion,
            "sentimiento": sentimiento,
            "apoyada_en_fuente": apoyada,
            "origen": origen,
            "confianza": acuerdo,
            "necesita_revision": acuerdo < umbral_revision,
        }
    )
    return ConsensoJuez(
        evaluacion=evaluacion,
        n=n,
        acuerdo=acuerdo,
        acuerdo_por_campo=acuerdo_por_campo,
        empates=empates,
    )

"""Juez por consenso: evalúa N veces la misma marca en la misma respuesta y vota (ADR 0008).

Envuelve uno o varios jueces (`ports.Judge`) y aplica `domain.consensus.consenso`. Cumple el
puerto síncrono (`evaluate`) y lo que usa el grafo (`aevaluate_many` y `traces`).

- **Trazas:** no hace llamadas propias. Cada llamada la registra el juez interno (modelo, versión
  de las preguntas, tokens y coste) y se apunta en su presupuesto. `traces` reúne las nuevas de
  todos los jueces internos, sin duplicarlas.
- **Caché:** con caché, repetir la misma pregunta al mismo juez devuelve N veces la misma
  respuesta y el «consenso» sería falso. `repetido` lo rechaza: el juez interno va sin caché.
- **Concurrencia:** las N pasadas de un lote van una detrás de otra; cada una respeta la
  concurrencia de su juez, así que el total nunca la multiplica por N.
"""

import asyncio
from collections.abc import Sequence
from typing import Protocol

from posiq.domain.consensus import UMBRAL_REVISION_CONSENSO, consenso
from posiq.domain.schemas import Brand, Evaluation, Run, Trace
from posiq.domain.stats_schemas import ConsensoJuez


class JuezInterno(Protocol):
    """`ports.Judge` con sus trazas (lo cumplen `SystemOneJudge` y `FixtureJudge`)."""

    name: str
    traces: list[Trace]

    def evaluate(self, run: Run, brand: Brand) -> Evaluation: ...


class ConsensusJudge:
    """`ports.Judge` que vota por mayoría las evaluaciones de varios jueces (o de uno N veces)."""

    def __init__(
        self,
        jueces: Sequence[JuezInterno],
        *,
        umbral_revision: float = UMBRAL_REVISION_CONSENSO,
    ) -> None:
        if not jueces:
            raise ValueError("ConsensusJudge necesita al menos un juez")
        self.jueces = list(jueces)
        self.umbral_revision = umbral_revision
        nombres = [j.name for j in self.jueces]
        self.name = (
            f"consenso:{len(nombres)}x{nombres[0]}"
            if len(set(nombres)) == 1
            else f"consenso:{'+'.join(nombres)}"
        )
        self.traces: list[Trace] = []
        self.consensos: list[ConsensoJuez] = []
        """Detalle (acuerdo por campo y empates) de cada evaluación, en orden de llamada."""

    @classmethod
    def repetido(
        cls,
        juez: JuezInterno,
        n: int = 3,
        *,
        umbral_revision: float = UMBRAL_REVISION_CONSENSO,
    ) -> "ConsensusJudge":
        """El mismo juez llamado `n` veces. Debe ir sin caché (ver el docstring del módulo)."""
        if n < 1:
            raise ValueError("n debe ser al menos 1")
        if getattr(juez, "cache", None) is not None:
            raise ValueError(
                "el juez interno tiene caché: repetiría la misma respuesta y el consenso sería "
                "falso; constrúyelo con cache=None"
            )
        return cls([juez] * n, umbral_revision=umbral_revision)

    # --- Trazas -----------------------------------------------------------------------------------

    def _distintos(self) -> list[JuezInterno]:
        vistos: dict[int, JuezInterno] = {}
        for j in self.jueces:
            vistos.setdefault(id(j), j)
        return list(vistos.values())

    def _marca(self) -> list[int]:
        return [len(j.traces) for j in self._distintos()]

    def _recoge(self, antes: list[int]) -> None:
        for juez, desde in zip(self._distintos(), antes, strict=True):
            self.traces.extend(juez.traces[desde:])

    def _vota(self, pasadas: list[list[Evaluation]]) -> list[Evaluation]:
        resultados = [
            consenso(list(evals), umbral_revision=self.umbral_revision)
            for evals in zip(*pasadas, strict=True)
        ]
        self.consensos.extend(resultados)
        return [r.evaluacion for r in resultados]

    # --- Interfaz pública -------------------------------------------------------------------------

    def evaluate(self, run: Run, brand: Brand) -> Evaluation:
        """Síncrono: no usar dentro de un bucle de eventos en marcha si el juez interno es async."""
        antes = self._marca()
        try:
            pasadas = [[j.evaluate(run, brand)] for j in self.jueces]
        finally:
            self._recoge(antes)
        return self._vota(pasadas)[0]

    def evaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        return asyncio.run(self.aevaluate_many(pairs))

    async def aevaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        antes = self._marca()
        pasadas: list[list[Evaluation]] = []
        try:
            for juez in self.jueces:
                pasadas.append(await self._pasada(juez, pairs))
        finally:
            self._recoge(antes)
        return self._vota(pasadas)

    @staticmethod
    async def _pasada(juez: JuezInterno, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        lote = getattr(juez, "aevaluate_many", None)
        if lote is not None:
            return list(await lote(pairs))
        return await asyncio.to_thread(lambda: [juez.evaluate(r, b) for r, b in pairs])

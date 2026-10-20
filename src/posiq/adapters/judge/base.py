"""Lógica común de los jueces System One (Jev y fallback LLM): estado, caché, trazas y política.

Las preguntas son SIEMPRE las de `domain/judge_questions.py`; aquí no se redefinen. La política de
confianza vive en código con los umbrales de settings:

- confianza ≥ `JUDGE_CONFIDENCE_ACCEPT` → se acepta (`necesita_revision=False`);
- entre `JUDGE_CONFIDENCE_FALLBACK` y la de aceptación → se acepta y se marca para revisión;
- < `JUDGE_CONFIDENCE_FALLBACK` → se delega en el juez de fallback, si lo hay; si no, se marca.

La confianza que decide es la de las preguntas que afectan al score: `mentioned`, `mention_type`
y `strength` (en un Noul, la distancia a 0,5 hace de confianza). Si el juez y la detección por
reglas discrepan sobre la aparición, se limita a 0,5, igual que en `answers_to_evaluation`.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.domain.detection import detect_in_run
from posiq.domain.judge_questions import (
    JUDGE_QUESTIONS,
    QUESTIONS_VERSION,
    answers_to_evaluation,
    build_state,
)
from posiq.domain.schemas import Brand, Detection, Evaluation, OrigenEvaluacion, Run, Trace
from posiq.settings import usd_per_m_to_eur

Answers = dict[str, dict[str, Any]]
DISCREPANCY_CAP = 0.5


@dataclass(frozen=True)
class JudgeOutcome:
    """Resultado bruto de una llamada, antes de aplicar la política de confianza."""

    evaluation: Evaluation
    confianza: float
    answers: Answers


def noul_confidence(p: float) -> float:
    return abs(p - 0.5) * 2


def score_confidence(
    answers: Mapping[str, Mapping[str, Any]], detection: Detection | None
) -> float:
    """Mínimo de las confianzas de `mentioned`, `mention_type` y `strength` (ver módulo)."""
    p = float(answers["mentioned"]["noul"])
    if detection is None:
        return min(noul_confidence(p), DISCREPANCY_CAP) if p >= 0.5 else noul_confidence(p)
    confianza = min(
        noul_confidence(p),
        float(answers["mention_type"]["confidence"]),
        float(answers["strength"]["confidence"]),
    )
    discrepa = p < 0.5 or answers["mention_type"]["choice"] == "ausente"
    return min(confianza, DISCREPANCY_CAP) if discrepa else confianza


def answers_to_dict(answers: Mapping[str, Any]) -> Answers:
    """Respuestas del SDK (modelos Pydantic) a diccionarios con claves en texto."""
    out: Answers = {}
    for key, answer in answers.items():
        data = answer.model_dump(mode="json") if hasattr(answer, "model_dump") else dict(answer)
        out[key] = data
    return out


class SystemOneJudge(ABC):
    """`ports.Judge` sobre una API System One. Las subclases solo implementan la llamada."""

    origen: OrigenEvaluacion

    def __init__(
        self,
        *,
        name: str,
        model: str,
        market: Sequence[Brand],
        accept: float,
        fallback_threshold: float,
        price_in_usd_per_m: float,
        price_out_usd_per_m: float,
        usd_eur: float,
        concurrency: int = 8,
        fallback: "SystemOneJudge | None" = None,
        budget: Budget | None = None,
        cache: DiskCache | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.market = list(market)
        self.accept = accept
        self.fallback_threshold = fallback_threshold
        self.price_in = price_in_usd_per_m
        self.price_out = price_out_usd_per_m
        self.usd_eur = usd_eur
        self.concurrency = concurrency
        self.fallback = fallback
        self.budget = budget
        self.cache = cache
        self.traces: list[Trace] = []

    # --- A implementar por cada API ---------------------------------------------------------------

    @abstractmethod
    def _open(self) -> Any:
        """Cliente asíncrono de la API (se usa como `async with`)."""

    @abstractmethod
    async def _call(
        self, client: Any, state: dict[str, Any], questions: Mapping[str, Any]
    ) -> tuple[Answers, int, int]:
        """Envía `state` con `questions`; devuelve respuestas y tokens de entrada/salida."""

    # --- Interfaz pública -------------------------------------------------------------------------

    def evaluate(self, run: Run, brand: Brand) -> Evaluation:
        """Versión síncrona de `aevaluate` (no usar dentro de un bucle de eventos en marcha)."""
        return asyncio.run(self.aevaluate(run, brand))

    def evaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        """Evalúa un lote en paralelo, como mucho `concurrency` llamadas a la vez."""
        return asyncio.run(self.aevaluate_many(pairs))

    async def aevaluate_many(self, pairs: Sequence[tuple[Run, Brand]]) -> list[Evaluation]:
        semaphore = asyncio.Semaphore(self.concurrency)
        async with self._session() as client:

            async def one(run: Run, brand: Brand) -> Evaluation:
                async with semaphore:
                    return await self.aevaluate(run, brand, client=client)

            return list(await asyncio.gather(*(one(r, b) for r, b in pairs)))

    async def aevaluate(self, run: Run, brand: Brand, *, client: Any | None = None) -> Evaluation:
        outcome = await self.ajudge(run, brand, client=client)
        if outcome.confianza < self.fallback_threshold and self.fallback is not None:
            return await self.fallback.aevaluate(run, brand)
        return outcome.evaluation.model_copy(
            update={
                "confianza": outcome.confianza,
                "necesita_revision": outcome.confianza < self.accept,
            }
        )

    async def ajudge(self, run: Run, brand: Brand, *, client: Any | None = None) -> JudgeOutcome:
        """Una llamada al juez sin política: evaluación, confianza de score y respuestas."""
        brands = (
            self.market if any(b.id == brand.id for b in self.market) else [*self.market, brand]
        )
        detection = detect_in_run(run, brands).get(brand.id)
        state = build_state(run, brand)
        answers = await self.ask(run.study_id, state, client=client)
        evaluation = answers_to_evaluation(answers, run, brand, detection, origen=self.origen)
        return JudgeOutcome(evaluation, score_confidence(answers, detection), answers)

    # --- Internos ---------------------------------------------------------------------------------

    @asynccontextmanager
    async def _session(self, client: Any | None = None) -> AsyncIterator[Any]:
        if client is not None:
            yield client
            return
        async with self._open() as opened:
            yield opened

    async def ask(
        self,
        study_id: str,
        state: dict[str, Any],
        *,
        questions: Mapping[str, Any] = JUDGE_QUESTIONS,
        version: str = f"judge_questions@{QUESTIONS_VERSION}",
        nodo: str | None = None,
        client: Any | None = None,
    ) -> Answers:
        """Una llamada System One con caché, `Trace` y presupuesto, para cualquier batería de
        preguntas (por defecto las de menciones). `version` identifica las preguntas en la caché y
        en la traza; `nodo` es el nombre de la traza (por defecto `judge:<nombre>`)."""
        nodo = nodo or f"judge:{self.name}"
        key = DiskCache.key(nodo, self.model, {"state": state, "questions": version})
        start = time.perf_counter()
        if self.cache is not None and (cached := self.cache.get(key)) is not None:
            self._record(study_id, nodo, version, 0, 0, start)
            return dict(cached)
        async with self._session(client) as session:
            answers, tokens_in, tokens_out = await self._call(session, state, questions)
        if self.cache is not None:
            self.cache.set(key, answers)
        self._record(study_id, nodo, version, tokens_in, tokens_out, start)
        return answers

    def _record(
        self, study_id: str, nodo: str, version: str, tokens_in: int, tokens_out: int, start: float
    ) -> None:
        trace = Trace(
            study_id=study_id,
            nodo=nodo,
            modelo=self.model,
            prompt_version=version,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            coste_eur=usd_per_m_to_eur(tokens_in, self.price_in, self.usd_eur)
            + usd_per_m_to_eur(tokens_out, self.price_out, self.usd_eur),
            duracion_ms=round((time.perf_counter() - start) * 1000),
            fecha=datetime.now(UTC),
        )
        self.traces.append(trace)
        if self.budget is not None:
            self.budget.record(trace)


__all__ = ["JUDGE_QUESTIONS", "Answers", "JudgeOutcome", "SystemOneJudge", "score_confidence"]

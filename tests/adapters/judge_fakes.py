"""Clientes System One falsos (sin red) para los tests de los jueces."""

import asyncio
from types import SimpleNamespace
from typing import Any

from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer


def sdk_answers(
    mentioned: float = 0.98,
    mention: str = "recomendacion_activa",
    level: int = 3,
    sentiment: str = "positivo",
    supported: float = 0.95,
    confidence: float = 0.9,
    mention_conf: float | None = None,
    strength_conf: float | None = None,
    sentiment_conf: float | None = None,
) -> dict[str, Any]:
    probs = {i: (0.91 if i == level else 0.03) for i in range(4)}
    return {
        "mentioned": NoulAnswer(type="noul", noul=mentioned),
        "mention_type": ChoiceAnswer(
            type="choice",
            choice=mention,
            confidence=mention_conf if mention_conf is not None else confidence,
            probabilities={mention: 0.9},
        ),
        "strength": ScoreAnswer(
            type="score",
            score=float(level),
            confidence=strength_conf if strength_conf is not None else confidence,
            legend={i: f"nivel {i}" for i in range(4)},
            probabilities=probs,
        ),
        "sentiment": ChoiceAnswer(
            type="choice",
            choice=sentiment,
            confidence=sentiment_conf if sentiment_conf is not None else confidence,
            probabilities={sentiment: 0.9},
        ),
        "supports_with_source": NoulAnswer(type="noul", noul=supported),
    }


class FakeSystemOneClient:
    """Imita AsyncTypeSafeClient y AsyncSystemOneAdapterClient."""

    def __init__(
        self, answers: dict[str, Any] | None = None, *, usage: Any = None, model: str | None = None
    ) -> None:
        self.answers = answers or sdk_answers()
        self.model = model
        self.usage = usage or SimpleNamespace(input_tokens=1000, output_tokens=20)
        self.calls: list[dict[str, Any]] = []
        self.in_flight = 0
        self.max_in_flight = 0
        self.closed = 0

    async def __aenter__(self) -> "FakeSystemOneClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed += 1

    async def system_one(self, state: Any, questions: Any, **kwargs: Any) -> Any:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1
        self.calls.append({"state": state, "questions": questions, **kwargs})
        return SimpleNamespace(answers=self.answers, usage=self.usage, model=self.model)

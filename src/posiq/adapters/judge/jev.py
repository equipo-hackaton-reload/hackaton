"""Juez Jev (TypeSafe System One) con fallback al juez LLM cuando la confianza es baja."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.errors import require_secret
from posiq.adapters.judge.base import (
    Answers,
    SystemOneJudge,
    answers_to_dict,
    served_model,
)
from posiq.domain.schemas import Brand
from posiq.settings import Settings

# Reintentos con espera creciente ante 408, 429 y 5xx (lo hace el SDK).
RETRY = RetryPolicy(max_retries=4, backoff_initial=0.5, backoff_max=8.0)


class JevJudge(SystemOneJudge):
    origen = "jev"

    def __init__(
        self,
        settings: Settings,
        market: Sequence[Brand],
        *,
        fallback: SystemOneJudge | None = None,
        budget: Budget | None = None,
        cache: DiskCache | None = None,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(
            name="jev",
            model=settings.jev_model,
            market=market,
            accept=settings.judge_confidence_accept,
            fallback_threshold=settings.judge_confidence_fallback,
            price_in_usd_per_m=settings.jev_price_in_usd_per_m,
            price_out_usd_per_m=settings.jev_price_out_usd_per_m,
            usd_eur=settings.usd_eur,
            concurrency=settings.judge_concurrency,
            fallback=fallback,
            budget=budget,
            cache=cache,
        )
        self._factory = client_factory or (
            lambda: AsyncTypeSafeClient(
                api_key=require_secret(settings.typesafe_api_key, "TYPESAFE_API_KEY", "JevJudge"),
                model=self.model,
                retry=RETRY,
            )
        )

    def _open(self) -> Any:
        return self._factory()

    async def _call(
        self, client: Any, state: dict[str, Any], questions: Mapping[str, Any]
    ) -> tuple[Answers, int, int, str | None]:
        # System One no admite temperatura ni semilla (`SystemOneRequest` solo lleva model, state,
        # questions y assets): la reproducibilidad sale del modelo fijado y de la caché en disco.
        response = await client.system_one(state=state, questions=questions, model=self.model)
        usage = response.usage
        return (
            answers_to_dict(response.answers),
            usage.input_tokens,
            usage.output_tokens,
            served_model(response),
        )

"""Juez de fallback: las MISMAS preguntas de `judge_questions` respondidas por un LLM.

Usa `system-one-adapter` (sustituto del cliente de TypeSafe sobre APIs de LLM) apuntando al
endpoint compatible con OpenAI de settings (DeepSeek por defecto). Origen `fallback`.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from system_one_adapter import AsyncSystemOneAdapterClient
from system_one_adapter.providers.openai import AsyncOpenAIProvider
from typesafe_sdk import RetryPolicy

from posiq.adapters.budget import Budget
from posiq.adapters.cache import DiskCache
from posiq.adapters.errors import require_secret
from posiq.adapters.judge.base import Answers, SystemOneJudge, answers_to_dict
from posiq.adapters.llm.openai_compat import DEFAULT_MODEL
from posiq.domain.schemas import Brand
from posiq.settings import Settings

RETRY = RetryPolicy(max_retries=4, backoff_initial=0.5, backoff_max=8.0)


class _AdapterSession:
    """Cliente del adaptador y su proveedor (propiedad nuestra), cerrados juntos."""

    def __init__(self, settings: Settings, model: str) -> None:
        self.provider = AsyncOpenAIProvider(
            model,
            base_url=settings.deepseek_base_url,
            api_key=require_secret(settings.deepseek_api_key, "DEEPSEEK_API_KEY", "LLMJudge"),
            api="chat_completions",
        )
        # DeepSeek no ofrece JSON Schema estricto: se pide JSON y se valida en cliente.
        self.client = AsyncSystemOneAdapterClient(
            structured_outputs=False,
            llm_answer_mode="probabilities",
            normalize_probabilities=True,
            n_retry_malformed_structure=2,
            retry=RETRY,
        )

    async def __aenter__(self) -> "_AdapterSession":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.client.aclose()
        await self.provider.aclose()

    async def system_one(self, state: Any, questions: Any, **_: Any) -> Any:
        return await self.client.system_one(state, questions, model=self.provider)


class LLMJudge(SystemOneJudge):
    origen = "fallback"

    def __init__(
        self,
        settings: Settings,
        market: Sequence[Brand],
        *,
        budget: Budget | None = None,
        cache: DiskCache | None = None,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        model = settings.deepseek_model or DEFAULT_MODEL
        super().__init__(
            name="llm",
            model=model,
            market=market,
            accept=settings.judge_confidence_accept,
            fallback_threshold=settings.judge_confidence_fallback,
            price_in_usd_per_m=settings.deepseek_price_in_usd_per_m,
            price_out_usd_per_m=settings.deepseek_price_out_usd_per_m,
            usd_eur=settings.usd_eur,
            concurrency=settings.judge_concurrency,
            budget=budget,
            cache=cache,
        )
        self._factory = client_factory or (lambda: _AdapterSession(settings, model))

    def _open(self) -> Any:
        return self._factory()

    async def _call(
        self, client: Any, state: dict[str, Any], questions: Mapping[str, Any]
    ) -> tuple[Answers, int, int]:
        response = await client.system_one(state, questions)
        usage = response.usage
        tokens_in = getattr(usage, "input_tokens_total", None) or getattr(usage, "input_tokens", 0)
        tokens_out = getattr(usage, "output_tokens_total", None) or getattr(
            usage, "output_tokens", 0
        )
        return answers_to_dict(response.answers), int(tokens_in or 0), int(tokens_out or 0)

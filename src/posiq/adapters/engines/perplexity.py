"""Perplexity: API Sonar, compatible con chat completions; busca por defecto en cada petición.

Se usa el SDK de OpenAI con `base_url` de Perplexity. Fuentes: `citations` (lista de URLs) y, si no
viene, `search_results` (objetos con `url`). Son campos extra de la respuesta. Se cobra una tarifa
por petición, que aquí cuenta como una búsqueda.
"""

from typing import Any

import openai
from pydantic import SecretStr

from posiq.adapters.engines.base import EngineReply, Pricing, RealEngine


def _url(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("url")
    return getattr(item, "url", None)


class PerplexityEngine(RealEngine):
    motor = "Perplexity"
    key_variable = "PERPLEXITY_API_KEY"
    retryable_errors = (openai.APIConnectionError,)

    @property
    def model(self) -> str:
        return self._settings.perplexity_engine_model

    @property
    def pricing(self) -> Pricing:
        s = self._settings
        return Pricing(
            s.pricing_perplexity_in, s.pricing_perplexity_out, s.pricing_perplexity_search
        )

    def _secret(self) -> SecretStr:
        return self._settings.perplexity_api_key

    def _make_client(self, api_key: str) -> Any:
        return openai.OpenAI(
            api_key=api_key, base_url=self._settings.perplexity_base_url, max_retries=0
        )

    def _call(self, texto: str) -> EngineReply:
        response = self._retry(
            lambda: self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": texto}]
            )
        )
        raw = response.model_dump() if hasattr(response, "model_dump") else {}
        items = raw.get("citations") or raw.get("search_results") or []
        urls = [u for item in items if (u := _url(item))]
        usage = getattr(response, "usage", None)
        return EngineReply(
            texto=response.choices[0].message.content or "",
            urls=urls,
            modelo=getattr(response, "model", None) or self.model,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            busquedas=1,
        )

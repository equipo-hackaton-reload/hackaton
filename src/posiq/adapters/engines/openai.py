"""ChatGPT: API de respuestas (Responses API) de OpenAI con la herramienta `web_search`.

Fuentes: anotaciones `url_citation` del contenido del mensaje. Cada elemento `web_search_call` de la
salida cuenta como una búsqueda.
"""

from typing import Any

import openai
from pydantic import SecretStr

from posiq.adapters.engines.base import EngineReply, Pricing, RealEngine


class OpenAIEngine(RealEngine):
    motor = "ChatGPT"
    key_variable = "OPENAI_API_KEY"
    retryable_errors = (openai.APIConnectionError,)

    @property
    def model(self) -> str:
        return self._settings.openai_engine_model

    @property
    def pricing(self) -> Pricing:
        s = self._settings
        return Pricing(s.pricing_chatgpt_in, s.pricing_chatgpt_out, s.pricing_chatgpt_search)

    def _secret(self) -> SecretStr:
        return self._settings.openai_api_key

    def _make_client(self, api_key: str) -> Any:
        return openai.OpenAI(api_key=api_key, max_retries=0)

    def _call(self, texto: str) -> EngineReply:
        response = self._retry(
            lambda: self.client.responses.create(
                model=self.model, input=texto, tools=[{"type": "web_search"}]
            )
        )
        urls: list[str] = []
        busquedas = 0
        for item in getattr(response, "output", None) or []:
            if item.type == "web_search_call":
                busquedas += 1
            elif item.type == "message":
                for part in getattr(item, "content", None) or []:
                    for ann in getattr(part, "annotations", None) or []:
                        if ann.type == "url_citation":
                            urls.append(ann.url)
        usage = getattr(response, "usage", None)
        return EngineReply(
            texto=response.output_text or "",
            urls=urls,
            modelo=getattr(response, "model", None) or self.model,
            tokens_in=getattr(usage, "input_tokens", 0) or 0,
            tokens_out=getattr(usage, "output_tokens", 0) or 0,
            busquedas=busquedas,
        )

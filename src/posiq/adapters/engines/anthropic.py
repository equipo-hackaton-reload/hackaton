"""Claude: Messages API de Anthropic con la herramienta de servidor `web_search`.

Fuentes: bloques `web_search_tool_result` del contenido (su `content` es una lista de
`web_search_result` con `url`; si es un objeto, es un error de la herramienta y se registra). Si el
bucle de búsqueda del servidor se pausa (`stop_reason == "pause_turn"`), se reenvía el turno del
asistente tal cual para que continúe, hasta `MAX_CONTINUATIONS` veces. Las búsquedas se cuentan con
`usage.server_tool_use.web_search_requests`.
"""

import logging
from functools import partial
from typing import Any

import anthropic
from pydantic import SecretStr

from posiq.adapters.engines.base import EngineReply, Pricing, RealEngine

logger = logging.getLogger(__name__)

MAX_CONTINUATIONS = 5
# `web_search_20260209` (con filtrado dinámico) no está en Haiku; ahí se usa la versión básica.
BASIC_SEARCH_MODELS = ("claude-haiku",)
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicEngine(RealEngine):
    motor = "Claude"
    key_variable = "ANTHROPIC_API_KEY"
    retryable_errors = (anthropic.APIConnectionError,)

    @property
    def model(self) -> str:
        return self._settings.anthropic_engine_model

    @property
    def pricing(self) -> Pricing:
        s = self._settings
        return Pricing(s.pricing_claude_in, s.pricing_claude_out, s.pricing_claude_search)

    def _secret(self) -> SecretStr:
        return self._settings.anthropic_api_key

    def _make_client(self, api_key: str) -> Any:
        return anthropic.Anthropic(api_key=api_key, max_retries=0)

    @property
    def tool(self) -> dict[str, Any]:
        basic = self.model.startswith(BASIC_SEARCH_MODELS)
        return {
            "type": "web_search_20250305" if basic else "web_search_20260209",
            "name": "web_search",
            "max_uses": self._settings.anthropic_engine_max_searches,
        }

    def _create(self, messages: list[dict[str, Any]]) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self._settings.anthropic_engine_max_tokens,
            "messages": messages,
            "tools": [self.tool],
        }
        if self.model.startswith("claude-haiku"):
            return self.client.messages.create(**kwargs)
        # Si el modelo rechaza por seguridad, la API reintenta con otro y `response.model` lo dice.
        return self.client.beta.messages.create(
            **kwargs, betas=[FALLBACK_BETA], fallbacks="default"
        )

    def _call(self, texto: str) -> EngineReply:
        messages: list[dict[str, Any]] = [{"role": "user", "content": texto}]
        partes: list[str] = []
        urls: list[str] = []
        tokens_in = tokens_out = busquedas = 0
        modelo = self.model
        for _ in range(1 + MAX_CONTINUATIONS):
            response = self._retry(partial(self._create, messages))
            modelo = getattr(response, "model", None) or modelo
            usage = getattr(response, "usage", None)
            tokens_in += getattr(usage, "input_tokens", 0) or 0
            tokens_out += getattr(usage, "output_tokens", 0) or 0
            server = getattr(usage, "server_tool_use", None)
            busquedas += getattr(server, "web_search_requests", 0) or 0
            for block in response.content:
                if block.type == "text":
                    partes.append(block.text)
                elif block.type == "web_search_tool_result":
                    if isinstance(block.content, list):
                        urls += [r.url for r in block.content if getattr(r, "url", None)]
                    else:
                        logger.warning(
                            "Claude: error de web_search: %s",
                            getattr(block.content, "error_code", block.content),
                        )
            if response.stop_reason != "pause_turn":
                if response.stop_reason == "refusal":
                    logger.warning("Claude: el modelo rechazó responder (%s)", modelo)
                break
            # Búsqueda larga pausada: se reenvía el turno tal cual y el servidor continúa.
            messages = [*messages, {"role": "assistant", "content": response.content}]
        else:
            logger.warning("Claude: sigue en pause_turn tras %d continuaciones", MAX_CONTINUATIONS)
        return EngineReply(
            texto="".join(partes),
            urls=urls,
            modelo=modelo,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            busquedas=busquedas,
        )

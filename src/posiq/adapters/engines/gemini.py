"""Gemini: SDK `google-genai` con la herramienta *Grounding with Google Search* (`google_search`).

Fuentes: `grounding_metadata.grounding_chunks` del candidato. La `uri` de cada fragmento suele ser
una redirección de `vertexaisearch.cloud.google.com`, así que el dominio real se toma de
`web.domain` o, si no viene, de `web.title` (Google pone ahí el dominio). Se cobra por petición con
búsqueda: cuenta una búsqueda si hay `grounding_metadata` con consultas o fragmentos.
"""

from typing import Any

import httpx
from google import genai
from google.genai import types
from pydantic import SecretStr

from posiq.adapters.engines.base import EngineReply, Pricing, RealEngine, domain_of

REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)


def chunk_domain(web: Any) -> str | None:
    """Dominio de un fragmento web: `domain`, host de `uri` si no es redirección, o `title`."""
    if domain := getattr(web, "domain", None):
        return str(domain)
    uri = getattr(web, "uri", None) or ""
    host = domain_of(uri)
    if host and not host.endswith(REDIRECT_HOSTS):
        return host
    title = getattr(web, "title", None) or ""
    return domain_of(title)


class GeminiEngine(RealEngine):
    motor = "Gemini"
    key_variable = "GEMINI_API_KEY"
    retryable_errors = (httpx.TransportError,)

    @property
    def model(self) -> str:
        return self._settings.gemini_engine_model

    @property
    def pricing(self) -> Pricing:
        s = self._settings
        return Pricing(s.pricing_gemini_in, s.pricing_gemini_out, s.pricing_gemini_search)

    def _secret(self) -> SecretStr:
        return self._settings.gemini_api_key

    def _make_client(self, api_key: str) -> Any:
        return genai.Client(api_key=api_key)

    def _call(self, texto: str) -> EngineReply:
        config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        response = self._retry(
            lambda: self.client.models.generate_content(
                model=self.model, contents=texto, config=config
            )
        )
        candidates = getattr(response, "candidates", None) or []
        metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
        chunks = getattr(metadata, "grounding_chunks", None) or []
        queries = getattr(metadata, "web_search_queries", None) or []
        urls = [d for c in chunks if (web := getattr(c, "web", None)) and (d := chunk_domain(web))]
        usage = getattr(response, "usage_metadata", None)
        # Los tokens de razonamiento se facturan como salida.
        tokens_out = (getattr(usage, "candidates_token_count", 0) or 0) + (
            getattr(usage, "thoughts_token_count", 0) or 0
        )
        return EngineReply(
            texto=response.text or "",
            urls=urls,
            modelo=getattr(response, "model_version", None) or self.model,
            tokens_in=getattr(usage, "prompt_token_count", 0) or 0,
            tokens_out=tokens_out,
            busquedas=1 if (queries or chunks) else 0,
        )

"""Configuración de posiq. leída de variables de entorno / `.env`. Ninguna clave va en el código."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    deepseek_api_key: SecretStr = SecretStr("")
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = ""

    typesafe_api_key: SecretStr = SecretStr("")
    jev_model: str = "jev-latest"

    openai_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    perplexity_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")

    database_url: str = "sqlite:///./posiq.db"

    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = ""

    budget_eur_max: float = 5.0
    judge_confidence_accept: float = 0.80
    judge_confidence_fallback: float = 0.55
    judge_concurrency: int = 8

    # Precios en USD por millón de tokens (verificar en la documentación oficial vigente).
    deepseek_price_in_usd_per_m: float = 0.28
    deepseek_price_out_usd_per_m: float = 0.42
    jev_price_in_usd_per_m: float = 0.04
    jev_price_out_usd_per_m: float = 0.0
    usd_eur: float = 0.86

    cache_enabled: bool = True
    cache_path: str = ".cache/posiq_cache.sqlite"

    kit_dir: str = "data/kit/02_Datos/caso_oftalmologia"

    # Motores reales (ADR 0006). Modelos y precios PROVISIONALES: contrastar con la página de
    # precios oficial antes de lanzar un estudio. Tokens en USD por millón; búsqueda en USD por
    # búsqueda (Gemini y Perplexity cobran por petición con búsqueda).
    engine_concurrency: int = 4
    engine_max_retries: int = 4
    engine_backoff_base_s: float = 1.0
    openai_engine_model: str = "gpt-5-mini"
    pricing_chatgpt_in: float = 0.25
    pricing_chatgpt_out: float = 2.00
    pricing_chatgpt_search: float = 0.01
    gemini_engine_model: str = "gemini-2.5-flash"
    pricing_gemini_in: float = 0.30
    pricing_gemini_out: float = 2.50
    pricing_gemini_search: float = 0.035
    perplexity_engine_model: str = "sonar"
    perplexity_base_url: str = "https://api.perplexity.ai"
    pricing_perplexity_in: float = 1.00
    pricing_perplexity_out: float = 1.00
    pricing_perplexity_search: float = 0.005
    anthropic_engine_model: str = "claude-opus-5-5"
    anthropic_engine_max_searches: int = 5
    anthropic_engine_max_tokens: int = 16000
    pricing_claude_in: float = 4.00
    pricing_claude_out: float = 20.00
    pricing_claude_search: float = 0.01


def usd_per_m_to_eur(tokens: int, usd_per_m: float, usd_eur: float) -> float:
    """Coste en EUR de `tokens` a `usd_per_m` dólares por millón."""
    return tokens * usd_per_m / 1_000_000 * usd_eur

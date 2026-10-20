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

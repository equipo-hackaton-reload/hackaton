from pathlib import Path

import pytest

from posiq.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Settings aislados del .env local, con caché en un directorio temporal."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        typesafe_api_key="ts-test",
        cache_path=str(tmp_path / "cache.sqlite"),
    )

"""`scripts/demo_kit.py` sigue funcionando con cuentas: registra, verifica y entra como demo."""

import importlib.util
from pathlib import Path
from types import ModuleType

from fastapi.testclient import TestClient

from posiq.interfaces.api.main import create_app
from posiq.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("demo_kit", ROOT / "scripts/demo_kit.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_kit_logs_in_and_downloads_the_word(tmp_path: Path) -> None:
    demo_kit = load_script()
    settings = Settings(
        _env_file=None,
        llm_provider="fixture",
        database_url=f"sqlite:///{(tmp_path / 'study.db').as_posix()}",
        cache_enabled=False,
    )
    with TestClient(create_app(settings=settings)) as client:
        path = demo_kit.demo(client, tmp_path / "out", timeout=60)
        assert path.exists() and path.stat().st_size > 0
        # Segunda vez: el usuario de demo ya existe y solo hace login.
        client.headers.pop("Authorization")
        demo_kit.login(client)
        estudios = client.get("/studies").json()
        assert len(estudios) == 1

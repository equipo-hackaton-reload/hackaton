from pathlib import Path

import pytest

KIT_DIR = Path(__file__).resolve().parents[1] / "data" / "kit" / "02_Datos" / "caso_oftalmologia"


@pytest.fixture(scope="session")
def kit_dir() -> Path:
    return KIT_DIR

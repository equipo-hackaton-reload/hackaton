import pytest

from posiq.adapters.repo.sql import SqlStudyRepo
from tests.application.fakes import memory_repo


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def repo() -> SqlStudyRepo:
    return memory_repo()

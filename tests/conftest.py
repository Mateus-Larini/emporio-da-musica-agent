from __future__ import annotations

from pathlib import Path

import pytest

from emporio_agent.data.loader import build_database
from emporio_agent.data.repository import Repository


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("db") / "emporio.db"
    return build_database(path)


@pytest.fixture(scope="session")
def repo(db_path: Path) -> Repository:
    r = Repository(db_path)
    yield r
    r.close()

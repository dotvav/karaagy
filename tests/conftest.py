"""Pytest fixtures and setup for Karaagy."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from karaagy.config import settings
from karaagy.core.database import DatabaseManager
from karaagy.main import app


@pytest.fixture(autouse=True)
def setup_isolated_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate database and thread directories to temporary paths for all tests."""
    test_db = tmp_path / "test_karaagy.db"
    test_threads = tmp_path / "karaagy_threads"
    monkeypatch.setattr(settings, "database_path", test_db)
    monkeypatch.setattr(settings, "threads_dir", test_threads)
    DatabaseManager.init_db()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client

"""Pytest fixtures and setup."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from src.my_project.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client

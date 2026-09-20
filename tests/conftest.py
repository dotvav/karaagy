"""Pytest fixtures and setup for Karaagy."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from karaagy.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client

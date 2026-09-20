"""Tests for main FastAPI application routes."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Test health check route returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ping(client: TestClient) -> None:
    """Test ping route returns pong."""
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    assert response.json()["message"] == "pong"

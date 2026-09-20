"""Tests for health and root endpoints."""

from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Karaagy"
    assert data["status"] == "online"


def test_healthz_endpoint(client: TestClient) -> None:
    """Test /healthz endpoint returns status ok."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "karaagy"


def test_v1_health_endpoint(client: TestClient) -> None:
    """Test /v1/health endpoint returns status ok."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

"""Tests for /v1/models endpoints."""

from fastapi.testclient import TestClient

from karaagy.core.registry import ModelRegistry


def test_list_models(client: TestClient) -> None:
    """Test GET /v1/models returns OpenAI formatted model list."""
    ModelRegistry._cached_models = ["gemini-3.8-flash-high", "claude-sonnet-4-6"]
    ModelRegistry._last_fetched_at = 9999999999.0
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0

    ids = [item["id"] for item in data["data"]]
    assert "gemini-3.8-flash-high" in ids
    assert "gpt-4o" in ids


def test_get_model_detail(client: TestClient) -> None:
    """Test GET /v1/models/{model_id} returns individual model card."""
    response = client.get("/v1/models/gpt-4o")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "gpt-4o"
    assert data["object"] == "model"


def test_get_model_not_found(client: TestClient) -> None:
    """Test GET /v1/models/{unknown} returns 404."""
    response = client.get("/v1/models/non-existent-model-xyz")
    assert response.status_code == 404

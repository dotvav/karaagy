"""Tests for health and root endpoints."""

from fastapi.testclient import TestClient


def test_root_endpoint_json(client: TestClient) -> None:
    """Test root endpoint returns JSON status payload for API clients."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Karaagy"
    assert data["status"] == "online"
    assert "metrics" in data
    assert "models" in data
    assert "karaagy" in data
    assert "antigravity" in data


def test_root_endpoint_html(client: TestClient) -> None:
    """Test root endpoint returns HTML dashboard when requested with text/html."""
    response = client.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<!DOCTYPE html>" in response.text
    assert "Karaagy" in response.text
    assert "Antigravity Quota" in response.text
    assert "Discovered Models" in response.text


def test_system_status_endpoint(client: TestClient) -> None:
    """Test /v1/system/status diagnostics endpoint."""
    response = client.get("/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Karaagy"
    assert "metrics" in data
    assert "uptime_seconds" in data["metrics"]


def test_refresh_usage_endpoint(client: TestClient) -> None:
    """Test /v1/system/refresh-usage quota cache invalidation."""
    response = client.post("/v1/system/refresh-usage")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "refreshed"
    assert "quota" in data


def test_sanitized_environment_masking() -> None:
    """Test sensitive secrets are fully redacted without leading chars and safe keys remain unmasked."""
    import os
    from unittest.mock import patch

    from karaagy.core.diagnostics import DiagnosticsManager

    mock_env = {
        "OPENAI_API_KEY": "sk-proj-secret123456",
        "MY_AUTH_TOKEN": "token_abc_xyz",
        "DATABASE_PASSWORD": "supersecretpassword",
        "HOME": "/home/karaagy",
        "KARAAGY_PORT": "8000",
        "KARAAGY_ENABLE_AUTO_PRUNE_SESSIONS": "true",
        "KARAAGY_MAX_CONCURRENT_SESSIONS": "4",
    }
    with patch.dict(os.environ, mock_env, clear=True):
        env_dict = DiagnosticsManager.get_sanitized_environment()
        assert env_dict["OPENAI_API_KEY"] == "[REDACTED]"
        assert env_dict["MY_AUTH_TOKEN"] == "[REDACTED]"
        assert env_dict["DATABASE_PASSWORD"] == "[REDACTED]"
        assert env_dict["HOME"] == "/home/karaagy"
        assert env_dict["KARAAGY_PORT"] == "8000"
        assert env_dict["KARAAGY_ENABLE_AUTO_PRUNE_SESSIONS"] == "true"
        assert env_dict["KARAAGY_MAX_CONCURRENT_SESSIONS"] == "4"


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

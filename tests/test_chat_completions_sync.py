"""Tests for POST /v1/chat/completions synchronous endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from karaagy.models.openai import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionResponse,
    UsageInfo,
)


def test_chat_completions_missing_messages(client: TestClient) -> None:
    """Test 400 when messages array is empty."""
    payload = {"model": "gpt-4o", "messages": []}
    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "missing_required_field"


@patch("karaagy.api.routes_chat.execute_agy_json", new_callable=AsyncMock)
def test_chat_completions_sync_success(mock_execute: AsyncMock, client: TestClient) -> None:
    """Test successful synchronous chat completion."""
    mock_execute.return_value = ChatCompletionResponse(
        id="chatcmpl-test123456",
        model="gemini-3.8-flash-high",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", content="Hello! How can I help you today?"
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    )

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello!"}],
        "stream": False,
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "chatcmpl-test123456"
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
    assert data["usage"]["total_tokens"] == 18


@patch("karaagy.api.routes_chat.execute_agy_json", new_callable=AsyncMock)
def test_chat_completions_runtime_error(mock_execute: AsyncMock, client: TestClient) -> None:
    """Test 500 when AGY execution fails."""
    mock_execute.side_effect = RuntimeError("AGY CLI error: binary crashed")

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello!"}],
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert "binary crashed" in data["error"]["message"]

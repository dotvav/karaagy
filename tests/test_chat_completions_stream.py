"""Tests for POST /v1/chat/completions streaming SSE endpoints."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

from fastapi.testclient import TestClient


async def mock_stream_generator(*args, **kwargs) -> AsyncGenerator[str, None]:
    """Mock async generator yielding SSE event lines."""
    yield 'data: {"id":"chatcmpl-stream1","object":"chat.completion.chunk","created":1700000000,"model":"gemini-3.8-flash-high","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n'
    yield 'data: {"id":"chatcmpl-stream1","object":"chat.completion.chunk","created":1700000000,"model":"gemini-3.8-flash-high","choices":[{"index":0,"delta":{"content":"Hi"},"finish_reason":null}]}\n\n'
    yield 'data: {"id":"chatcmpl-stream1","object":"chat.completion.chunk","created":1700000000,"model":"gemini-3.8-flash-high","choices":[{"index":0,"delta":{"content":" there!"},"finish_reason":null}]}\n\n'
    yield 'data: {"id":"chatcmpl-stream1","object":"chat.completion.chunk","created":1700000000,"model":"gemini-3.8-flash-high","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":3,"total_tokens":8}}\n\n'
    yield "data: [DONE]\n\n"


@patch("karaagy.api.routes_chat.execute_agy_stream", side_effect=mock_stream_generator)
def test_chat_completions_streaming_sse(mock_stream: object, client: TestClient) -> None:
    """Test SSE streaming response format."""
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "chat.completion.chunk" in body
    assert "Hi" in body
    assert " there!" in body
    assert "data: [DONE]" in body

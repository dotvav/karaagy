"""Tests for POST /v1/chat/completions streaming SSE endpoints."""

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


@patch("karaagy.api.routes_chat.execute_agy_stream", side_effect=mock_stream_generator)
def test_chat_completions_streaming_json_object(mock_stream: object, client: TestClient) -> None:
    """Test streaming request with response_format json_object passes expect_json=True."""
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Return count in JSON"}],
        "response_format": {"type": "json_object"},
        "stream": True,
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    mock_fn = mock_stream  # type: ignore[assignment]
    assert mock_fn.call_args.kwargs["expect_json"] is True


@patch("karaagy.api.routes_chat.build_agy_prompt")
@patch("karaagy.api.routes_chat.execute_agy_stream", side_effect=mock_stream_generator)
def test_chat_completions_streaming_json_schema(
    mock_stream: object, mock_prompt: object, client: TestClient
) -> None:
    """Test streaming request with response_format json_schema passes expect_json=True and schema to prompt."""
    mock_prompt.return_value = "prompt text"  # type: ignore[attr-defined]
    schema_def = {
        "type": "json_schema",
        "json_schema": {
            "name": "item",
            "schema": {"type": "object", "properties": {"id": {"type": "integer"}}},
        },
    }
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Return item"}],
        "response_format": schema_def,
        "stream": True,
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    mock_stream_fn = mock_stream  # type: ignore[assignment]
    assert mock_stream_fn.call_args.kwargs["expect_json"] is True
    mock_prompt_fn = mock_prompt  # type: ignore[assignment]
    assert mock_prompt_fn.call_args.kwargs.get("response_format") is not None


@pytest.mark.asyncio
async def test_execute_agy_stream_internal_strips_code_fences() -> None:
    """Test that _execute_agy_stream_internal strips code fences from stream chunks when expect_json=True."""
    from karaagy.core.process import _execute_agy_stream_internal

    # Create mock process with stdout readline yielding stream-json lines
    lines = [
        json.dumps(
            {
                "event": "step_update",
                "step_update": {"text_delta": '```json\n{"title": "'},
            }
        ).encode("utf-8")
        + b"\n",
        json.dumps(
            {
                "event": "step_update",
                "step_update": {"text_delta": 'Pasta"}\n```'},
            }
        ).encode("utf-8")
        + b"\n",
        json.dumps(
            {
                "event": "result",
                "result": {
                    "response": '```json\n{"title": "Pasta"}\n```',
                    "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                },
            }
        ).encode("utf-8")
        + b"\n",
        b"",
    ]

    mock_proc = AsyncMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    mock_proc.stdout = AsyncMock()
    mock_proc.stdout.readline.side_effect = lines
    mock_proc.wait = AsyncMock(return_value=0)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        events = []
        async for chunk in _execute_agy_stream_internal(
            prompt="Recipe",
            model="gemini-3.8-flash-high",
            expect_json=True,
        ):
            events.append(chunk)

    # Reconstruct text deltas from SSE chunks
    content_deltas = []
    for event in events:
        for line in event.splitlines():
            if line.startswith("data: ") and not line.endswith("[DONE]"):
                data = json.loads(line[6:])
                choice = data.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                if "content" in delta and delta["content"]:
                    content_deltas.append(delta["content"])

    full_content = "".join(content_deltas)
    assert full_content == '{"title": "Pasta"}'
    assert "```" not in full_content

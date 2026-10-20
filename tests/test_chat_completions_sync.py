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


@patch("karaagy.api.routes_chat.execute_agy_json", new_callable=AsyncMock)
def test_chat_completions_multimodal_payload(mock_execute: AsyncMock, client: TestClient) -> None:
    """Test handling of OpenAI multimodal vision messages payload."""
    mock_execute.return_value = ChatCompletionResponse(
        id="chatcmpl-multi123",
        model="gemini-3.8-flash-high",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", content="Matched console: Switch HAC-001"
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=50, completion_tokens=10, total_tokens=60),
    )

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": "You are a marketplace reconciler.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Reconcile this item:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://img.leboncoin.fr/test.jpg"},
                    },
                ],
            },
        ],
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["choices"][0]["message"]["content"] == "Matched console: Switch HAC-001"


@patch("karaagy.api.routes_chat.execute_agy_json", new_callable=AsyncMock)
def test_chat_completions_sync_json_object_strips_fences(
    mock_execute: AsyncMock, client: TestClient
) -> None:
    """Test response_format json_object strips markdown code fences from returned content."""
    mock_execute.return_value = ChatCompletionResponse(
        id="chatcmpl-jsonobj1",
        model="gemini-3.8-flash-high",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", content='```json\n{"status": "ok", "count": 42}\n```'
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=15, completion_tokens=10, total_tokens=25),
    )

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Return count in JSON"}],
        "response_format": {"type": "json_object"},
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["choices"][0]["message"]["content"] == '{"status": "ok", "count": 42}'
    assert mock_execute.call_args.kwargs["expect_json"] is True


@patch("karaagy.api.routes_chat.build_agy_prompt")
@patch("karaagy.api.routes_chat.execute_agy_json", new_callable=AsyncMock)
def test_chat_completions_sync_json_schema_strips_fences_and_passes_prompt(
    mock_execute: AsyncMock, mock_build_prompt: AsyncMock, client: TestClient
) -> None:
    """Test response_format json_schema passes format to prompt builder and strips code fences."""
    mock_build_prompt.return_value = "system and user prompt"
    mock_execute.return_value = ChatCompletionResponse(
        id="chatcmpl-jsonschema1",
        model="gemini-3.8-flash-high",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", content='```json\n{"title": "Pasta"}\n```'
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=20, completion_tokens=8, total_tokens=28),
    )

    schema_def = {
        "type": "json_schema",
        "json_schema": {
            "name": "recipe",
            "schema": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
        },
    }
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Give me a recipe"}],
        "response_format": schema_def,
    }

    response = client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["choices"][0]["message"]["content"] == '{"title": "Pasta"}'
    assert mock_execute.call_args.kwargs["expect_json"] is True

    # Verify build_agy_prompt was passed response_format
    assert mock_build_prompt.called
    passed_rf = mock_build_prompt.call_args.kwargs.get("response_format")
    assert passed_rf is not None


def test_models_openai_schema_helpers() -> None:
    """Test is_json_response_format and extract_json_schema helper functions."""
    from karaagy.models.openai import (
        ResponseFormat,
        ResponseFormatJsonSchema,
        extract_json_schema,
        is_json_response_format,
    )

    assert not is_json_response_format(None)
    assert not is_json_response_format({"type": "text"})
    assert is_json_response_format({"type": "json_object"})
    assert is_json_response_format({"type": "json_schema"})
    assert is_json_response_format(ResponseFormat(type="json_object"))
    assert is_json_response_format(ResponseFormat(type="json_schema"))

    # OpenAI nested schema
    rf_obj = ResponseFormat(
        type="json_schema",
        json_schema=ResponseFormatJsonSchema(
            name="test",
            schema={"type": "object", "properties": {"a": {"type": "number"}}},
        ),
    )
    schema = extract_json_schema(rf_obj)
    assert schema == {"type": "object", "properties": {"a": {"type": "number"}}}

    # Dict nested schema
    dict_rf = {
        "type": "json_schema",
        "json_schema": {"schema": {"type": "object", "properties": {"b": {"type": "string"}}}},
    }
    assert extract_json_schema(dict_rf) == {
        "type": "object",
        "properties": {"b": {"type": "string"}},
    }

    # Dict direct schema
    direct_rf = {
        "type": "json_schema",
        "schema": {"type": "object"},
    }
    assert extract_json_schema(direct_rf) == {"type": "object"}

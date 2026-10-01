"""Tests for OpenAI Assistants / Threads API endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from karaagy.models.openai import (
    ChatCompletionChoice,
    ChatCompletionMessage,
    ChatCompletionResponse,
    UsageInfo,
)


def test_create_and_get_thread(client: TestClient) -> None:
    """Test creating a thread and fetching its details."""
    response = client.post("/v1/threads", json={"metadata": {"test_key": "test_val"}})
    assert response.status_code == 201
    data = response.json()
    assert data["object"] == "thread"
    assert "id" in data
    assert data["metadata"]["test_key"] == "test_val"
    thread_id = data["id"]

    # Get thread
    get_res = client.get(f"/v1/threads/{thread_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == thread_id


def test_thread_messages_flow(client: TestClient) -> None:
    """Test adding messages and listing them in a thread."""
    # Create thread
    t_res = client.post("/v1/threads")
    assert t_res.status_code == 201
    thread_id = t_res.json()["id"]

    # Add message
    msg_res = client.post(
        f"/v1/threads/{thread_id}/messages",
        json={"role": "user", "content": "Bonjour !"},
    )
    assert msg_res.status_code == 201
    msg_data = msg_res.json()
    assert msg_data["object"] == "thread.message"
    assert msg_data["role"] == "user"
    assert msg_data["content"][0]["text"]["value"] == "Bonjour !"

    # List messages
    list_res = client.get(f"/v1/threads/{thread_id}/messages")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["object"] == "list"
    assert len(list_data["data"]) == 1
    assert list_data["data"][0]["id"] == msg_data["id"]


@patch("karaagy.core.threads._execute_agy_json_internal", new_callable=AsyncMock)
def test_thread_run_sync(mock_execute: AsyncMock, client: TestClient) -> None:
    """Test running a thread synchronously."""
    mock_execute.return_value = ChatCompletionResponse(
        id="chatcmpl-thread123",
        model="gemini-3.7-flash-low",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatCompletionMessage(
                    role="assistant", content="Salut ! Que puis-je faire pour toi ?"
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(prompt_tokens=20, completion_tokens=10, total_tokens=30),
    )

    # 1. Create thread with message
    t_res = client.post(
        "/v1/threads",
        json={"messages": [{"role": "user", "content": "Salut !"}]},
    )
    assert t_res.status_code == 201
    thread_id = t_res.json()["id"]

    # 2. Run thread
    run_res = client.post(
        f"/v1/threads/{thread_id}/runs",
        json={"model": "gemini-3.7-flash-low", "instructions": "Tu es Voizoche."},
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["object"] == "thread.run"
    assert run_data["status"] == "completed"
    assert run_data["thread_id"] == thread_id

    # 3. Check assistant message was added
    list_res = client.get(f"/v1/threads/{thread_id}/messages?order=asc")
    assert list_res.status_code == 200
    msgs = list_res.json()["data"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"][0]["text"]["value"] == "Salut ! Que puis-je faire pour toi ?"


def test_delete_thread(client: TestClient) -> None:
    """Test deleting a thread."""
    t_res = client.post("/v1/threads")
    assert t_res.status_code == 201
    thread_id = t_res.json()["id"]

    # Delete thread
    del_res = client.delete(f"/v1/threads/{thread_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Check 404
    get_res = client.get(f"/v1/threads/{thread_id}")
    assert get_res.status_code == 404


def test_thread_path_traversal_protection(client: TestClient) -> None:
    """Test that path traversal attempts in thread_id return 404 or error safely."""
    res_get = client.get("/v1/threads/..%2F..%2Fetc%2Fpasswd")
    assert res_get.status_code in {400, 404}

    res_del = client.delete("/v1/threads/..%2F..%2Fetc%2Fpasswd")
    assert res_del.status_code in {400, 404}


@patch("karaagy.core.threads._execute_agy_json_internal", new_callable=AsyncMock)
def test_thread_run_error_sanitization(mock_execute: AsyncMock, client: TestClient) -> None:
    """Test that thread run failure sanitizes last_error without leaking sensitive internal details."""
    mock_execute.side_effect = RuntimeError("Fatal DB crash at /etc/secret_token password=123")

    t_res = client.post("/v1/threads", json={"messages": [{"role": "user", "content": "Test"}]})
    thread_id = t_res.json()["id"]

    run_res = client.post(f"/v1/threads/{thread_id}/runs", json={"model": "gemini-3.7-flash-low"})
    assert run_res.status_code == 500
    err_data = run_res.json()
    assert "password=123" not in err_data["error"]["message"]
    assert "Internal server error" in err_data["error"]["message"]
